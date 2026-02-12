
import logging
from typing import Optional

from django.contrib.auth.models import User

from celery import shared_task
from .models import PACSQuery, PACSSeries
from .serializers import PACSSeriesSerializer


logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def delete_pacs_series(self, pacs_series_id):
    try:
        pacs_series = PACSSeries.objects.get(id=pacs_series_id)

        if not pacs_series.is_pending_deletion():
            return # idempotent safety

        pacs_series.delete()
    except PACSSeries.DoesNotExist:
        pass
    except Exception as e:
        PACSSeries.objects.filter(id=pacs_series_id).update( # atomic update
            deletion_status=PACSSeries.DeletionStatus.FAILED,
            deletion_error=str(e)
        )
        raise

@shared_task
def send_pacs_query(pacs_query_id):
    """
    Send PACS query.
    """
    #from celery.contrib import rdb;rdb.set_trace()
    try:
        pacs_query = PACSQuery.objects.get(pk=pacs_query_id)
    except PACSQuery.DoesNotExist:
        logger.error(f"PACS query with id {pacs_query_id} not found when running "
                     f"send_pacs_query task.")
    else:
        pacs_query.send()


@shared_task
def register_pacs_series(
    PatientID: str,
    StudyDate: str,
    StudyInstanceUID: str,
    SeriesInstanceUID: str,
    pacs_name: str,
    path: str,
    ndicom: int,
    PatientName: Optional[str] = None,
    PatientBirthDate: Optional[str] = None,
    PatientAge: Optional[int] = None,
    PatientSex: Optional[str] = None,
    AccessionNumber: Optional[str] = None,
    Modality: Optional[str] = None,
    ProtocolName: Optional[str] = None,
    StudyDescription: Optional[str] = None,
    SeriesDescription: Optional[str] = None,
):
    """
    Register a DICOM series (directory of DICOM files) to the database.

    Pre-condition: DICOM files *must* exist in storage before running this task.
    """
    data = {
        'PatientID': PatientID,
        'PatientName': PatientName,
        'PatientBirthDate': PatientBirthDate,
        'PatientAge': PatientAge,
        'PatientSex': PatientSex,
        'StudyDate': StudyDate,
        'AccessionNumber': AccessionNumber,
        'Modality': Modality,
        'ProtocolName': ProtocolName,
        'StudyInstanceUID': StudyInstanceUID,
        'StudyDescription': StudyDescription,
        'SeriesInstanceUID': SeriesInstanceUID,
        'SeriesDescription': SeriesDescription,
        'pacs_name': pacs_name,
        'path': path,
        'ndicom': ndicom,
    }
    serializer = PACSSeriesSerializer(data=_filter_some_values(data))
    serializer.is_valid(raise_exception=True)
    owner = User.objects.get(username='chris')
    serializer.save(owner=owner)


def _filter_some_values(x: dict[str, any]) -> dict[str, any]:
    """
    Remove entries where the value is ``None``.`
    """
    return {k: v for k, v in x.items() if v is not None}
