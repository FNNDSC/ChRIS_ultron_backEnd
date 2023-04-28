
import logging


from unittest import mock

from django.test import TestCase

from rest_framework import serializers

from uploadedfiles.models import UploadedFile
from users.serializers import UserSerializer, SwiftManager


class UserSerializerTests(TestCase):
    """
    Generic user view tests' setup and tearDown
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_create(self):
        """
        Test whether overriden create method takes care of the password hashing and
        creates a welcome file for the user in its personal storage space.
        """
        user_serializer = UserSerializer()
        validated_data = {'username': self.username, 'password': self.password,
                          'email': self.email}
        with mock.patch.object(SwiftManager, 'upload_obj',
                               return_value=None) as upload_obj_mock:

            user = user_serializer.create(validated_data)

            self.assertEqual(user.username, self.username)
            self.assertEqual(user.email, self.email)
            self.assertNotEqual(user.password, self.password)
            self.assertTrue(user.check_password(self.password))

            welcome_file_path = '%s/uploads/welcome.txt' % self.username
            welcome_file = UploadedFile.objects.get(owner=user)
            self.assertEqual(welcome_file.fname.name, welcome_file_path)
            upload_obj_mock.assert_called_with(welcome_file_path, mock.ANY,
                                               content_type='text/plain')

    def test_validate_username(self):
        """
        Test whether overriden validate_username method raises a
        serializers.ValidationError when the username contains forward slashes or it is
        'chris' or 'SERVICES' or 'PIPELINES' special identifiers.
        """
        user_serializer = UserSerializer()
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('user/')
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('chris')
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('SERVICES')
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('PIPELINES')
        username = user_serializer.validate_username(self.username)
        self.assertEqual(username, self.username)
