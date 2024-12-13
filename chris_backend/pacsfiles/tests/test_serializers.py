
import logging

from django.contrib.auth.models import User
from django.test import TestCase, tag
from django.conf import settings
from unittest import mock
from rest_framework import serializers

from core.models import ChrisFolder
from pacsfiles.models import PACS, PACSQuery
from pacsfiles.serializers import (PACSQuerySerializer, PACSRetrieveSerializer,
                                   PACSSeriesSerializer)


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class SerializerTests(TestCase):
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # superuser chris (owner of root folders)
        self.chris_username = 'chris'
        chris_user = User.objects.get(username=self.chris_username)

        # create normal user
        self.username = 'foo'
        self.password = 'bar'
        User.objects.create_user(username=self.username, password=self.password)

        # create a PACS
        self.pacs_name = 'myPACS'
        folder_path = f'SERVICES/PACS/{self.pacs_name}'
        (pacs_folder, tf) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                              owner=chris_user)
        PACS.objects.get_or_create(folder=pacs_folder, identifier=self.pacs_name)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PACSQuerySerializerTests(SerializerTests):

    def test_create_success(self):
        """
        Test whether overriden 'create' method successfully creates a new PACS query.
        """
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        query = {'SeriesInstanceUID': '2.3.15.2.1057'}
        data = {'title': 'query1', 'query': query, 'owner': user, 'pacs': pacs}

        pacs_query_serializer = PACSQuerySerializer(data=data)
        pacs_query = pacs_query_serializer.create(data)
        self.assertEqual(pacs_query.status, 'created')


    def test_create_failure_pacs_user_title_combination_already_exists(self):
        """
        Test whether overriden 'create' method raises a ValidationError when a user has
        already registered a PACS query with the same title and pacs.
        """
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        query = {'SeriesInstanceUID': '1.3.12.2.1107'}
        data = {'title': 'query2', 'query': query, 'owner': user, 'pacs': pacs}

        PACSQuery.objects.get_or_create(title='query2', query=query, owner=user, pacs=pacs)

        pacs_query_serializer = PACSQuerySerializer(data=data)
        with self.assertRaises(serializers.ValidationError):
            pacs_query_serializer.create(data)

    def test_update_success(self):
        """
        Test whether overriden 'update' method successfully updates an existing PACS query.
        """
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        query = {'SeriesInstanceUID': '2.3.15.2.1057'}

        pacs_query, _ = PACSQuery.objects.get_or_create(title='query2', query=query,
                                                        owner=user, pacs=pacs)

        data = {'title': 'query4'}
        pacs_query_serializer = PACSQuerySerializer(pacs_query, data)
        pacs_query = pacs_query_serializer.update(pacs_query, data)
        self.assertEqual(pacs_query.title, 'query4')

    def test_update_failure_pacs_user_title_combination_already_exists(self):
        """
        Test whether overriden 'update' method raises a ValidationError when a user has
        already registered a PACS query with the same title and pacs.
        """
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        query = {'SeriesInstanceUID': '1.3.12.2.1107'}

        pacs_query, _ = PACSQuery.objects.get_or_create(title='query2', query=query,
                                                        owner=user, pacs=pacs)
        PACSQuery.objects.get_or_create(title='query3', query=query, owner=user, pacs=pacs)

        data = {'title': 'query3'}
        pacs_query_serializer = PACSQuerySerializer(pacs_query, data)
        with self.assertRaises(serializers.ValidationError):
            pacs_query_serializer.update(pacs_query, data)


class PACSSeriesSerializerTests(SerializerTests):

    def test_validate_ndicom_failure_not_positive(self):
        """
        Test whether overriden validate_ndicom method validates submitted ndicom must
        be a positive integer.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_ndicom(0)

    def test_validate_ndicom_success(self):
        """
        Test whether overriden validate_ndicom method properly validates submitted ndicom.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        self.assertEqual(pacs_series_serializer.validate_ndicom(1), 1)

    def test_validate_path_failure_does_not_start_with_SERVICES_PACS(self):
        """
        Test whether overriden validate_path method validates submitted path must start
        with the 'SERVICES/PACS/' string.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        path = 'cube/123456-Jorge/brain/brain_mri'
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_path(path)
        path = 'SERVICES/123456-Jorge/brain/brain_mri'
        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer.validate_path(path)


    def test_validate_path_success(self):
        """
        Test whether overriden validate_path method validates submitted path.
        """
        pacs_series_serializer = PACSSeriesSerializer()
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        self.assertEqual(pacs_series_serializer.validate_path(path), path)

    def test_validate_failure_path_does_not_start_with_SERVICES_PACS_pacs_name(self):
        """
        Test whether overriden validate method validates that submitted path must start
        with the 'SERVICES/PACS/pacs_name' string.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS1', 'path': path, 'ndicom': 1}

        with self.assertRaises(serializers.ValidationError):
            pacs_series_serializer = PACSSeriesSerializer()
            pacs_series_serializer.validate(data)

    def test_validate_failure_ndicom_in_storage_different_from_request_data(self):
        """
        Test whether overriden validate method validates that submitted path must start
        with the 'SERVICES/PACS/pacs_name' string.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path, 'ndicom': 2}


        storage_manager_mock = mock.Mock()
        storage_manager_mock.ls = mock.Mock(return_value=['file1'])

        with mock.patch('pacsfiles.serializers.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value = storage_manager_mock

            with self.assertRaises(serializers.ValidationError):
                pacs_series_serializer = PACSSeriesSerializer()
                pacs_series_serializer.validate(data)

    def test_validate_success(self):
        """
        Test whether overriden validate method correctly validates data.
        """
        path = 'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE'
        data = {'PatientID': '123456', 'PatientName': 'crazy',
                'StudyDate': '2020-07-15',
                'StudyInstanceUID': '1.1.3432.54.6545674765.765434',
                'StudyDescription': 'brain_crazy_study',
                'SeriesDescription': 'SAG T1 MPRAGE',
                'SeriesInstanceUID': '2.4.3432.54.845674765.763345',
                'pacs_name': 'MyPACS', 'path': path, 'ndicom': 1}


        storage_manager_mock = mock.Mock()
        storage_manager_mock.ls = mock.Mock(return_value=[
            'SERVICES/PACS/MyPACS/123456-crazy/brain_crazy_study/SAG_T1_MPRAGE/file1.dcm'])

        with mock.patch('pacsfiles.serializers.connect_storage') as connect_storage_mock:
            connect_storage_mock.return_value = storage_manager_mock
            pacs_series_serializer = PACSSeriesSerializer()
            pacs_series_serializer.validate(data)
            storage_manager_mock.ls.assert_called_with(path)
