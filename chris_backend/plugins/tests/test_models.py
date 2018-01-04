
import os, shutil
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

import swiftclient

from feeds.models import Feed, FeedFile
from plugins.models import Plugin, PluginParameter, PluginInstance, swiftclient


class PluginModelTests(TestCase):
    
    def setUp(self):
        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': False}}

        # create a plugin
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                    type='fs')
        # add plugins' parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])

    def test_get_plugin_parameter_names(self):
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        param_names = plugin.get_plugin_parameter_names()
        self.assertEquals(param_names, ['dir'])
        
      
class PluginInstanceModelTests(TestCase):
    
    def setUp(self):
        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': False}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'prefix': {'type': 'string', 'optional': False}}
        self.username = 'foo'
        self.password = 'foo-pass'

        # create plugins
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                    type='fs')
        (plugin_ds, tf) = Plugin.objects.get_or_create(name=self.plugin_ds_name,
                                                    type='ds')
        # add plugins' parameters
        PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='prefix',
            type=self.plugin_ds_parameters['prefix']['type'],
            optional=self.plugin_ds_parameters['prefix']['optional'])

        # create user
        User.objects.create_user(username=self.username,
                                        password=self.password)

    def test_save_creates_new_feed_just_after_fs_plugininstance_is_created(self):
        """
        Test whether overriden save method creates a feed just after an 'fs' plugin 
        instance is created.
        """
        # create an 'fs' plugin instance that in turn should create a new feed
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        
        self.assertEquals(Feed.objects.count(), 1)
        self.assertEquals(pl_inst.feed.name,pl_inst.plugin.name)

    def test_save_do_not_create_new_feed_just_after_ds_plugininstance_is_created(self):
        """
        Test whether overriden save method do not create a feed just after a 'ds' plugin 
        instance is created.
        """
        # create a 'ds' plugin instance that shouldn't create a new feed
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        self.assertEquals(Feed.objects.count(), 0)

    def test_get_root_instance(self):
        """
        Test whether custom get_root_instance method returns the root 'fs' plugin 
        instance for a give plugin instance.
        """
        # create a 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst_root = PluginInstance.objects.create(plugin=plugin, owner=user)
        # create a 'ds' plugin instance whose root is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=pl_inst_root)
        root_instance = pl_inst.get_root_instance()
        self.assertEquals(root_instance, pl_inst_root)

    def test_get_output_path(self):
        """
        Test whether custom get_output_path method returns appropriate output paths
        for both 'fs' and 'ds' plugins.
        """
        # create an 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst_fs = PluginInstance.objects.create(plugin=plugin_fs, owner=user)
        # 'fs' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        fs_output_path = '{0}/feed_{1}/{2}_{3}/data'.format( self.username,
                                                             pl_inst_fs.feed.id,
                                                             pl_inst_fs.plugin.name,
                                                             pl_inst_fs.id) 
        self.assertEquals(pl_inst_fs.get_output_path(), fs_output_path)
        

        # create a 'ds' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        pl_inst_ds = PluginInstance.objects.create(plugin=plugin_ds,
                                                   owner=user, previous=pl_inst_fs)
        # 'ds' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        ds_output_path = os.path.join(os.path.dirname(fs_output_path),
                                      '{0}_{1}/data'.format(pl_inst_ds.plugin.name,
                                                            pl_inst_ds.id))
        self.assertEquals(pl_inst_ds.get_output_path(), ds_output_path)

    def test_register_output_files(self):
        """
        Test whether custom register_output_files method properly register a plugin's
        output file with the REST API.
        """
        # create an 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        pl_inst.feed.name = 'Feed1'
        pl_inst.feed.save()
        output_path = pl_inst.get_output_path()
        object_list = [{'name': output_path + '/file1.txt'}]
        container_data = ['', object_list]

        with mock.patch.object(swiftclient.Connection, '__init__',
                               return_value=None) as conn_init_mock:
            with mock.patch.object(swiftclient.Connection, 'get_container',
                                   return_value=container_data) as conn_get_container_mock:
                pl_inst.register_output_files()
                conn_init_mock.assert_called_with(user=settings.SWIFT_USERNAME,
                                                  key=settings.SWIFT_KEY,
                                                  authurl=settings.SWIFT_AUTH_URL,)
                conn_get_container_mock.assert_called_with(settings.SWIFT_CONTAINER_NAME,
                                                   prefix=output_path, full_listing=True)
                self.assertEquals(FeedFile.objects.count(), 1)
                feedfile = FeedFile.objects.get(plugin_inst=pl_inst, feed=pl_inst.feed)
                self.assertEquals(feedfile.fname.name, output_path + '/file1.txt')

    @tag('integration')
    def test_integration_register_output_files(self):
        """
        Test whether custom register_output_files method properly register a plugin's
        output file with the REST API.
        """
        # create an 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        pl_inst.feed.name = 'Feed1'
        pl_inst.feed.save()

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

        # create test directory where files are created
        self.test_dir = settings.MEDIA_ROOT + '/test'
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        # create a test file
        test_file = self.test_dir + '/file1.txt'
        file = open(test_file, "w")
        file.write("test file")
        file.close()

        # upload file to Swift storage
        output_path = pl_inst.get_output_path()
        with open(test_file, 'r') as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, output_path + '/file1.txt',
                            contents=file1.read(),
                            content_type='text/plain')
        # remove test directory
        shutil.rmtree(self.test_dir)

        pl_inst.register_output_files()
        self.assertEquals(FeedFile.objects.count(), 1)
        feedfile = FeedFile.objects.get(plugin_inst=pl_inst, feed=pl_inst.feed)
        self.assertEquals(feedfile.fname.name, output_path + '/file1.txt')

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, output_path + '/file1.txt')


        
