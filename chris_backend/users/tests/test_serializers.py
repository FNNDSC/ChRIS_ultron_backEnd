
import logging

from django.test import TestCase

from rest_framework import serializers

from userfiles.models import UserFile
from users.serializers import UserSerializer
from core.storage.helpers import mock_storage


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
        with mock_storage('users.serializers.settings') as storage_manager:
            user = user_serializer.create(validated_data)

            self.assertEqual(user.username, self.username)
            self.assertEqual(user.email, self.email)
            self.assertNotEqual(user.password, self.password)
            self.assertTrue(user.check_password(self.password))

            welcome_file_path = 'home/%s/welcome.txt' % self.username
            welcome_file = UserFile.objects.get(owner=user)
            self.assertEqual(welcome_file.fname.name, welcome_file_path)
            self.assertTrue(storage_manager.obj_exists(welcome_file_path))

    def test_validate_username(self):
        """
        Test whether overriden validate_username method raises a
        serializers.ValidationError when the username contains forward slashes or is
        the 'chris' special user.
        """
        user_serializer = UserSerializer()
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('user/')
        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('chris')
        username = user_serializer.validate_username(self.username)
        self.assertEqual(username, self.username)
