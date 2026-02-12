
import logging
from unittest.mock import patch, Mock

from django.test import TestCase, tag, override_settings
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.urls import reverse

from rest_framework import status
from rest_framework.exceptions import ValidationError

from celery.exceptions import Retry

from core.models import ChrisFolder
from core.storage import connect_storage
from pacsfiles.models import PACS, PACSSeries, PACSFile
from pacsfiles.tasks import register_pacs_series, delete_pacs_series


class DeletePacSSeriesTaskTests(TestCase):
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_not_pending_does_not_call_delete(self):
        mock_series = Mock()
        mock_series.is_pending_deletion.return_value = False
        mock_series.delete = Mock()

        with patch('pacsfiles.tasks.PACSSeries.objects.get', return_value=mock_series):
            result = delete_pacs_series.apply(args=(1,))
            # synchronous apply returns an EagerResult; .get() returns the task return value
            self.assertIsNone(result.get())
            mock_series.delete.assert_not_called()

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    )
    def test_exception_updates_status_and_retries(self):
        mock_series = Mock()
        mock_series.is_pending_deletion.return_value = True
        mock_series.delete.side_effect = Exception("delete failed")

        mock_filter_qs = Mock()

        with patch(
            "pacsfiles.tasks.PACSSeries.objects.get",
            return_value=mock_series
        ), patch(
            "pacsfiles.tasks.PACSSeries.objects.filter",
            return_value=mock_filter_qs
        ):

            with self.assertRaises(Retry) as context:
                delete_pacs_series.apply(args=(1,)).get()

            self.assertIsInstance(context.exception.exc, Exception)
            self.assertEqual(str(context.exception.exc), "delete failed")
            self.assertEqual(mock_series.delete.call_count, 1)
            self.assertEqual(mock_filter_qs.update.call_count, 1)

            # Inspect last update call
            _, kwargs = mock_filter_qs.update.call_args

            self.assertEqual(
                kwargs["deletion_status"],
                PACSSeries.DeletionStatus.FAILED
            )
            self.assertEqual(
                kwargs["deletion_error"],
                "delete failed"
            )


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
