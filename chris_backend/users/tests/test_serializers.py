
import logging

from django.test import TestCase
from django.conf import settings
from rest_framework import serializers

from userfiles.models import UserFile
from users.serializers import UserSerializer, GroupSerializer, GroupUserSerializer
from core.storage.helpers import mock_storage


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class SerializerTests(TestCase):
    """
    Generic serializers tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class UserSerializerTests(SerializerTests):
    """
    User serializer tests.
    """

    def test_create(self):
        """
        Test whether overriden create method takes care of the password hashing.
        """
        user_serializer = UserSerializer()
        validated_data = {'username': self.username, 'password': self.password,
                          'email': self.email}
        with mock_storage('users.models.settings') as storage_manager:
            user = user_serializer.create(validated_data)

            self.assertEqual(user.username, self.username)
            self.assertEqual(user.email, self.email)
            self.assertNotEqual(user.password, self.password)
            self.assertTrue(user.check_password(self.password))

    def test_validate_username(self):
        """
        Test whether overriden validate_username method raises a
        serializers.ValidationError when the username contains forward slashes.
        """
        user_serializer = UserSerializer()

        with self.assertRaises(serializers.ValidationError):
            user_serializer.validate_username('user/')

        username = user_serializer.validate_username(self.username)
        self.assertEqual(username, self.username)


class GroupSerializerTests(SerializerTests):
    """
    Group serializer tests.
    """

    def test_validate_name(self):
        """
        Test whether overriden validate_name method raises a
        serializers.ValidationError when the group name contains forward slashes.
        """
        group_serializer = GroupSerializer()

        with self.assertRaises(serializers.ValidationError):
            group_serializer.validate_name('user/')

        group_name = group_serializer.validate_name('students')
        self.assertEqual(group_name, 'students')


class GroupUserSerializerTests(SerializerTests):
    """
    Group user serializer tests.
    """

    def test_validate_name(self):
        """
        Test whether overriden validate_username method raises a
        serializers.ValidationError when the passed username doesn't exist in the DB.
        """
        group_user_serializer = GroupUserSerializer()

        with self.assertRaises(serializers.ValidationError):
            group_user_serializer.validate_username('foo')

        user = group_user_serializer.validate_username(self.chris_username)
        self.assertEqual(user.username, self.chris_username)
