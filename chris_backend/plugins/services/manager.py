"""
Plugin manager module that provides functionality to add, modify and delete plugins.
"""

import os
import sys
from argparse import ArgumentParser
from chrisstoreclient.client import StoreClient

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # django needs to be loaded (eg. when this script is run from the command line)
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.utils import timezone

from plugins.models import Plugin
from plugins.models import ComputeResource
from plugins.serializers import PluginSerializer, PluginParameterSerializer
from plugins.serializers import DEFAULT_PARAMETER_SERIALIZERS


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
                                help="Compute resource where the plugin's instances run")
        parser_add.add_argument('storeurl',
                                help="Url of ChRIS store where the plugin is registered")
        parser_add.add_argument('--storeusername', help="Username for the ChRIS store")
        parser_add.add_argument('--storepassword', help="Password for the ChRIS store")
        parser_add.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "modify" command
        parser_modify = subparsers.add_parser('modify', help='Modify existing plugin')
        parser_modify.add_argument('name', help="Plugin's name")
        parser_modify.add_argument('--computeresource',
                                help="Compute resource where the plugin's instances run")
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
            default = parameter['default'] if 'default' in parameter else None
            del parameter['default']
            parameter_serializer = PluginParameterSerializer(data=parameter)
            parameter_serializer.is_valid(raise_exception=True)
            param = parameter_serializer.save(plugin=plugin)
            if default is not None:
                default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param.type](
                    data={'value': default})
                default_param_serializer.is_valid(raise_exception=True)
                default_param_serializer.save(plugin_param=param)

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
        if args.storeurl:
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
            plugin = plg_serializer.save(compute_resource=compute_resource)
            # collect existing and new parameters and validate and save them to the DB
            db_parameters = plugin.parameters.all()
            for parameter in parameters_data:
                default = parameter['default'] if 'default' in parameter else None
                del parameter['default']
                db_param = [p for p in db_parameters if p.name == parameter['name']]
                if db_param:
                    parameter_serializer = PluginParameterSerializer(db_param[0],
                                                                     data=parameter)
                else:
                    parameter_serializer = PluginParameterSerializer(data=parameter)
                parameter_serializer.is_valid(raise_exception=True)
                param = parameter_serializer.save(plugin=plugin)
                if default is not None:
                    db_default = param.get_default()
                    if db_default is not None: # check if there is already a default in DB
                        default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[
                            param.type](db_default, data={'value': default})
                    else:
                        default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[
                            param.type](data={'value': default})
                    default_param_serializer.is_valid(raise_exception=True)
                    default_param_serializer.save(plugin_param=param)
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

    @staticmethod
    def get_plugin_representation_from_store(name, store_url, username=None,
                                             password=None, timeout=30):
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
