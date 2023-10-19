

import logging
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from rest_framework import serializers

from userfiles.serializers import UserFileSerializer


class UserFileSerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_validate_path_failure_does_not_start_with_username_uploads(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the 'home/<username>/' string.
        """
        userfiles_serializer = UserFileSerializer()
        user = mock.Mock(spec=User)
        user.username = 'cube'
        request = mock.Mock()
        request.user = user
        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('foo/file1.txt')
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('home/cube_file1.txt')
            with self.assertRaises(serializers.ValidationError):
                userfiles_serializer.validate_upload_path('cube/uploads_file1.txt')

    @tag('integration')
    def test_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        userfiles_serializer = UserFileSerializer()
        user = mock.Mock(spec=User)
        user.username = 'cube'
        request = mock.Mock()
        request.user = user
        with mock.patch.dict(userfiles_serializer.context,
                             {'request': request}, clear=True):
            upload_path = 'home/cube/uploads/file1.txt'
            self.assertEqual(userfiles_serializer.validate_upload_path(upload_path),
                             upload_path)
