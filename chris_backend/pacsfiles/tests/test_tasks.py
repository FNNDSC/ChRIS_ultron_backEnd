import logging
import json
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.urls import reverse

from rest_framework import status
from rest_framework.exceptions import ValidationError

from core.models import ChrisFolder
from core.storage import connect_storage
from pacsfiles.models import PACS, PACSSeries, PACSFile
from pacsfiles.tasks import register_pacs_series


class PACSSeriesCreateTests(TestCase):
    """
    Test creating PACS series using the task function.
    """

    def setUp(self):
        self.storage_manager = connect_storage(settings)

    def tearDown(self):
        super().tearDown()
        test_data_dir = 'SERVICES/PACS/MyPACS/123456-crazy'
        if self.storage_manager.path_exists(test_data_dir):
            self.storage_manager.delete_path(test_data_dir)

    @tag('integration')
    def test_integration_pacs_series_create_success(self):
        series_instance_uid = '1.1.3432.54.6545674765.765434'
        series_dir = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE1/file2.dcm'
        path = series_dir + '/file2.dcm'
        fake_dicom_content = b'test file content'
        # upload fake file to storage
        self.storage_manager.upload_obj(path, fake_dicom_content)

        # invoke the task to register the file
        register_pacs_series(
            path=path,
            ndicom=1,
            PatientID='12345',
            PatientName='crazy',
            PatientSex='O',
            StudyDate='2020-07-15',
            StudyInstanceUID='1.1.3432.54.6545674765.765434',
            StudyDescription='brain crazy study',
            SeriesInstanceUID=series_instance_uid,
            SeriesDescription='SAG T1 MPRAGE',
            pacs_name='MyPACS',
        )

        # assert PACSSeries and PACSFile were created
        series = PACSSeries.objects.get(SeriesInstanceUID=series_instance_uid)
        self.assertEqual(series.StudyDescription, 'brain crazy study')

    def test_pacs_series_create_failure_already_exists(self):
        pacs_path = 'SERVICES/PACS/MyPACS'
        series_path = (
            f'{pacs_path}/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        )

        owner = User.objects.get(username='chris')
        series_folder, _ = ChrisFolder.objects.get_or_create(
            path=series_path, owner=owner
        )
        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path=pacs_path, owner=owner
        )
        pacs, _ = PACS.objects.get_or_create(
            identifier='MyPACS', folder=pacs_folder
        )
        existing_series, _ = PACSSeries.objects.get_or_create(
            PatientID='123456',
            StudyDate='2020-07-15',
            StudyInstanceUID='1.1.3432.54.6545674765.765434',
            SeriesInstanceUID='2.4.3432.54.845674765.763345',
            pacs=pacs,
            folder=series_folder,
        )

        file_content = b'example DICOM which should not be registered'
        self.storage_manager.upload_obj(
            f'{series_path}/file1.dcm', file_content
        )
        expected = (
            f'A DICOM series with SeriesInstanceUID={existing_series.SeriesInstanceUID} '
            'already registered for pacs MyPACS'
        )
        with self.assertRaisesRegex(ValidationError, expected):
            register_pacs_series(
                PatientID='12345',
                StudyDate='2020-07-15',
                StudyInstanceUID='1.1.3432.54.6545674765.765434',
                SeriesInstanceUID='2.4.3432.54.845674765.763345',
                pacs_name='MyPACS',
                path=series_path,
                ndicom=1,
                PatientName='crazy',
                PatientSex='O',
                StudyDescription='brain_crazy_study',
                SeriesDescription='SAG T1 MPRAGE',
            )
