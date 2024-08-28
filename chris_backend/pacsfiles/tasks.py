from celery import shared_task
from django.contrib.auth.models import User

from .serializers import PACSSeriesSerializer


@shared_task
def register_pacs_series(
        patient_id: str,
        patient_name: str,
        study_date: str,
        study_instance_uid: str,
        study_description: str,
        series_description: str,
        series_instance_uid: str,
        pacs_name: str,
        path: str,
        ndicom: int
):
    """
    Register a DICOM series (directory of DICOM files) existing in storage to the database,
    """
    data = {
        'PatientID': patient_id,
        'PatientName': patient_name,
        'StudyDate': study_date,
        'StudyInstanceUID': study_instance_uid,
        'StudyDescription': study_description,
        'SeriesInstanceUID': series_instance_uid,
        'SeriesDescription': series_description,
        'pacs_name': pacs_name,
        'path': path,
        'ndicom': ndicom
    }
    serializer = PACSSeriesSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    owner = User.objects.get(username='chris')
    serializer.save(owner=owner)
