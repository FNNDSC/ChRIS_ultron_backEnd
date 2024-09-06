from typing import Optional
from celery import shared_task
from django.contrib.auth.models import User

from .serializers import PACSSeriesSerializer


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
