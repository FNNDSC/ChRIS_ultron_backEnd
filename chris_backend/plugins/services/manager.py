"""
Plugin manager module that provides functionality to add, modify and delete plugins
through the CLI.
"""

import os
import sys
from argparse import ArgumentParser
from chrisstoreclient.client import StoreClient

if __name__ == '__main__':
    # django needs to be loaded when this script is run standalone from the command line
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
        parser_add.add_argument('-v', '--version', help="Plugin's version. If not "
                                                        "provided then the latest "
                                                        "version is fetched.")
        parser_add.add_argument('--storeusername', help="Username for the ChRIS store")
        parser_add.add_argument('--storepassword', help="Password for the ChRIS store")
        parser_add.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "modify" command
        parser_modify = subparsers.add_parser('modify', help='Modify existing plugin')
        parser_modify.add_argument('name', help="Plugin's name")
        parser_modify.add_argument('version', help="Plugin's version")
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
        parser_remove.add_argument('version', help="Plugin's version")

        self.parser = parser

    def add_plugin(self, args):
        """
        Register/add a new plugin to the system.
        """
        plg_repr = self.get_plugin_representation_from_store(args.name, args.storeurl,
                                                             args.version,
                                                             args.storeusername,
                                                             args.storepassword,
                                                             args.storetimeout)
        parameters_data = plg_repr['parameters']
        del plg_repr['parameters']
        plg_serializer = PluginSerializer(data=plg_repr)
        plg_serializer.is_valid(raise_exception=True)

        # collect and validate parameters
        parameters_serializers = []
        for parameter in parameters_data:
            default = parameter.pop('default', None)
            parameter_serializer = PluginParameterSerializer(data=parameter)
            parameter_serializer.is_valid(raise_exception=True)
            serializer_dict = {'serializer': parameter_serializer,
                               'default_serializer': None}
            if default is not None:
                param_type = parameter['type']
                default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param_type](
                    data={'value': default})
                default_param_serializer.is_valid(raise_exception=True)
                serializer_dict['default_serializer'] = default_param_serializer
            parameters_serializers.append(serializer_dict)

        # if no validation errors at this point then save to the DB
        (compute_resource, tf) = ComputeResource.objects.get_or_create(
            compute_resource_identifier=args.computeresource)
        plugin = plg_serializer.save(compute_resource=compute_resource)
        for param_serializer_dict in parameters_serializers:
            param = param_serializer_dict['serializer'].save(plugin=plugin)
            if param_serializer_dict['default_serializer'] is not None:
                param_serializer_dict['default_serializer'].save(plugin_param=param)

    def modify_plugin(self, args):
        """
        Modify an existing/registered plugin and add the current date as a new plugin
        modification date.
        """
        plugin = self.get_plugin(args.name, args.version)
        compute_resource = None
        plg_repr = None
        if args.computeresource:
            (compute_resource, tf) = ComputeResource.objects.get_or_create(
                compute_resource_identifier=args.computeresource)
        if args.storeurl:
            plg_repr = self.get_plugin_representation_from_store(args.name, args.storeurl,
                                                                 args.version,
                                                                 args.storeusername,
                                                                 args.storepassword,
                                                                 args.storetimeout)
        if plg_repr:
            del plg_repr['parameters']
            plg_serializer = PluginSerializer(plugin, data=plg_repr)
            plg_serializer.is_valid(raise_exception=True)
            if compute_resource:
                plugin = plg_serializer.save(compute_resource=compute_resource)
            else:
                plugin = plg_serializer.save()
        elif compute_resource:
            plg_serializer = PluginSerializer(plugin)
            plugin = plg_serializer.save(compute_resource=compute_resource)

        if plg_repr or compute_resource:
            plugin.modification_date = timezone.now()
            plugin.save()

    def remove_plugin(self, args):
        """
        Remove an existing/registered plugin from the system. All the associated plugin
        instances are cancelled before they are deleted by the DB CASCADE.
        """
        plugin = self.get_plugin(args.name, args.version)
        for plg_inst in plugin.instances.all():
            plg_inst.cancel()
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
    def get_plugin_representation_from_store(name, store_url, version=None, username=None,
                                             password=None, timeout=30):
        """
        Get a plugin app representation from the ChRIS store.
        """
        store_client = StoreClient(store_url, username, password, timeout)
        plg = store_client.get_plugin(name, version)
        parameters = []
        offset = 0
        limit = 50
        while True:
            result = store_client.get_plugin_parameters(plg['id'], {'limit': limit,
                                                                    'offset': offset})
            parameters.extend(result['data'])
            offset += limit
            if not result['hasNextPage']: break
        plg['parameters'] = parameters
        return plg

    @staticmethod
    def get_plugin(name, version):
        """
        Get an existing plugin.
        """
        try:
            plugin = Plugin.objects.get(name=name, version=version)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find '%s' plugin with version %s in the system" %
                            (name, version))
        return plugin


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    manager.run()
