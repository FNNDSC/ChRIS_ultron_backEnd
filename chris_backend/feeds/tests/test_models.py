
import logging
import io

from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.conf import settings

from core.models import (ChrisFolder, ChrisLinkFile)
from core.storage import connect_storage
from plugins.models import PluginMeta, Plugin, PluginParameter, ComputeResource
from plugininstances.models import PluginInstance
from userfiles.models import UserFile
from feeds.models import Note, Feed, FeedGroupPermission, FeedUserPermission


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.feed_name = "Feed1"
        self.plugin_name = "pacspull"
        self.plugin_type = "fs"
        self.plugin_parameters = {'mrn': {'type': 'string', 'optional': False},
                                  'img_type': {'type': 'string', 'optional': True}}
        self.username = 'foo'
        self.password = 'bar'
        self.other_username = 'boo'
        self.other_password = 'far'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create a "fs" plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_name,
                                                         type=self.plugin_type)
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        # add plugin parameter
        PluginParameter.objects.get_or_create(
            plugin=plugin,
            name='mrn',
            type=self.plugin_parameters['mrn']['type'],
            optional=self.plugin_parameters['mrn']['optional'])

        # create users
        other_user = User.objects.create_user(username=self.other_username,
                                              password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

        # assign predefined group
        all_grp = Group.objects.get(name='all_users')

        other_user.groups.set([all_grp])
        user.groups.set([all_grp])

        # create a plugin instance that in turn creates a new feed
        (plg_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        plg_inst.feed.name = self.feed_name
        plg_inst.feed.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FeedModelTests(ModelTests):

    def test_save_creates_new_note_just_after_feed_is_created(self):
        """
        Test whether overriden save method creates a note just after a feed is created.
        """
        self.assertEqual(Note.objects.count(), 1)

    def test_add_jobs_status_count(self):
        """
        Test whether custom add_jobs_status_count method properly adds the number of
        associated plugin instances per execution status to each element of a Feed
        queryset.
        """
        feed = Feed.add_jobs_status_count(Feed.objects.all()).get(name=self.feed_name)
        count = feed.created_jobs
        self.assertEqual(count, 1)
        count = feed.waiting_jobs
        self.assertEqual(count, 0)
        count = feed.scheduled_jobs
        self.assertEqual(count, 0)
        count = feed.started_jobs
        self.assertEqual(count, 0)
        count = feed.registering_jobs
        self.assertEqual(count, 0)
        count = feed.finished_jobs
        self.assertEqual(count, 0)
        count = feed.errored_jobs
        self.assertEqual(count, 0)
        count = feed.cancelled_jobs
        self.assertEqual(count, 0)

    def test_get_jobs_status_count(self):
        """
        Test whether custom get_jobs_status_count method properly returns
        the number of plugin instances per execution status.
        """
        feed = Feed.objects.get(name=self.feed_name)
        count = feed.get_jobs_status_count()['created_jobs']
        self.assertEqual(count, 1)
        count = feed.get_jobs_status_count()['waiting_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['scheduled_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['started_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['registering_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['finished_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['errored_jobs']
        self.assertEqual(count, 0)
        count = feed.get_jobs_status_count()['cancelled_jobs']
        self.assertEqual(count, 0)


class FeedGroupPermissionTests(ModelTests):

    def test_save(self):
        """
        Test whether overriden save method grants the group write permission to all the
        folders, files and link files within the feed's folder. In addition, tests
        whether the same permission is applied to all objects pointed by the linked
        files under the feed's folder if they are owned by the feed's owner.
        """
        user = User.objects.get(username=self.username)
        grp = Group.objects.get(name='all_users')
        feed = Feed.objects.get(name=self.feed_name)
        folder = feed.folder.children.first()

        # create a file within the folder
        storage_manager = connect_storage(settings)
        file_path = f'{folder.path}/file.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        f = UserFile(owner=user, parent_folder=folder)
        f.fname.name = file_path
        f.save()

        # create a link file within the folder
        lf = ChrisLinkFile(path=f'home/{self.username}/uploads', owner=user,
                           parent_folder=folder)
        lf.save(name=f'home_{self.username}_uploads')

        # create a file within the pointed folder
        pointed_folder, tf = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)
        file_path = f'{pointed_folder.path}/file1.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        pf = UserFile(owner=user, parent_folder=pointed_folder)
        pf.fname.name = file_path
        pf.save()

        perm = FeedGroupPermission(feed=feed, group=grp)
        perm.save()

        grps = folder.shared_groups.values_list('name', flat=True)
        self.assertIn('all_users', grps)

        grps = f.shared_groups.values_list('name', flat=True)
        self.assertIn('all_users', grps)

        grps = lf.shared_groups.values_list('name', flat=True)
        self.assertIn('all_users', grps)

        grps = pf.shared_groups.values_list('name', flat=True)
        self.assertIn('all_users', grps)

        ChrisFolder.objects.get(path=f'home/{self.username}').delete()

    def test_delete(self):
        """
        Test whether overriden delete method removes the group's write permission from all
        the folders, files and link files within the feed's folder. In addition, tests
        whether the same permission is removed from all objects pointed by the linked
        files under the feed's folder if they are owned by the feed's owner.
        """
        user = User.objects.get(username=self.username)
        grp = Group.objects.get(name='all_users')
        feed = Feed.objects.get(name=self.feed_name)
        folder = feed.folder.children.first()

        # create a file within the folder
        storage_manager = connect_storage(settings)
        file_path = f'{folder.path}/file.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        f = UserFile(owner=user, parent_folder=folder)
        f.fname.name = file_path
        f.save()

        # create a link file within the folder
        lf = ChrisLinkFile(path=f'home/{self.username}/uploads', owner=user,
                           parent_folder=folder)
        lf.save(name=f'home_{self.username}_uploads')

        # create a file within the pointed folder
        pointed_folder, tf = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)
        file_path = f'{pointed_folder.path}/file1.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        pf = UserFile(owner=user, parent_folder=pointed_folder)
        pf.fname.name = file_path
        pf.save()

        perm = FeedGroupPermission(feed=feed, group=grp)
        perm.save()
        perm.delete()

        grps = folder.shared_groups.values_list('name', flat=True)
        self.assertNotIn('all_users', grps)

        grps = f.shared_groups.values_list('name', flat=True)
        self.assertNotIn('all_users', grps)

        grps = lf.shared_groups.values_list('name', flat=True)
        self.assertNotIn('all_users', grps)

        grps = pf.shared_groups.values_list('name', flat=True)
        self.assertNotIn('all_users', grps)

        ChrisFolder.objects.get(path=f'home/{self.username}').delete()


class FeedUserPermissionTests(ModelTests):

    def test_save(self):
        """
        Test whether overriden save method grants the user write permission to all the
        folders, files and link files within the feed's folder. In addition, tests
        whether the same permission is applied to all objects pointed by the linked
        files under the feed's folder if they are owned by the feed's owner.
        """
        user = User.objects.get(username=self.username)
        other_user = User.objects.get(username=self.other_username)
        feed = Feed.objects.get(name=self.feed_name)
        folder = feed.folder.children.first()

        # create a file within the folder
        storage_manager = connect_storage(settings)
        file_path = f'{folder.path}/file.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        f = UserFile(owner=user, parent_folder=folder)
        f.fname.name = file_path
        f.save()

        # create a link file within the folder
        lf = ChrisLinkFile(path=f'home/{self.username}/uploads', owner=user,
                           parent_folder=folder)
        lf.save(name=f'home_{self.username}_uploads')

        # create a file within the pointed folder
        pointed_folder, tf = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)
        file_path = f'{pointed_folder.path}/file1.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        pf = UserFile(owner=user, parent_folder=pointed_folder)
        pf.fname.name = file_path
        pf.save()

        perm = FeedUserPermission(feed=feed, user=other_user)
        perm.save()

        usernames = folder.shared_users.values_list('username', flat=True)
        self.assertIn(self.other_username, usernames)

        usernames = f.shared_users.values_list('username', flat=True)
        self.assertIn(self.other_username, usernames)

        usernames = lf.shared_users.values_list('username', flat=True)
        self.assertIn(self.other_username, usernames)

        usernames = pf.shared_users.values_list('username', flat=True)
        self.assertIn(self.other_username, usernames)

        ChrisFolder.objects.get(path=f'home/{self.username}').delete()

    def test_delete(self):
        """
        Test whether overriden delete method removes the user's write permission from all
        the folders, files and link files within the feed's folder. In addition, tests
        whether the same permission is removed from all objects pointed by the linked
        files under the feed's folder if they are owned by the feed's owner.
        """
        user = User.objects.get(username=self.username)
        other_user = User.objects.get(username=self.other_username)
        feed = Feed.objects.get(name=self.feed_name)
        folder = feed.folder.children.first()

        # create a file within the folder
        storage_manager = connect_storage(settings)
        file_path = f'{folder.path}/file.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        f = UserFile(owner=user, parent_folder=folder)
        f.fname.name = file_path
        f.save()

        # create a link file within the folder
        lf = ChrisLinkFile(path=f'home/{self.username}/uploads', owner=user,
                           parent_folder=folder)
        lf.save(name=f'home_{self.username}_uploads')

        # create a file within the pointed folder
        pointed_folder, tf = ChrisFolder.objects.get_or_create(
            path=f'home/{self.username}/uploads', owner=user)
        file_path = f'{pointed_folder.path}/file1.txt'
        with io.StringIO("test file") as fi:
            storage_manager.upload_obj(file_path, fi.read(),
                                       content_type='text/plain')
        pf = UserFile(owner=user, parent_folder=pointed_folder)
        pf.fname.name = file_path
        pf.save()

        perm = FeedUserPermission(feed=feed, user=other_user)
        perm.save()
        perm.delete()

        usernames = folder.shared_users.values_list('username', flat=True)
        self.assertNotIn(self.other_username, usernames)

        usernames = f.shared_users.values_list('username', flat=True)
        self.assertNotIn(self.other_username, usernames)

        usernames = lf.shared_users.values_list('username', flat=True)
        self.assertNotIn(self.other_username, usernames)

        usernames = pf.shared_users.values_list('username', flat=True)
        self.assertNotIn(self.other_username, usernames)

        ChrisFolder.objects.get(path=f'home/{self.username}').delete()
