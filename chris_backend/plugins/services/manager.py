"""
Plugin manager module that provides functionality to add, modify and delete plugins to the
plugins django app. There is also functionality to run and check the execution status of a
plugin app.
"""

import os
import sys
import json
import time
from argparse import ArgumentParser
from chrisstoreclient.client import StoreClient

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # django needs to be loaded (eg. when this script is run from the command line)
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.utils import timezone
from plugins.models import Plugin, PluginParameter
from plugins.models import TYPES, PLUGIN_TYPE_CHOICES, STATUS_TYPES
from plugins.fields import CPUInt, MemoryInt
from plugins.services import charm
from plugins.models import ComputeResource
from plugins.serializers import PluginSerializer, PluginParameterSerializer


class PluginManager(object):
    def __init__(self):
        parser = ArgumentParser(description='Manage plugins')
        subparsers = parser.add_subparsers(dest='subparser_name', title='subcommands',
                                           description='valid subcommands',
                                           help='sub-command help')

        # create the parser for the "add" command
        parser_add = subparsers.add_parser('add', help='Add a new plugin')
        parser_add.add_argument('name', help="Plugin's name")
        parser_add.add_argument('computeresource',
                                help="Compute resource where the plugin's instances runs")
        parser_add.add_argument('storeurl',
                                help="Url of ChRIS store where the plugin is registered")
        parser_add.add_argument('storeusername', help="Username for the ChRIS store")
        parser_add.add_argument('storepassword', help="Password for the ChRIS store")
        parser_add.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "modify" command
        parser_modify = subparsers.add_parser('modify', help='Modify existing plugin')
        parser_modify.add_argument('name', help="Plugin's name")
        parser_modify.add_argument('--computeresource',
                                help="Compute resource where the plugin's instances runs")
        parser_modify.add_argument('storeurl',
                                help="Url of ChRIS store where the plugin is registered")
        parser_modify.add_argument('--storeusername', help="Username for the ChRIS store")
        parser_modify.add_argument('--storepassword', help="Password for the ChRIS store")
        parser_add.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "remove" command
        parser_remove = subparsers.add_parser('remove', help='Remove an existing plugin')
        parser_remove.add_argument('name', help="Plugin's name")

        self.parser = parser
        self.str_service        = ''
        self.str_IOPhost        = ''

        # Debug specifications
        self.b_quiet            = False
        self.b_useDebug         = True
        self.str_debugFile      = '%s/tmp/debug-charm.log' % os.environ['HOME']

    def add_plugin(self, args):
        """
        Register/add a new plugin to the system.
        """
        timeout = 30
        if args.storetimeout:
            timeout = args.storetimeout
        plg_repr = self.get_plugin_representation_from_store(args.storeurl,
                                                             args.storeusername,
                                                             args.storepassword, timeout)
        plg_serializer = PluginSerializer(data=plg_repr)
        plg_serializer.is_valid(raise_exception=True)
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier=args.computeresource)
        plugin = plg_serializer.save(compute_resource=compute_resource)
        # collect parameters and validate and save them to the DB
        parameters_data = plg_repr['parameters']
        for parameter in parameters_data:
            parameter_serializer = PluginParameterSerializer(parameter)
            parameter_serializer.is_valid(raise_exception=True)
            parameter_serializer.save(plugin=plugin)

    def modify_plugin(self, args):
        """
        Modify an existing/registered plugin and add the current date as a new plugin
        modification date.
        """
        data = self.get_plugin_descriptors(args)
        plugin = self.get_plugin(args.name)
        if args.newname:
            data['name'] = args.newname
        plg_serializer = PluginSerializer(plugin, data=data)
        plg_serializer.is_valid(raise_exception=True)
        plugin.modification_date = timezone.now()
        plugin.save()

    def register_plugin_app_modification(self, dock_image_name):
        """
        Register/add new parameters to a plugin from the corresponding plugin's app.
        Also update plugin's fields and add the current date as a new plugin modification
        date.
        """
        # get representation from the corresponding app
        app_repr = self.get_plugin_app_representation(dock_image_name)
        name = self.get_plugin_name(app_repr)
        max_cpu_limit, min_cpu_limit                 = self.get_cpu_limit(app_repr)
        max_memory_limit, min_memory_limit           = self.get_memory_limit(app_repr)
        max_number_of_workers, min_number_of_workers = self.get_number_of_workers(app_repr)
        max_gpu_limit, min_gpu_limit                 = self.get_gpu_limit(app_repr)

        # update plugin fields (type cannot be changed as 'ds' plugins cannot have created
        # a feed in the DB)
        plugin = self.get_plugin(name)
        plugin.authors       = app_repr['authors']
        plugin.title         = app_repr['title']
        plugin.category      = app_repr['category']
        plugin.description   = app_repr['description']
        plugin.documentation = app_repr['documentation']
        plugin.license       = app_repr['license']
        plugin.version       = app_repr['version']
        plugin.max_cpu_limit         = self.insert_default(max_cpu_limit, Plugin.defaults['max_limit'])
        plugin.min_cpu_limit         = self.insert_default(min_cpu_limit,
                                                           Plugin.defaults['min_cpu_limit'])
        plugin.max_memory_limit      = self.insert_default(max_memory_limit, Plugin.defaults['max_limit'])
        plugin.min_memory_limit      = self.insert_default(min_memory_limit,
                                                           Plugin.defaults['min_memory_limit'])
        plugin.max_number_of_workers = self.insert_default(max_number_of_workers, Plugin.defaults['max_limit'])
        plugin.min_number_of_workers = self.insert_default(min_number_of_workers, 1)
        plugin.max_gpu_limit         = self.insert_default(max_gpu_limit, Plugin.defaults['max_limit'])
        plugin.min_gpu_limit         = self.insert_default(min_gpu_limit, 0)

        # add there are new parameters then add them
        new_params = app_repr['parameters']
        existing_param_names = [parameter.name for parameter in plugin.parameters.all()]
        for param in new_params:
            if param['name'] not in existing_param_names:
                self._save_plugin_param(plugin, param)

        plugin.modification_date = timezone.now()
        plugin.save()

    def remove_plugin(self, args):
        """
        Remove an existing/registered plugin from the system.
        """
        plugin = self.get_plugin(args.name)
        plugin.delete()

    def run(self, args=None):
        """
        Parse the arguments passed to the manager and perform the appropriate action.
        """
        options = self.parser.parse_args(args)
        if options.subparser_name == 'add':
            self.add_plugin(options)
        elif options.subparser_name == 'modify':
            self.modify_plugin(options)
        elif options.subparser_name == 'remove':
            self.remove_plugin(options)

    def run_plugin_app(self, plugin_inst, parameter_dict, **kwargs):
        """
        Run a plugin's app.
        """

        # These directory overrides allow for mapping from the original ChRIS dir space
        # to the plugin input and output dir spaces.
        str_inputDirOverride        = ''
        str_outputDirOverride       = ''
        self.str_IOPhost = plugin_inst.plugin.compute_resource.compute_resource_identifier
 

        for k, v in kwargs.items():
            if k == 'useDebug':             self.b_useDebug         = v
            if k == 'debugFile':            self.str_debugFile      = v
            if k == 'quiet':                self.b_quiet            = v
            if k == 'service':              self.str_service        = v
            if k == 'inputDirOverride':     str_inputDirOverride    = v
            if k == 'outputDirOverride':    str_outputDirOverride   = v
            if k == 'IOPhost':              self.str_IOPhost        = v


        plugin_repr = self.get_plugin_app_representation(plugin_inst.plugin.dock_image)
        # get input dir
        inputdir            = ""
        inputdirManagerFS   = ""
        if plugin_inst.previous:
            inputdirManagerFS   = plugin_inst.previous.get_output_path()
            inputdir            = inputdirManagerFS
        if len(str_inputDirOverride):
            inputdir = str_inputDirOverride
        # get output dir
        outputdirManagerFS      = plugin_inst.get_output_path()
        outputdir               = outputdirManagerFS
        if len(str_outputDirOverride):
            outputdir = str_outputDirOverride
        app_args = []
        # append input dir to app's argument list (only for ds plugins)
        if plugin_repr['type'] == 'ds' and inputdir:
            app_args.append(inputdir)
        # append output dir to app's argument list
        app_args.append(outputdir)
        # append flag to save input meta data (passed options)
        app_args.append("--saveinputmeta")
        # append flag to save output meta data (output description)
        app_args.append("--saveoutputmeta")
        # append the parameters to app's argument list
        if parameter_dict:
            for param_name in parameter_dict:
                param_value = parameter_dict[param_name]
                for plugin_param in plugin_repr['parameters']:
                    if plugin_param['name'] == param_name:
                        app_args.append(plugin_param['flag'])
                        if plugin_param['action'] == 'store':
                            app_args.append(param_value)
                        break

        # run the app via an external REST service...
        chris_service = charm.Charm(
            app_args    = app_args,
            d_args      = parameter_dict,
            plugin_inst = plugin_inst,
            plugin_repr = plugin_repr,
            inputdir    = inputdirManagerFS,
            outputdir   = outputdirManagerFS,
            IOPhost     = self.str_IOPhost,
            quiet       = True
        )

        # Some dev notes...
        #
        # To run the app directly on the CLI via 'crunner', use
        #         chris_service.app_manage(method = 'crunner')
        # Note that this call blocks until the CLI process returns.
        #
        # To run the app 'internally', i.e. not as a CLI but by calling the app 
        # run() method directly in python:
        #         chris_service.app_manage(method = 'internal')
        # Again, this blocks on the app run() method.
        #
        # The call to "method = 'pfcon'" does not block but dispatches
        # to a completely asynchronous external server process and returns 
        # immediately. The check on output is performed when views are updated,
        # again by talking to the application server.
        #

        chris_service.app_manage(method     = self.str_service,
                                 IOPhost    = self.str_IOPhost   )

        # Finally, any output files generated by the app need to be registered in the DB.
        # This is handled by the app_manage() method, and in asynchronous cases (i.e. via the pman server)
        # registration occurs via a call to the overloaded retrieve() method in PluginInstanceDetail in
        # plugins/views.py.
        #

    def check_apps_exec_server(self, **kwargs):
        """
        check if a remote server instance is servicing requests
        :return:
        """
        # pudb.set_trace()
        chris_service   = charm.Charm(**kwargs)
        chris_service.app_service_checkIfAvailable(**kwargs)
        # Wait a bit for transients
        time.sleep(5)

    def shutdown_apps_exec_server(self, **kwargs):
        """
        Shutdown a remote server instance
        :return:
        """
        # pudb.set_trace()
        chris_service   = charm.Charm(**kwargs)
        chris_service.app_service_shutdown(**kwargs)
        # Wait a bit for transients
        time.sleep(5)

    def check_plugin_app_exec_status(self, plugin_inst, **kwargs):
        """
        Check a plugin's app execution status. It connects to the remote
        service to determine job status.
        """
        str_responseStatus  = ''
        # pudb.set_trace()
        chris_service   = charm.Charm(
            plugin_inst = plugin_inst
        )
        str_responseStatus = chris_service.app_statusCheckAndRegister()
        return str_responseStatus

    @staticmethod
    def get_plugin_representation_from_store(name, store_url, username, password,
                                             timeout=30):
        """
        Get a plugin app representation from the ChRIS store.
        """
        store_client = StoreClient(store_url, username, password, timeout)
        return store_client.get_plugin(name)

    @staticmethod
    def get_plugin(name):
        """
        Get an existing plugin.
        """
        try:
            plugin = Plugin.objects.get(name=name)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find '%s' plugin in the system" % name)
        return plugin


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    manager.run()
