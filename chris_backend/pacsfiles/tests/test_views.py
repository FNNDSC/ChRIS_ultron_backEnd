
import logging
import json
import io
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.urls import reverse

from rest_framework import status

from core.models import ChrisFolder
from core.storage import connect_storage
from pacsfiles.models import PACS, PACSSeries, PACSFile
from pacsfiles import views


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class PACSViewTests(TestCase):
    """
    Generic pacs series view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.content_type = 'application/vnd.collection+json'
        self.username = 'test'
        self.password = 'testpass'

        pacs_grp, _ = Group.objects.get_or_create(name='pacs_users')
        user = User.objects.create_user(username=self.username, password=self.password)
        user.groups.set([pacs_grp])

        # create a PACS file in the DB "already registered" to the server)
        self.storage_manager = connect_storage(settings)
        # upload file to storage
        self.path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        with io.StringIO("test file") as file1:
            self.storage_manager.upload_obj(self.path + '/file1.dcm', file1.read(),
                                          content_type='text/plain')

        self.pacs_name = 'MyPACS'
        folder_path = f'SERVICES/PACS/{self.pacs_name}'
        owner = User.objects.get(username=self.chris_username)
        (pacs_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                             owner=owner)
        pacs = PACS(folder=pacs_folder, identifier=self.pacs_name)
        pacs.save()

        (series_folder, _) = ChrisFolder.objects.get_or_create(path=self.path,
                                                                    owner=owner)

        PACSSeries.objects.get_or_create(PatientID='123456',
                             PatientName='crazy',
                             PatientSex='O',
                             StudyDate='2020-07-15',
                             StudyInstanceUID='1.1.3432.54.6545674765.765434',
                             StudyDescription='brain_crazy_study',
                             SeriesInstanceUID='2.4.3432.54.845674765.763345',
                             SeriesDescription='SAG T1 MPRAGE',
                             pacs=pacs,
                             folder=series_folder)

        pacs_file = PACSFile(owner=owner, parent_folder=series_folder)
        pacs_file.fname.name = self.path + '/file1.dcm'
        pacs_file.save()

    def tearDown(self):
        # delete file from storage
        self.storage_manager.delete_obj(self.path + '/file1.dcm')
        # re-enable logging
        logging.disable(logging.NOTSET)


class PACSSeriesListViewTests(PACSViewTests):
    """
    Test the pacsseries-list view.
    """

    def setUp(self):
        super(PACSSeriesListViewTests, self).setUp()
        self.create_read_url = reverse("pacsseries-list")

    def test_pacs_series_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, 'brain_crazy_study')

    def test_pacs_series_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSSeriesDetailViewTests(PACSViewTests):
    """
    Test the pacsfile-detail view.
    """

    def setUp(self):
        super(PACSSeriesDetailViewTests, self).setUp()
        pacs_file = PACSFile.objects.get(fname=self.path + '/file1.dcm')
        self.read_url = reverse("pacsfile-detail",
                                kwargs={"pk": pacs_file.id})

    def test_pacs_series_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.path)

    def test_pacs_series_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSFileListViewTests(PACSViewTests):
    """
    Test the pacsfile-list view.
    """

    def setUp(self):
        super(PACSFileListViewTests, self).setUp()
        self.read_url = reverse("pacsfile-list")

    def tearDown(self):
        super(PACSFileListViewTests, self).tearDown()

    def test_pacsfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.path)

    def test_pacsfile_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSFileDetailViewTests(PACSViewTests):
    """
    Test the pacsfile-detail view.
    """

    def setUp(self):
        super(PACSFileDetailViewTests, self).setUp()
        pacs_file = PACSFile.objects.get(fname=self.path + '/file1.dcm')
        self.read_url = reverse("pacsfile-detail",
                                kwargs={"pk": pacs_file.id})

    def test_pacsfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.path)

    def test_pacsfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PACSFileResourceViewTests(PACSViewTests):
    """
    Test the pacsfile-resource view.
    """

    def setUp(self):
        super(PACSFileResourceViewTests, self).setUp()
        pacs_file = PACSFile.objects.get(fname=self.path + '/file1.dcm')
        self.download_url = reverse("pacsfile-resource",
                                    kwargs={"pk": pacs_file.id}) + 'file1.dcm'

    def tearDown(self):
        super(PACSFileResourceViewTests, self).tearDown()

    def test_pacsfileresource_get(self):
        pacs_file = PACSFile.objects.get(fname=self.path + '/file1.dcm')
        fileresource_view_inst = mock.Mock()
        fileresource_view_inst.get_object = mock.Mock(return_value=pacs_file)
        request_mock = mock.Mock()
        with mock.patch('pacsfiles.views.FileResponse') as response_mock:
            views.PACSFileResource.get(fileresource_view_inst, request_mock)
            response_mock.assert_called_with(pacs_file.fname)

    @tag('integration')
    def test_integration_pacsfileresource_download_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        content = [c for c in response.streaming_content][0].decode('utf-8')
        self.assertEqual(content, "test file")

    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
