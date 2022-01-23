"""
Plugin manager module that provides functionality to add, modify and delete plugins
through the CLI.
"""

import os
import sys

if __name__ == '__main__':
    # django needs to be loaded when this script is run standalone from the command line
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.conf import settings
from django.utils import timezone

from argparse import ArgumentParser
from argparse import ArgumentError
from chrisstoreclient.client import StoreClient

from plugins.models import ComputeResource
from plugins.models import PluginMeta, Plugin
from plugins.serializers import ComputeResourceSerializer
from plugins.serializers import (PluginMetaSerializer, PluginSerializer,
                                 PluginParameterSerializer, DEFAULT_PARAMETER_SERIALIZERS)


class PluginManager(object):

    def __init__(self):
        parser = ArgumentParser(description='Manage plugins')
        subparsers = parser.add_subparsers(dest='subparser_name', title='subcommands',
                                           description='valid subcommands',
                                           help='sub-command help')

        # create the parser for the "add" command
        parser_add = subparsers.add_parser('add', help='add a new compute resource')
        parser_add.add_argument('computeresource',
                                help="compute resource where plugins' instances run")
        parser_add.add_argument('url', help="compute resource's url")
        parser_add.add_argument('--auth_url', help="compute resource's auth url")
        parser_add.add_argument('--auth_token', help="compute resource's auth token")
        parser_add.add_argument('--user', default='pfcon', help="compute resource's user")
        parser_add.add_argument('--password', default='pfcon1234',
                                help="compute resource's password")
        parser_add.add_argument('--description', default='',
                                help="compute resource's description")
        parser_add.add_argument('--maxjobexecseconds', type=int,
                                help="compute resource's max job execution time in "
                                     "seconds")

        # create the parser for the "modify" command
        parser_modify = subparsers.add_parser('modify',
                                              help='modify existing compute resource')
        parser_modify.add_argument('computeresource', help="compute resource")
        parser_modify.add_argument('--name', help="compute resource's new name")
        parser_modify.add_argument('--url', help="compute resource's new url")
        parser_modify.add_argument('--auth_url', help="compute resource's auth url")
        parser_modify.add_argument('--auth_token', help="compute resource's auth token")
        parser_modify.add_argument('--user', help="compute resource's user")
        parser_modify.add_argument('--password', help="compute resource's password")
        parser_modify.add_argument('--description', default='',
                                   help="compute resource's new description")
        parser_modify.add_argument('--maxjobexecseconds', type=int,
                                   help="compute resource's new max job execution time "
                                        "in seconds")

        # create parser for the "register" command
        parser_register = subparsers.add_parser(
            'register', help='register a plugin with a compute resource')
        parser_register.add_argument(
            'computeresource', help="compute resource where the plugin's instances run")
        group = parser_register.add_mutually_exclusive_group()
        group.add_argument('--pluginname', help="plugin's name")
        group.add_argument('--pluginurl', help="plugin's url")
        parser_register.add_argument('--pluginversion', help="plugin's version. If not "
                                                        "provided then the latest "
                                                        "version is fetched.")
        parser_register.add_argument('--storetimeout', help="ChRIS store request timeout")

        # create the parser for the "remove" command
        parser_remove = subparsers.add_parser(
            'remove', help='remove an existing plugin or compute')
        parser_remove.add_argument('resourcename', choices=['plugin', 'compute'],
                                help="resource name")
        parser_remove.add_argument('id', help="resource id")

        self.parser = parser

    def add_compute_resource(self, name, url, auth_url, auth_token, user, passw, desc,
                             maxjobexecsec):
        """
        Add a new compute resource to the system.
        """
        # validate compute resource name
        try:
            cr = ComputeResource.objects.get(name=name)
        except ComputeResource.DoesNotExist:
            data = {'name': name, 'compute_url': url, 'compute_user': user,
                    'compute_password': passw, 'description': desc}
            if auth_url:
                data['compute_auth_url'] = auth_url
            if auth_token:
                data['compute_auth_token'] = auth_token
            if maxjobexecsec:
                data['max_job_exec_seconds'] = maxjobexecsec
            compute_resource_serializer = ComputeResourceSerializer(data=data)
            compute_resource_serializer.is_valid(raise_exception=True)
            cr = compute_resource_serializer.save()
        return cr

    def modify_compute_resource(self, name, new_name, url, auth_url, auth_token, user,
                                passw, desc, maxjobexecsec):
        """
        Modify an existing compute resource and add the current date as a new
        modification date.
        """
        try:
            cr = ComputeResource.objects.get(name=name)
        except ComputeResource.DoesNotExist:
            raise NameError("Compute resource '%s' does not exists" % name)
        data = {}
        if new_name:
            data['name'] = new_name
        if url:
            data['compute_url'] = url
        if auth_url:
            data['compute_auth_url'] = auth_url
        if auth_token:
            data['compute_auth_token'] = auth_token
        if user:
            data['compute_user'] = user
        if passw:
            data['compute_password'] = passw
        if desc:
            data['description'] = desc
        if maxjobexecsec:
            data['max_job_exec_seconds'] = maxjobexecsec
        if data:
            compute_resource_serializer = ComputeResourceSerializer(cr, data=data)
            compute_resource_serializer.is_valid(raise_exception=True)
            cr = compute_resource_serializer.save()
            cr.modification_date = timezone.now()
            cr.save()
        return cr

    def register_plugin(self, name, version, compute_name, timeout=30):
        """
        Register/add a new plugin identified by its name and version from the ChRIS store
        into the system.
        """
        try:
            cr = ComputeResource.objects.get(name=compute_name)
        except ComputeResource.DoesNotExist:
            raise NameError("Compute resource '%s' does not exists" % compute_name)
        plg_repr = None
        if not version:
            plg_repr = self.get_plugin_representation_from_store(name, None, timeout)
            version = plg_repr['version']
        try:
            plugin = self.get_plugin(name, version)
        except NameError:
            # plugin doesn't exist in the system, let's create it
            if not plg_repr:
                plg_repr = self.get_plugin_representation_from_store(name, version,
                                                                     timeout)
            return self._create_plugin(plg_repr, cr)
        # plugin already in the system, register it with cr if not already registered
        plugin.compute_resources.add(cr)
        return plugin

    def register_plugin_by_url(self, url, compute_name, timeout=30):
        """
        Register/add a new plugin identified by its ChRIS store url from the store into
        the system.
        """
        try:
            cr = ComputeResource.objects.get(name=compute_name)
        except ComputeResource.DoesNotExist:
            raise NameError("Compute resource '%s' does not exists" % compute_name)
        plg_repr = self.get_plugin_representation_from_store_by_url(url, timeout)
        name = plg_repr.get('name')
        version = plg_repr.get('version')
        try:
            plugin = self.get_plugin(name, version)
        except NameError:
            # plugin doesn't exist in the system, let's create it
            return self._create_plugin(plg_repr, cr)
        # plugin already in the system, register it with cr if not already registered
        plugin.compute_resources.add(cr)
        return plugin

    def _create_plugin(self, plg_repr, compute_resource):
        """
        Private utility method to register/add a new plugin into the system.
        """
        meta_data = {'name': plg_repr.pop('name'),
                     'title': plg_repr.pop('title', ''),
                     'stars': plg_repr.pop('stars', 0),
                     'public_repo': plg_repr.pop('public_repo', ''),
                     'license': plg_repr.pop('license', ''),
                     'type': plg_repr.pop('type'),
                     'icon': plg_repr.pop('icon', ''),
                     'category': plg_repr.pop('category', ''),
                     'authors': plg_repr.pop('authors', ''),
                     'documentation': plg_repr.pop('documentation', '')}
        parameters_data = plg_repr.pop('parameters')

        # check whether plugin_name does not exist and validate the plugin meta data
        try:
            meta = PluginMeta.objects.get(name=meta_data['name'])
            meta_serializer = PluginMetaSerializer(meta, data=meta_data)
        except PluginMeta.DoesNotExist:
            meta_serializer = PluginMetaSerializer(data=meta_data)
        meta_serializer.is_valid(raise_exception=True)

        # validate the plugin's versioned data
        plg_serializer = PluginSerializer(data=plg_repr)
        plg_serializer.is_valid(raise_exception=True)

        # check DB constraints
        plg_name = meta_serializer.validated_data.get('name')
        self.validate_name_version(plg_serializer.validated_data.get('version'), plg_name)
        self.validate_name_image(plg_serializer.validated_data.get('dock_image'),
                                 plg_name)

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

        pl_meta = meta_serializer.save()
        plugin = plg_serializer.save(meta=pl_meta, compute_resources=[compute_resource])
        for param_serializer_dict in parameters_serializers:
            param = param_serializer_dict['serializer'].save(plugin=plugin)
            if param_serializer_dict['default_serializer'] is not None:
                param_serializer_dict['default_serializer'].save(plugin_param=param)
        return plugin

    def remove_plugin(self, id):
        """
        Remove an existing/registered plugin from the system. All the associated plugin
        instances are cancelled before they are deleted by the DB CASCADE.
        """
        try:
            plugin = Plugin.objects.get(id=id)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find plugin with id '%s'" % id)
        for plg_inst in plugin.instances.all():
            plg_inst.cancel()
        if plugin.meta.plugins.count() == 1:
            plugin.meta.delete()  # the cascade deletes the plugin too
        else:
            plugin.delete()  # the cascade deletes the plugin instances too

    def remove_compute_resource(self, id):
        """
        Remove an existing compute resource from the system.
        """
        try:
            cr = ComputeResource.objects.get(id=id)
        except ComputeResource.DoesNotExist:
            raise NameError("Couldn't find compute resource with id '%s'" % id)
        cr.delete()

    def run(self, args=None):
        """
        Parse the arguments passed to the manager and perform the appropriate action.
        """
        options = self.parser.parse_args(args)
        if options.subparser_name == 'add':
            self.add_compute_resource(options.computeresource, options.url,
                                      options.auth_url, options.auth_token, options.user,
                                      options.password, options.description,
                                      options.maxjobexecseconds)
        elif options.subparser_name == 'modify':
            self.modify_compute_resource(options.computeresource, options.name,
                                         options.url, options.auth_url,
                                         options.auth_token, options.user,
                                         options.password, options.description,
                                         options.maxjobexecseconds)
        elif options.subparser_name == 'register':
            if options.pluginurl:
                self.register_plugin_by_url(options.pluginurl, options.computeresource,
                                            options.storetimeout)
            elif options.pluginname:
                self.register_plugin(options.pluginname, options.pluginversion,
                                     options.computeresource, options.storetimeout)
            else:
                raise ArgumentError('Either a name or a url must be provided')
        elif options.subparser_name == 'remove':
            if options.resourcename == 'plugin':
                self.remove_plugin(options.id)
            if options.resourcename == 'compute':
                self.remove_compute_resource(options.id)

    @staticmethod
    def validate_name_version(version, name):
        """
        Custom method to check if plugin name and version are unique together.
        """
        try:
            Plugin.objects.get(meta__name=name, version=version)
        except Plugin.DoesNotExist:
            pass
        else:
            msg = "Plugin with name %s and version %s already exists" % (name, version)
            raise ValueError(msg)

    @staticmethod
    def validate_name_image(dock_image, name):
        """
        Custom method to check if plugin name and docker image are unique together.
        """
        try:
            Plugin.objects.get(meta__name=name, dock_image=dock_image)
        except Plugin.DoesNotExist:
            pass
        else:
            msg = "Docker image %s already used in a previous version of plugin with " \
                  "name %s" % (dock_image, name)
            raise ValueError(msg)

    @staticmethod
    def get_plugin_representation_from_store(name, version=None, timeout=30):
        """
        Get a plugin app representation from the ChRIS store.
        """
        store_url = settings.CHRIS_STORE_URL
        store_client = StoreClient(store_url, None, None, timeout)
        plg = store_client.get_plugin(name, version)
        plg['parameters'] = PluginManager.get_plugin_parameters_from_store(plg['id'],
                                                                           timeout)
        return plg

    @staticmethod
    def get_plugin_representation_from_store_by_url(url, timeout=30):
        """
        Get a plugin app representation from the ChRIS store given the url of the plugin.
        """
        store_url = settings.CHRIS_STORE_URL
        store_client = StoreClient(store_url, None, None, timeout)
        res = store_client.get(url)
        result = store_client.get_data_from_collection(res)

        if not result['data']:
            raise NameError(f"Could not find plugin with url '{url}'")

        plg = result['data'][0]
        parameters_url = res.items[0].links.get(rel='parameters').href
        plg['parameters'] = PluginManager.get_plugin_parameters_from_url(parameters_url, timeout)
        return plg

    @staticmethod
    def get_plugin(name, version):
        """
        Get an existing plugin.
        """
        try:
            plg_meta = PluginMeta.objects.get(name=name)
        except PluginMeta.DoesNotExist:
            raise NameError("Couldn't find any plugin named '%s' in the system" % name)
        try:
            plugin = Plugin.objects.get(meta=plg_meta, version=version)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find plugin '%s' with version '%s' in the system" %
                            (name, version))
        return plugin

    @staticmethod
    def get_plugin_parameters_from_store(plg_id, timeout=30):
        """
        Get a plugin's parameters representation from the ChRIS store.
        """
        store_url = settings.CHRIS_STORE_URL
        store_client = StoreClient(store_url, None, None, timeout)
        parameters = []
        offset = 0
        limit = 50
        while True:
            result = store_client.get_plugin_parameters(plg_id, {'limit': limit,
                                                                 'offset': offset})
            parameters.extend(result['data'])
            offset += limit
            if not result['hasNextPage']: break
        return parameters

    @staticmethod
    def get_plugin_parameters_from_url(parameters_url, timeout=30):
        """
        Get a plugin's parameters representation from a ChRIS store by URL.
        """
        store_url = settings.CHRIS_STORE_URL
        store_client = StoreClient(store_url, None, None, timeout)
        parameters = []
        offset = 0
        limit = 50
        while True:
            res = store_client.get(parameters_url, {'limit': limit, 'offset': offset})
            result = store_client.get_data_from_collection(res)
            parameters.extend(result['data'])
            offset += limit
            if not result['hasNextPage']: break
        return parameters


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    manager.run()
