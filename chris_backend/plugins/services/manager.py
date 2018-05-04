"""
Plugin manager module that provides functionality to add, modify and delete plugins to the
plugins django app. There is also functionality to run and check the execution status of a
plugin app.
"""

import os
import sys
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
from plugins.models import Plugin, PluginParameter, ComputeResource
from plugins.serializers import PluginSerializer, PluginParameterSerializer
from plugins.services import charm


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
        parser_modify.add_argument('--storeurl',
                                help="Url of ChRIS store where the plugin is registered")
        parser_modify.add_argument('--storeusername', help="Username for the ChRIS store")
        parser_modify.add_argument('--storepassword', help="Password for the ChRIS store")
        parser_modify.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "remove" command
        parser_remove = subparsers.add_parser('remove', help='Remove an existing plugin')
        parser_remove.add_argument('name', help="Plugin's name")

        self.parser = parser
        self.str_service        = ''

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
        plg_repr = self.get_plugin_representation_from_store(args.name, args.storeurl,
                                                             args.storeusername,
                                                             args.storepassword, timeout)
        parameters_data = plg_repr['parameters']
        del plg_repr['parameters']
        plg_serializer = PluginSerializer(data=plg_repr)
        plg_serializer.is_valid(raise_exception=True)
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier=args.computeresource)
        plugin = plg_serializer.save(compute_resource=compute_resource)
        # collect parameters and validate and save them to the DB
        for parameter in parameters_data:
            parameter_serializer = PluginParameterSerializer(data=parameter)
            parameter_serializer.is_valid(raise_exception=True)
            parameter_serializer.save(plugin=plugin)

    def modify_plugin(self, args):
        """
        Modify an existing/registered plugin and add the current date as a new plugin
        modification date.
        """
        plugin = self.get_plugin(args.name)
        compute_resource = None
        plg_repr = None
        if args.computeresource:
            (compute_resource, tf) = ComputeResource.objects.get_or_create(
                compute_resource_identifier=args.computeresource)
        if args.storeurl and args.storeusername and args.storepassword:
            timeout = 30
            if args.storetimeout:
                timeout = args.storetimeout
            plg_repr = self.get_plugin_representation_from_store(args.name, args.storeurl,
                                                                 args.storeusername,
                                                                 args.storepassword,
                                                                 timeout)
        if plg_repr:
            parameters_data = plg_repr['parameters']
            del plg_repr['parameters']
            plg_serializer = PluginSerializer(plugin, data=plg_repr)
            plg_serializer.is_valid(raise_exception=True)
            if compute_resource:
                plugin = plg_serializer.save(compute_resource=compute_resource)
            else:
                plugin = plg_serializer.save()
            # collect existing and new parameters and validate and save them to the DB
            db_parameters = plugin.parameters.all()
            for parameter in parameters_data:
                db_param = [p for p in db_parameters if p.name == parameter['name']]
                if db_param:
                    parameter_serializer = PluginParameterSerializer(db_param[0],
                                                                     data=parameter)
                else:
                    parameter_serializer = PluginParameterSerializer(data=parameter)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializer.save(plugin=plugin)
        elif compute_resource:
            plg_serializer = PluginSerializer(plugin)
            plugin = plg_serializer.save(compute_resource=compute_resource)

        if plg_repr or compute_resource:
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

        for k, v in kwargs.items():
            if k == 'useDebug':             self.b_useDebug         = v
            if k == 'debugFile':            self.str_debugFile      = v
            if k == 'quiet':                self.b_quiet            = v
            if k == 'service':              self.str_service        = v
            if k == 'inputDirOverride':     str_inputDirOverride    = v
            if k == 'outputDirOverride':    str_outputDirOverride   = v

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
        if plugin_inst.plugin.type == 'ds' and inputdir:
            app_args.append(inputdir)
        # append output dir to app's argument list
        app_args.append(outputdir)
        # append flag to save input meta data (passed options)
        app_args.append("--saveinputmeta")
        # append flag to save output meta data (output description)
        app_args.append("--saveoutputmeta")
        # append the parameters to app's argument list
        db_parameters = plugin_inst.plugin.parameters.all()
        if parameter_dict:
            for param_name in parameter_dict:
                param_value = parameter_dict[param_name]
                for db_param in db_parameters:
                    if db_param.name == param_name:
                        app_args.append(db_param.flag)
                        if db_param.action == 'store':
                            app_args.append(param_value)
                        break

        # run the app via an external REST service...
        str_IOPhost = plugin_inst.compute_resource.compute_resource_identifier
        chris_service = charm.Charm(
            app_args    = app_args,
            d_args      = parameter_dict,
            plugin_inst = plugin_inst,
            inputdir    = inputdirManagerFS,
            outputdir   = outputdirManagerFS,
            IOPhost     = str_IOPhost,
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
                                 IOPhost    = str_IOPhost   )

        # Finally, any output files generated by the app need to be registered in the DB.
        # This is handled by the app_manage() method, and in asynchronous cases (i.e. via the pman server)
        # registration occurs via a call to the overloaded retrieve() method in PluginInstanceDetail in
        # plugins/views.py.
        #

    @staticmethod
    def check_apps_exec_server(**kwargs):
        """
        check if a remote server instance is servicing requests
        :return:
        """
        # pudb.set_trace()
        chris_service = charm.Charm(**kwargs)
        chris_service.app_service_checkIfAvailable(**kwargs)
        # Wait a bit for transients
        time.sleep(5)

    @staticmethod
    def shutdown_apps_exec_server(**kwargs):
        """
        Shutdown a remote server instance
        :return:
        """
        # pudb.set_trace()
        chris_service = charm.Charm(**kwargs)
        chris_service.app_service_shutdown(**kwargs)
        # Wait a bit for transients
        time.sleep(5)

    @staticmethod
    def check_plugin_app_exec_status(plugin_inst):
        """
        Check a plugin's app execution status. It connects to the remote
        service to determine job status.
        """
        # pudb.set_trace()
        chris_service = charm.Charm(
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
