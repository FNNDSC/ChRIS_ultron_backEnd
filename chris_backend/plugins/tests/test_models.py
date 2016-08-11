
import os, shutil

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from feeds.models import Feed, FeedFile
from plugins.models import Plugin, PluginParameter, PluginInstance



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
        user = User.objects.create_user(username=self.username,
                                        password=self.password)

        # create test directory where files are created
        self.test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = self.test_dir
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        #remove test directory
        shutil.rmtree(self.test_dir)
        settings.MEDIA_ROOT = os.path.dirname(self.test_dir)

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
        # MEDIA_ROOT/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        fs_output_path = '{0}/{1}/feed_{2}/{3}_{4}/data'.format(self.test_dir, self.username,
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
        # MEDIA_ROOT/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        ds_output_path = os.path.join(os.path.dirname(fs_output_path),
                                      '{0}_{1}/data'.format(pl_inst_ds.plugin.name,
                                                            pl_inst_ds.id))
        self.assertEquals(pl_inst_ds.get_output_path(), ds_output_path)
        self.assertTrue(os.path.isdir(ds_output_path))

    def test_register_output_files(self):
        """
        Test whether custom register_output_files method properly register a plugin's
        output file with the REST API.
        """
        # create aplugin instance 
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        root = settings.MEDIA_ROOT
        output_path = '{0}/{1}/feed_{2}/{3}_{4}/data'.format(root, self.username,
                                                             pl_inst.feed.id,
                                                             pl_inst.plugin.name,
                                                             pl_inst.id)
        output_path = pl_inst.get_output_path()

        # create a test file 
        test_file = output_path + '/file1.txt'
        file = open(test_file, "w")
        file.write("test file")
        file.close()
        pl_inst.register_output_files()
        self.assertEquals(FeedFile.objects.count(), 1)

        
