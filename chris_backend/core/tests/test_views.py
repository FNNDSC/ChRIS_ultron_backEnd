
import logging
import warnings

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from rest_framework import status

import jwt
from jwt.warnings import InsecureKeyLengthWarning

from core.models import FileDownloadToken
from core.utils import download_token_signing_key
from core.views import authenticate_token


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class CoreViewTests(TestCase):
    """
    Generic user view tests' setup and tearDown
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.content_type = 'application/vnd.collection+json'
        self.username = 'cube'
        self.password = 'cubepass'
        self.email = 'dev@babymri.org'

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FileDownloadTokenListViewTests(CoreViewTests):
    """
    Test the filedownloadtoken-list view.
    """

    def setUp(self):
        super(FileDownloadTokenListViewTests, self).setUp()
        self.user = User.objects.create_user(username=self.username,
                                             email=self.email,
                                             password=self.password)
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': self.user.username, 'exp': dt},
                           download_token_signing_key(), algorithm='HS512')
        (self.token, tf) = FileDownloadToken.objects.get_or_create(token=token,
                                                                   owner=self.user)
        self.create_read_url = reverse("filedownloadtoken-list")

    def test_integration_file_download_token_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_file_download_token_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_download_token_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "token")

    def test_file_download_token_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_download_token_create_signs_with_the_derived_key(self):
        """
        The token minted by the view must verify, so that the encode site in
        FileDownloadTokenList.perform_create and the decode site in authenticate_token
        are asserted to agree on the key rather than merely to run.
        """
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(authenticate_token(response.data['token']), self.user)

    def test_file_download_token_create_emits_no_key_length_warning(self):
        """
        PyJWT >= 2.11 warns when an HS512 key is shorter than 64 bytes. Signing with
        SECRET_KEY directly would put that warning in the production logs.
        """
        self.client.login(username=self.username, password=self.password)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            self.client.post(self.create_read_url)
        self.assertEqual(
            [w for w in caught if issubclass(w.category, InsecureKeyLengthWarning)], [])

    def test_file_download_token_signing_key_long_enough_for_hs512(self):
        """
        RFC 7518 Section 3.2 wants an HMAC key at least as long as the hash output.
        SECRET_KEY itself is 50 characters, which is why it is not used directly.
        """
        self.assertEqual(len(download_token_signing_key()), 64)

    def test_file_download_token_signing_key_is_not_the_secret_key(self):
        self.assertNotEqual(download_token_signing_key(),
                            settings.SECRET_KEY.encode())


class FileDownloadTokenDetailViewTests(CoreViewTests):
    """
    Test the filedownloadtoken-detail view
    """

    def setUp(self):
        super(FileDownloadTokenDetailViewTests, self).setUp()
        user = User.objects.create_user(username=self.username,
                                        email=self.email,
                                        password=self.password)
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': user.username, 'exp': dt},
                           download_token_signing_key(), algorithm='HS512')
        (self.token, tf) = FileDownloadToken.objects.get_or_create(token=token,
                                                                   owner=user)
        self.read_url = reverse("filedownloadtoken-detail",
                                kwargs={"pk": self.token.id})

    def test_file_download_token_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'token')
        self.assertContains(response, self.token)

    def test_file_download_token_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_file_download_token_detail_failure_access_denied(self):
        User.objects.create_user(username='boo', email='boo@gmail.com',
                                 password='boopass')
        self.client.login(username='boo', password='boopass')
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
