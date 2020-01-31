
import logging

from django.test import TestCase

from rest_framework import serializers

from users.serializers import UserSerializer


class UserSerializerTests(TestCase):
    """
    Generic user view tests' setup and tearDown
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)

    def test_create(self):
        """
        Test whether overriden create method takes care of the password hashing.
        """
        user_serializer = UserSerializer()
        validated_data = {'username': self.username, 'password': self.password,
                          'email': self.email}
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
