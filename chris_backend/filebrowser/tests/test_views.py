
import logging
import io
import os
from unittest import mock

from django.test import TestCase, tag
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse

from rest_framework import status

from core.models import ChrisFolder, ChrisLinkFile
from core.storage import connect_storage
from userfiles.models import UserFile
from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class FileBrowserViewTests(TestCase):
    """
    Generic filebrowser view tests' setup and tearDown.
    """

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        chris_user = User.objects.create_user(username=self.chris_username,
                                              password=self.chris_password)

        self.content_type = 'application/vnd.collection+json'
        self.username = 'foo'
        self.password = 'foopass'
        self.other_username = 'boo'
        self.other_password = 'boopass'

        # create folders
        ChrisFolder.objects.get_or_create(path='SERVICES/PACS', owner=chris_user)
        ChrisFolder.objects.get_or_create(path=f'PIPELINES/{self.username}', owner=chris_user)

        # create users
        user = User.objects.create_user(username=self.username, password=self.password)
        User.objects.create_user(username=self.other_username, password=self.other_password)

        # create a file in the DB "already uploaded" to the server)
        upload_path = f'home/{self.username}/uploads/myfolder/file1.txt'

        folder_path = os.path.dirname(upload_path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=user)
        userfile = UserFile(owner=user, parent_folder=file_parent_folder)
        userfile.fname.name = upload_path
        userfile.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FileBrowserFolderListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderListViewTests, self).setUp()
        self.read_url = reverse('chrisfolder-list')

    def test_filebrowserfolder_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'path')
        #import pdb; pdb.set_trace()
        self.assertEqual(response.data['results'][0]['path'],'')

    def test_filebrowserfolder_list_success_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertContains(response, 'path')
        self.assertEqual(response.data['results'][0]['path'],'')


class FileBrowserFolderListQuerySearchViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-list-query-search' view.
    """

    def setUp(self):
        super(FileBrowserFolderListQuerySearchViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin

    def test_filebrowserfolder_list_query_search_home_folder_success(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=home'
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'home')

    def test_filebrowserfolder_list_query_search_home_folder_success_unauthenticated(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=home'
        response = self.client.get(read_url)
        self.assertContains(response, 'home')

    def test_filebrowserfolder_list_query_search_user_home_folder_success(self):
        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.username}'
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.username}')

    def test_filebrowserfolder_list_query_search_user_home_folder_failure_unauthenticated(self):
        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.username}'
        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

    def test_filebrowserfolder_list_query_search_SERVICES_folder_success(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=SERVICES'
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'SERVICES')

    def test_filebrowserfolder_list_query_search_SERVICES_folder_failure_unauthenticated(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=SERVICES'
        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

    def test_filebrowserfolder_list_query_search_PIPELINES_folder_success(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=PIPELINES'
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'PIPELINES')

    def test_filebrowserfolder_list_query_search_PIPELINES_folder_succes_unauthenticated(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=PIPELINES'
        response = self.client.get(read_url)
        self.assertContains(response, 'PIPELINES')

    def test_filebrowserfolder_list_query_search_feeds_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds'
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.other_username}/feeds')

    def test_filebrowserfolder_list_query_search_feeds_folder_failure_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds'
        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

    def test_filebrowserfolder_list_query_search_feed_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds/feed_{pl_inst.feed.id}'

        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_list_query_search_feed_folder_failure_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds/feed_{pl_inst.feed.id}'

        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

    def test_filebrowserfolder_list_query_search_feed_folder_success_public_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        self.client.login(username=self.username, password=self.password)
        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds/feed_{pl_inst.feed.id}'

        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_list_query_search_feed_folder_success_public_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        read_url = reverse('chrisfolder-list-query-search') + f'?path=home/{self.other_username}/feeds/feed_{pl_inst.feed.id}'

        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_list_query_search_failure(self):
        self.client.login(username=self.username, password=self.password)
        read_url = reverse('chrisfolder-list-query-search') + '?path=LOLO'
        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

    def test_filebrowserfolder_list_query_search_failure_unauthenticated(self):
        read_url = reverse('chrisfolder-list-query-search') + '?path=LOLO'
        response = self.client.get(read_url)
        self.assertFalse(response.data['results'])

class FileBrowserFolderDetailViewTests(FileBrowserViewTests):
    """
    Test the chrisfolder-detail view.
    """

    def setUp(self):
        super(FileBrowserFolderDetailViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin

    def test_filebrowserfolder_home_folder_success(self):
        folder = ChrisFolder.objects.get(path='home')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'home')

    def test_filebrowserfolder_home_folder_success_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='home')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertContains(response, 'home')

    def test_filebrowserfolder_user_home_folder_success(self):
        folder = ChrisFolder.objects.get(path=f'home/{self.username}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.username}')

    def test_filebrowserfolder_user_home_folder_failure_not_found_unauthenticated(self):
        folder = ChrisFolder.objects.get(path=f'home/{self.username}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_SERVICES_folder_success(self):
        folder = ChrisFolder.objects.get(path='SERVICES')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'SERVICES')

    def test_filebrowserfolder_SERVICES_folder_failure_not_found_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='SERVICES')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_PIPELINES_folder_success(self):
        folder = ChrisFolder.objects.get(path='PIPELINES')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'PIPELINES')

    def test_filebrowserfolder_PIPELINES_folder_succes_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='PIPELINES')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertContains(response, 'PIPELINES')

    def test_filebrowserfolder_feeds_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(path=f'home/{self.other_username}/feeds')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertContains(response,f'home/{self.other_username}/feeds')

    def test_filebrowserfolder_feeds_folder_failure_not_found_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        folder = ChrisFolder.objects.get(path=f'home/{self.other_username}/feeds')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_feed_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_feed_folder_failure_not_found_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_feed_folder_success_public_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_feed_folder_success_public_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-detail", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolder_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        read_url = reverse("chrisfolder-detail", kwargs={"pk": 111111111})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolder_failure_not_found_unauthenticated(self):
        read_url = reverse("chrisfolder-detail", kwargs={"pk": 111111111})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileBrowserFolderChildListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-child-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderChildListViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin

    def test_filebrowserfolderchild_list_root_folder_success(self):
        folder = ChrisFolder.objects.get(path='')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'home')
        self.assertContains(response, 'SERVICES')
        self.assertContains(response, 'PIPELINES')
        self.assertEqual(len(response.data['results']), 3)

    def test_filebrowserfolderchild_list_root_folder_success_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertContains(response, 'home')
        self.assertContains(response, 'PIPELINES')
        self.assertEqual(len(response.data['results']), 2)

    def test_filebrowserfolderchild_list_home_folder_success(self):
        folder = ChrisFolder.objects.get(path='home')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.username}')
        self.assertEqual(len(response.data['results']), 1)

    def test_filebrowserfolderchild_list_home_folder_empty_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='home')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(len(response.data['results']), 0)

    def test_filebrowserfolderchild_list_user_home_folder_success(self):
        folder = ChrisFolder.objects.get(path=f'home/{self.username}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.username}')

    def test_filebrowserfolderchild_list_user_home_folder_failure_not_found_unauthenticated(self):
        folder = ChrisFolder.objects.get(path=f'home/{self.username}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderchild_list_SERVICES_folder_success(self):
        folder = ChrisFolder.objects.get(path='SERVICES')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, 'SERVICES/PACS')

    def test_filebrowserfolderchild_list_SERVICES_folder_failure_not_found_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='SERVICES')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderchild_list_PIPELINES_folder_success(self):
        folder = ChrisFolder.objects.get(path='PIPELINES')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, f'PIPELINES/{self.username}')

    def test_filebrowserfolderchild_list_PIPELINES_folder_succes_unauthenticated(self):
        folder = ChrisFolder.objects.get(path='PIPELINES')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_filebrowserfolderchild_list_feeds_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(path=f'home/{self.other_username}/feeds')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertContains(response, f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')

    def test_filebrowserfolderchild_list_feeds_folder_failure_not_found_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        folder = ChrisFolder.objects.get(path=f'home/{self.other_username}/feeds')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderchild_list_feed_folder_success_shared_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}/')

    def test_filebrowserfolderchild_list_feed_folder_failure_not_found_shared_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'shared_feed'
        pl_inst.feed.save()
        pl_inst.feed.owner.add(User.objects.get(username=self.username))

        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderchild_list_feed_folder_success_public_feed(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        self.client.login(username=self.username, password=self.password)
        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}/')

    def test_filebrowserfolderchild_list_feed_folder_success_public_feed_unauthenticated(self):
        other_user = User.objects.get(username=self.other_username)
        plugin = self.plugin

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=other_user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])
        pl_inst.feed.name = 'public_feed'
        pl_inst.feed.public = True
        pl_inst.feed.save()

        folder = ChrisFolder.objects.get(
            path=f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}')
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": folder.id})

        response = self.client.get(read_url)
        self.assertContains(response,
                            f'home/{self.other_username}/feeds/feed_{pl_inst.feed.id}/')

    def test_filebrowserfolderchild_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": 111111111})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderchild_list_failure_not_found_unauthenticated(self):
        read_url = reverse("chrisfolder-child-list", kwargs={"pk": 111111111})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FileBrowserFolderFileListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-file-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderFileListViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin

        # create a file in the DB "already uploaded" to the server)
        self.storage_manager = connect_storage(settings)
        # upload file to storage
        self.upload_path = f'home/{self.username}/uploads/file2.txt'
        with io.StringIO("test file") as file1:
            self.storage_manager.upload_obj(self.upload_path, file1.read(),
                                         content_type='text/plain')
        user = User.objects.get(username=self.username)

        folder_path = os.path.dirname(self.upload_path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=user)
        userfile = UserFile(owner=user, parent_folder=file_parent_folder)
        userfile.fname.name = self.upload_path
        userfile.save()

        self.read_url = reverse("chrisfolder-file-list", kwargs={"pk": file_parent_folder.id})

    def tearDown(self):
        # delete file from storage
        self.storage_manager.delete_obj(self.upload_path)

        super(FileBrowserFolderFileListViewTests, self).tearDown()

    def test_filebrowserfolderfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, self.upload_path)

    def test_filebrowserfolderfile_list_success_public_feed_unauthenticated(self):
        user = User.objects.get(username=self.username)

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=self.plugin, owner=user,
                                                title='test',
                                                compute_resource=
                                                self.plugin.compute_resources.all()[0])
        pl_inst.feed.public = True
        pl_inst.feed.save()

        # create file
        self.storage_manager = connect_storage(settings)

        file_path = f'{pl_inst.output_folder.path}/file3.txt'
        with io.StringIO("test file") as file3:
            self.storage_manager.upload_obj(file_path, file3.read(),
                                         content_type='text/plain')

        userfile = UserFile(owner=user, parent_folder=pl_inst.output_folder)
        userfile.fname.name = file_path
        userfile.save()

        read_url = reverse("chrisfolder-file-list",
                           kwargs={"pk": pl_inst.output_folder.id})

        response = self.client.get(read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, file_path)

        self.storage_manager.delete_obj(file_path)

    def test_filebrowserfolderfile_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderfile_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("chrisfolder-file-list", kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderfile_list_failure_not_found_unauthenticated(self):
        response = self.client.get(reverse("chrisfolder-file-list", kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderfile_list_file_folder_success(self):
        folder_path = os.path.dirname(self.upload_path)
        folder = ChrisFolder.objects.get(path=folder_path)
        read_url = reverse("chrisfolder-file-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, self.upload_path)

    def test_filebrowserfolderfile_list_file_folder_failure_not_found_unauthenticated(self):
        folder_path = os.path.dirname(self.upload_path)
        folder = ChrisFolder.objects.get(path=folder_path)
        read_url = reverse("chrisfolder-file-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class FileBrowserFolderLinkFileListViewTests(FileBrowserViewTests):
    """
    Test the 'chrisfolder-linkfile-list' view.
    """

    def setUp(self):
        super(FileBrowserFolderLinkFileListViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin

        # create link file
        self.link_path = f'home/{self.username}/feeds/feed_1/out/SERVICES_PACS.chrislink'
        user = User.objects.get(username=self.username)

        folder_path = os.path.dirname(self.link_path)
        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                               owner=user)
        link_file = ChrisLinkFile(path='SERVICES/PACS', owner=user,
                                  parent_folder=parent_folder)
        link_file.save(name='SERVICES_PACS')
        self.read_url = reverse("chrisfolder-linkfile-list",
                                kwargs={"pk": parent_folder.id})

    def tearDown(self):
        super(FileBrowserFolderLinkFileListViewTests, self).tearDown()
        self.storage_manager = connect_storage(settings)
        self.storage_manager.delete_obj(self.link_path)

    def test_filebrowserfolderlinkfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, self.link_path)

    def test_filebrowserfolderlinkfile_list_success_public_feed_unauthenticated(self):
        user = User.objects.get(username=self.username)

        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=self.plugin, owner=user,
                                                title='test',
                                                compute_resource=
                                                self.plugin.compute_resources.all()[0])
        pl_inst.feed.public = True
        pl_inst.feed.save()

        # create link file
        link_path = f'{pl_inst.output_folder.path}/SERVICES_PACS.chrislink'

        link_file = ChrisLinkFile(path='SERVICES/PACS', owner=user,
                                  parent_folder=pl_inst.output_folder)
        link_file.save(name='SERVICES_PACS')

        read_url = reverse("chrisfolder-linkfile-list",
                           kwargs={"pk": pl_inst.output_folder.id})
        response = self.client.get(read_url)
        self.assertContains(response, 'file_resource')
        self.assertContains(response, link_path)

    def test_filebrowserfolderlinkfile_list_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderlinkfile_list_failure_not_found(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("chrisfolder-linkfile-list",
                                           kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderlinkfile_list_failure_not_found_unauthenticated(self):
        response = self.client.get(reverse("chrisfolder-linkfile-list",
                                           kwargs={"pk": 111111111}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filebrowserfolderlinkfile_list_file_folder_success(self):
        folder_path = os.path.dirname(self.link_path)
        folder = ChrisFolder.objects.get(path=folder_path)
        read_url = reverse("chrisfolder-linkfile-list", kwargs={"pk": folder.id})
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(read_url)
        self.assertContains(response, self.link_path)

    def test_filebrowserfolderlinkfile_list_file_folder_failure_not_found_unauthenticated(self):
        folder_path = os.path.dirname(self.link_path)
        folder = ChrisFolder.objects.get(path=folder_path)
        read_url = reverse("chrisfolder-linkfile-list", kwargs={"pk": folder.id})
        response = self.client.get(read_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class FileBrowserLinkFileDetailViewTests(FileBrowserViewTests):
    """
    Test the chrislinkfile-detail view.
    """

    def setUp(self):
        super(FileBrowserLinkFileDetailViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin
        user = User.objects.get(username=self.username)

        # create a feed by creating a "fs" plugin instance
        self.pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])

        # create link file
        self.link_path = f'{self.pl_inst.output_folder.path}/SERVICES_PACS.chrislink'

        link_file = ChrisLinkFile(path='SERVICES/PACS', owner=user,
                                  parent_folder=self.pl_inst.output_folder)
        link_file.save(name='SERVICES_PACS')
        self.read_url = reverse("chrislinkfile-detail",
                                kwargs={"pk": link_file.id})

    def tearDown(self):
        super(FileBrowserLinkFileDetailViewTests, self).tearDown()
        self.storage_manager = connect_storage(settings)
        self.storage_manager.delete_obj(self.link_path)

    def test_fileBrowserlinkfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.link_path)

    def test_fileBrowserlinkfile_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_url)
        self.assertContains(response, self.link_path)

    def test_fileBrowserlinkfile_detail_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    def test_fileBrowserlinkfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fileBrowserlinkfile_detail_success_public_feed_unauthenticated(self):
        self.pl_inst.feed.public = True
        self.pl_inst.feed.save()
        response = self.client.get(self.read_url)
        self.assertContains(response, self.link_path)


class FileBrowserLinkFileResourceViewTests(FileBrowserViewTests):
    """
    Test the chrislinkfile-resource view.
    """

    def setUp(self):
        super(FileBrowserLinkFileResourceViewTests, self).setUp()

        # create compute resource
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create 'fs' plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([compute_resource])
        plugin.save()

        self.plugin = plugin
        user = User.objects.get(username=self.username)

        # create a feed by creating a "fs" plugin instance
        self.pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                title='test',
                                                compute_resource=
                                                plugin.compute_resources.all()[0])

        # create link file
        self.link_path = f'{self.pl_inst.output_folder.path}/SERVICES_PACS.chrislink'

        link_file = ChrisLinkFile(path='SERVICES/PACS', owner=user,
                                  parent_folder=self.pl_inst.output_folder)
        link_file.save(name='SERVICES_PACS')

        self.download_url = reverse("chrislinkfile-resource",
                                    kwargs={"pk": link_file.id}) + 'SERVICES_PACS.chrislink'

    def tearDown(self):
        super(FileBrowserLinkFileResourceViewTests, self).tearDown()
        self.storage_manager = connect_storage(settings)
        self.storage_manager.delete_obj(self.link_path)

    def test_fileBrowserlinkfile_resource_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        content = [c for c in response.streaming_content][0].decode('utf-8')
        self.assertEqual(content, 'SERVICES/PACS')

    def test_fileBrowserlinkfile_resource_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        content = [c for c in response.streaming_content][0].decode('utf-8')
        self.assertEqual(content, 'SERVICES/PACS')

    def test_fileBrowserlinkfile_resource_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    def test_fileBrowserlinkfile_resource_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fileBrowserlinkfile_resource_success_public_feed_unauthenticated(self):
        self.pl_inst.feed.public = True
        self.pl_inst.feed.save()
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200)
        content = [c for c in response.streaming_content][0].decode('utf-8')
        self.assertEqual(content, 'SERVICES/PACS')
