
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User
from uploadedfiles.models import UploadedFile, uploaded_file_path


class UploadedFileModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_uploaded_file_path(self):
        uploadedfile_instance = mock.Mock()
        uploadedfile_instance.owner = mock.Mock(spec=User)
        uploadedfile_instance.owner.username = 'foo'
        uploadedfile_instance.owner.upload_path = 'foo/uploads/myuploads'
        filename = 'file1.txt'
        file_path = uploaded_file_path(uploadedfile_instance, filename)
        self.assertEqual(file_path, 'foo/uploads/myuploads')

    def test_str(self):
        uploadedfile_mock = mock.MagicMock(spec=UploadedFile)
        uploadedfile_mock.fname.name = 'foo/uploads/myuploads'
        self.assertEqual(UploadedFile.__str__(uploadedfile_mock), 'foo/uploads/myuploads')