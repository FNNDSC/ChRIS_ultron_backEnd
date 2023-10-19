
import logging
from unittest import mock, skip

from django.test import TestCase
from django.contrib.auth.models import User

from servicefiles.models import ServiceFile, Service
from pacsfiles.models import PACSFile
from userfiles.models import UserFile
from plugininstances.models import PluginInstanceFile
from pipelines.models import PipelineSourceFile
from filebrowser import services


class ServiceTests(TestCase):
    """
    Test top-level functions in the services module
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.username = 'testfoo'
        self.password = 'testfoopass'

        # create a user
        User.objects.create_user(username=self.username, password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)

    def test_get_path_file_model_class(self):
        """
        Test whether services.get_path_file_model_class function gets the correct file
        model class associated to a path.
        """
        username = self.username

        path = 'PIPELINES'
        model_class = services.get_path_file_model_class(path)
        self.assertEqual(model_class, PipelineSourceFile)

        path = 'SERVICES/PACS'
        model_class = services.get_path_file_model_class(path)
        self.assertEqual(model_class, PACSFile)

        path = 'SERVICES'
        model_class = services.get_path_file_model_class(path)
        self.assertEqual(model_class, ServiceFile)

        path = f'home/{username}/uploads'
        model_class = services.get_path_file_model_class(path)
        self.assertEqual(model_class, UserFile)

        path = f'home/{username}/feeds'
        model_class = services.get_path_file_model_class(path)
        self.assertEqual(model_class, PluginInstanceFile)

        path = 'SOR'
        model_class = services.get_path_file_model_class(path)
        self.assertIs(model_class, UserFile)

    def test_get_path_file_queryset(self):
        """
        Test whether services.get_path_file_queryset function correctly returns the
        queryset associated to a path or Raises ValueError if the path is not found.
        """
        username = self.username
        user = User.objects.get(username=self.username)
        path = 'SOR'
        with self.assertRaises(ValueError):
            services.get_path_file_queryset(path, user)

        path = f'home/{username}/crazypath1234567890'
        with self.assertRaises(ValueError):
            services.get_path_file_queryset(path, user)

        path = f'home/{username}'
        qs = services.get_path_file_queryset(path, user)
        self.assertTrue(qs.count() >= 0)

    def test_get_path_folders(self):
        """
        Test whether services.get_path_folders function correctly returns a path's
        list of folders.
        """
        username = self.username
        user = User.objects.get(username=self.username)

        path = f'home/{username}'
        folders = services.get_path_folders(path, user)
        self.assertIn('feeds', folders)

        path = 'SERVICES'
        # create a service's files in the DB
        service = Service(identifier='lolo')
        service.save()
        f1 = ServiceFile(service=service)
        f1.fname.name = 'SERVICES/lolo/lele/a.txt'
        f1.save()
        f2 = ServiceFile(service=service)
        f2.fname.name = 'SERVICES/lolo/b.txt'
        f2.save()
        f3 = ServiceFile(service=service)
        f3.fname.name = 'SERVICES/lili/c.txt'
        f3.save()
        folders = services.get_path_folders(path, user)
        self.assertEqual(sorted(folders), ['PACS', 'lili', 'lolo'])
