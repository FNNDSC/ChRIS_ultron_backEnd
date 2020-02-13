
import logging
import os
import io
from unittest import mock

from django.test import TestCase, tag
from django.contrib.auth.models import User
from django.conf import settings

from feeds.models import Feed
from plugins.models import Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter
from plugininstances.models import PluginInstance, PluginInstanceFile
from plugininstances.models import PluginInstanceFilter
from plugininstances.models import swiftclient
from plugininstances.models import PluginAppManager


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)

        self.plugin_fs_name = "simplecopyapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'prefix': {'type': 'string', 'optional': False}}
        self.username = 'foo'
        self.password = 'foo-pass'
        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier="host")

        # create plugins
        (plugin_fs, tf) = Plugin.objects.get_or_create(name=self.plugin_fs_name,
                                                       type='fs',
                                                       compute_resource=self.compute_resource)
        (plugin_ds, tf) = Plugin.objects.get_or_create(name=self.plugin_ds_name,
                                                       type='ds',
                                                       compute_resource=self.compute_resource)
        # add plugins' parameters
        (plg_param, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param, value=default)

        PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='prefix',
            type=self.plugin_ds_parameters['prefix']['type'],
            optional=self.plugin_ds_parameters['prefix']['optional'])

        # create user
        User.objects.create_user(username=self.username,
                                 password=self.password)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.DEBUG)


class PluginInstanceModelTests(ModelTests):

    def test_save_creates_new_feed_just_after_fs_plugininstance_is_created(self):
        """
        Test whether overriden save method creates a feed just after an 'fs' plugin 
        instance is created.
        """
        # create an 'fs' plugin instance that in turn should create a new feed
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                            compute_resource=plugin.compute_resource)
        
        self.assertEqual(Feed.objects.count(), 1)
        self.assertEqual(pl_inst.feed.name,pl_inst.plugin.name)

    def test_save_does_not_create_new_feed_just_after_ds_plugininstance_is_created(self):
        """
        Test whether overriden save method does not create a feed just after a 'ds' plugin
        instance is created.
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        PluginInstance.objects.create(plugin=plugin, owner=user, previous=plg_inst,
                                      compute_resource=plugin.compute_resource)
        # the new 'ds' plugin instance shouldn't create a new feed
        self.assertEqual(Feed.objects.count(), 1)

    def test_get_root_instance(self):
        """
        Test whether custom get_root_instance method returns the root 'fs' plugin 
        instance for a give plugin instance.
        """
        # create a 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        # create a 'ds' plugin instance whose root is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=plg_inst_root,
                                                compute_resource=plugin.compute_resource)
        root_instance = plg_inst.get_root_instance()
        self.assertEqual(root_instance, plg_inst_root)

    def test_get_descendant_instances(self):
        """
        Test whether custom get_descendant_instances method returns all the plugin
        instances that are a descendant of a plugin instance
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        plg_inst1 = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=plg_inst_root,
                                                compute_resource=plugin.compute_resource)
        # create another 'ds' plugin instance whose previous is the previous 'ds' plugin
        # instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        plg_inst2 = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=plg_inst1,
                                                compute_resource=plugin.compute_resource)
        decend_instances = plg_inst_root.get_descendant_instances()
        self.assertEqual(len(decend_instances), 3)
        self.assertEqual(decend_instances[0], plg_inst_root)
        self.assertEqual(decend_instances[1], plg_inst1)
        self.assertEqual(decend_instances[2], plg_inst2)

    def test_get_output_path(self):
        """
        Test whether custom get_output_path method returns appropriate output paths
        for both 'fs' and 'ds' plugins.
        """
        # create an 'fs' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_fs = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst_fs = PluginInstance.objects.create(plugin=plugin_fs, owner=user,
                                                    compute_resource=plugin_fs.compute_resource)
        # 'fs' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        fs_output_path = '{0}/feed_{1}/{2}_{3}/data'.format( self.username,
                                                             pl_inst_fs.feed.id,
                                                             pl_inst_fs.plugin.name,
                                                             pl_inst_fs.id) 
        self.assertEqual(pl_inst_fs.get_output_path(), fs_output_path)
        

        # create a 'ds' plugin instance 
        user = User.objects.get(username=self.username)
        plugin_ds = Plugin.objects.get(name=self.plugin_ds_name)
        pl_inst_ds = PluginInstance.objects.create(plugin=plugin_ds,
                    owner=user, previous=pl_inst_fs, compute_resource=plugin_ds.compute_resource)
        # 'ds' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        ds_output_path = os.path.join(os.path.dirname(fs_output_path),
                                      '{0}_{1}/data'.format(pl_inst_ds.plugin.name,
                                                            pl_inst_ds.id))
        self.assertEqual(pl_inst_ds.get_output_path(), ds_output_path)

    def test_register_output_files(self):
        """
        Test whether custom register_output_files method properly registers a plugin's
        output file with the REST API.
        """
        # create an 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user, 
                                    compute_resource=plugin.compute_resource)
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
                self.assertEqual(PluginInstanceFile.objects.count(), 1)
                plg_inst_file = PluginInstanceFile.objects.get(plugin_inst=pl_inst)
                self.assertEqual(plg_inst_file.fname.name, output_path + '/file1.txt')

    @tag('integration')
    def test_integration_register_output_files(self):
        """
        Test whether custom register_output_files method properly registers a plugin's
        output file with the REST API.
        """
        # create an 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                            compute_resource=plugin.compute_resource)

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user=settings.SWIFT_USERNAME,
            key=settings.SWIFT_KEY,
            authurl=settings.SWIFT_AUTH_URL,
        )
        # create container in case it doesn't already exist
        conn.put_container(settings.SWIFT_CONTAINER_NAME)

        # upload file to Swift storage
        output_path = plg_inst.get_output_path()
        with io.StringIO("test file") as file1:
            conn.put_object(settings.SWIFT_CONTAINER_NAME, output_path + '/file1.txt',
                            contents=file1.read(),
                            content_type='text/plain')

        plg_inst.register_output_files()
        self.assertEqual(PluginInstanceFile.objects.count(), 1)
        plg_inst_file = PluginInstanceFile.objects.get(plugin_inst=plg_inst)
        self.assertEqual(plg_inst_file.fname.name, output_path + '/file1.txt')

        # delete file from Swift storage
        conn.delete_object(settings.SWIFT_CONTAINER_NAME, output_path + '/file1.txt')

    def test_cancel(self):
        """
        Test whether custom cancel method cancels the execution of the app corresponding
        to a plugin instance.
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)

        self.assertEqual(plg_inst.status, 'started')
        with mock.patch.object(PluginAppManager, 'cancel_plugin_app_exec',
                               return_value=None) as manager_cancel_plugin_app_exec_mock:
            plg_inst.cancel()
            # check that manager's cancel_plugin_app_exec method was called once
            manager_cancel_plugin_app_exec_mock.assert_called_once()
        self.assertEqual(plg_inst.status, 'cancelled')

    def test_run(self):
        """
        Test whether custom run method starts the execution of the app corresponding
        to a plugin instance.
        """
        with mock.patch.object(PluginAppManager, 'run_plugin_app',
                               return_value=None) as run_plugin_app_mock:
            user = User.objects.get(username=self.username)
            plugin = Plugin.objects.get(name=self.plugin_fs_name)
            plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                     compute_resource=plugin.compute_resource)
            self.assertEqual(plg_inst.status, 'started')
            parameters_dict = {'dir': './'}
            plg_inst.run(parameters_dict)
            self.assertEqual(plg_inst.status, 'started')
            # check that manager's run_plugin_app method was called with appropriate args
            run_plugin_app_mock.assert_called_with(plg_inst,
                                                   parameters_dict,
                                                   service             = 'pfcon',
                                                   inputDirOverride    = '/share/incoming',
                                                   outputDirOverride   = '/share/outgoing')

    def test_check_exec_status(self):
        """
        Test whether custom check_exec_status method checks the execution status of the
        app corresponding to a plugin instance.
        """
        with mock.patch.object(PluginAppManager, 'check_plugin_app_exec_status',
                               return_value=None) as check_plugin_app_exec_status_mock:
            user = User.objects.get(username=self.username)
            plugin = Plugin.objects.get(name=self.plugin_fs_name)
            plg_inst = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                     compute_resource=plugin.compute_resource)
            plg_inst.check_exec_status()
            # check that manager's check_plugin_app_exec_status method was called once
            check_plugin_app_exec_status_mock.assert_called_once()


class PluginInstanceFilterModelTests(ModelTests):

    def test_filter_by_root_id(self):
        """
        Test whether custom filter_by_root_id method returns the plugin instances in a
        queryset with a common root plugin instance.
        """
        # create a 'fs' plugin instance
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(name=self.plugin_fs_name)
        plg_inst_root = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                compute_resource=plugin.compute_resource)
        # create a 'ds' plugin instance whose previous is the previous 'fs' plugin instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        plg_inst1 = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=plg_inst_root,
                                                compute_resource=plugin.compute_resource)
        # create another 'ds' plugin instance whose previous is the previous 'ds' plugin
        # instance
        plugin = Plugin.objects.get(name=self.plugin_ds_name)
        plg_inst2 = PluginInstance.objects.create(plugin=plugin, owner=user,
                                                previous=plg_inst1,
                                                compute_resource=plugin.compute_resource)
        queryset = PluginInstance.objects.all()
        value = plg_inst1.id
        filter = PluginInstanceFilter()
        filtered_queryset = filter.filter_by_root_id(queryset, "", value)
        self.assertEqual(len(filtered_queryset), 2)
        self.assertEqual(filtered_queryset[0], plg_inst1)
        self.assertEqual(filtered_queryset[1], plg_inst2)
