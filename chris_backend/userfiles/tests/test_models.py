
import logging
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User
from userfiles.models import UserFile


class UserFileModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_str(self):
        userfile_mock = mock.MagicMock(spec=UserFile)
        userfile_mock.fname.name = 'home/foo/uploads/myuploads'
        self.assertEqual(UserFile.__str__(userfile_mock), 'home/foo/uploads/myuploads')
