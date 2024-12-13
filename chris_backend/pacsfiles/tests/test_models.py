
import logging
import os
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from core.models import ChrisFolder
from core.utils import json_zip2str
from pacsfiles.models import PACS, PACSQuery, PACSRetrieve


CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ModelTests(TestCase):

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


class PACSQueryModelTests(ModelTests):

    def setUp(self):
        super(PACSQueryModelTests, self).setUp()

        # create a PACSQuery instance
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        self.query = {'SeriesInstanceUID': '2.3.15.2.1057'}

        pacs_query, _ = PACSQuery.objects.get_or_create(title='query1', query=self.query,
                                                        owner=user, pacs=pacs)

    def test_send_success(self):
        """
        Test whether overriden send method successfully completes a PACS query request
        to pfdcm service.
        """
        pacs_query = PACSQuery.objects.get(title='query1')

        with mock.patch('pacsfiles.models.PfdcmClient.query') as pfdcm_query_mock:
            result = {'mock': 'mock'}
            pfdcm_query_mock.return_value = result

            pacs_query.send()

            pfdcm_query_mock.assert_called_with(self.pacs_name, self.query)
            self.assertEqual(pacs_query.status, 'succeeded')

    def test_send_failure(self):
        """
        Test whether overriden send method fails to make a PACS query request
        to pfdcm service.
        """
        pacs_query = PACSQuery.objects.get(title='query1')

        with mock.patch('pacsfiles.models.PfdcmClient.query') as pfdcm_query_mock:
            pfdcm_query_mock.side_effect=Exception

            pacs_query.send()

            pfdcm_query_mock.assert_called_with(self.pacs_name, self.query)
            self.assertEqual(pacs_query.status, 'errored')


class PACSRetrieveModelTests(ModelTests):

    def setUp(self):
        super(PACSRetrieveModelTests, self).setUp()

        # create a PACSQuery instance
        user = User.objects.get(username=self.username)
        pacs = PACS.objects.get(identifier=self.pacs_name)
        self.query = {'SeriesInstanceUID': '2.3.15.2.1057'}

        pacs_query, _ = PACSQuery.objects.get_or_create(title='query1', query=self.query,
                                                        owner=user, pacs=pacs)

        self.pacs_retrieve, _ = PACSRetrieve.objects.get_or_create(pacs_query=pacs_query,
                                                              owner=user)

    def test_send_success(self):
        """
        Test whether overriden send method successfully sends a PACS retrieve request
        to pfdcm service.
        """
        pacs_retrieve = self.pacs_retrieve

        with mock.patch('pacsfiles.models.PfdcmClient.retrieve') as pfdcm_retrieve_mock:
            result = {'mock': 'mock'}
            pfdcm_retrieve_mock.return_value = result

            pacs_retrieve.send()

            pfdcm_retrieve_mock.assert_called_with(self.pacs_name, self.query)
            self.assertEqual(pacs_retrieve.status, 'sent')

    def test_send_failure(self):
        """
        Test whether overriden send method fails to make a PACS retrieve request
        to pfdcm service.
        """
        pacs_retrieve = self.pacs_retrieve

        with mock.patch('pacsfiles.models.PfdcmClient.retrieve') as pfdcm_retrieve_mock:
            pfdcm_retrieve_mock.side_effect = Exception

            pacs_retrieve.send()

            pfdcm_retrieve_mock.assert_called_with(self.pacs_name, self.query)
            self.assertEqual(pacs_retrieve.status, 'errored')
