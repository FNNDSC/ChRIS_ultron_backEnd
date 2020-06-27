

import logging
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from rest_framework import serializers

from uploadedfiles.serializers import UploadedFileSerializer


class UploadedFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_validate_path_failure_does_not_start_with_username_uploads(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the '<username>/<uploads>/' string.
        """
        uploadedfiles_serializer = UploadedFileSerializer()
        user = mock.Mock(spec=User)
        user.username = 'cube'
        request = mock.Mock()
        request.user = user
        with mock.patch.dict(uploadedfiles_serializer.context,
                             {'request': request}, clear=True):
            with self.assertRaises(serializers.ValidationError):
                uploadedfiles_serializer.validate_upload_path('foo/file1.txt')
            with self.assertRaises(serializers.ValidationError):
                uploadedfiles_serializer.validate_upload_path('cube/file1.txt')
            with self.assertRaises(serializers.ValidationError):
                uploadedfiles_serializer.validate_upload_path('cube/uploads_file1.txt')

    @tag('integration')
    def test_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        uploadedfiles_serializer = UploadedFileSerializer()
        user = mock.Mock(spec=User)
        user.username = 'cube'
        request = mock.Mock()
        request.user = user
        with mock.patch.dict(uploadedfiles_serializer.context,
                             {'request': request}, clear=True):
            upload_path = 'cube/uploads/file1.txt'
            self.assertEqual(uploadedfiles_serializer.validate_upload_path(upload_path),
                             upload_path)

    def test_validate_updates_validated_data(self):
        """
        Test whether overriden validate method updates validated data with a PACS object.
        """
        data = {'upload_path': 'cube/uploads_file1.txt'}
        uploadedfiles_serializer = UploadedFileSerializer()
        user = mock.Mock(spec=User)
        user.username = 'cube'
        request = mock.Mock()
        request.user = user
        with mock.patch.dict(uploadedfiles_serializer.context,
                             {'request': request}, clear=True):
            new_data = uploadedfiles_serializer.validate(data)
            self.assertEqual(new_data['owner'].upload_path, 'cube/uploads_file1.txt')
