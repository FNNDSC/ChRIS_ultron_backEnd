"""
Plugin manager module that provides functionality to add and delete plugins to the
plugins django app. The last modification date of a plugin can also be registered.
"""


from importlib import import_module
from argparse import ArgumentParser
from inspect import getmembers

from django.utils import timezone

from plugins.models import Plugin, PluginParameter 
from .plugin import PluginService

__version__ = "1.0.0"


class PluginManager(object):

    def __init__(self):
        parser = ArgumentParser(description='Manage plugins')
        parser.add_argument("name", help="plugin name")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-a", "--add", action="store_true", help="add a new plugin")
        group.add_argument("-r", "--remove", action="store_true",
                           help="remove an existing plugin")
        group.add_argument("-m", "--modify", action="store_true",
                           help="register now as modification date")
        self.parser = parser

    def _get_plugin_service_class(self, name):
        """
        Internal method to get a plugin's class name given the plugin's name.
        """
        # a name.name plugins' package.module structure is assumed 
        plugin_service_module_name = "%s.%s" % (name, name)
        try:
            plugin_service_module = import_module(plugin_service_module_name)
        except ImportError as e:
            raise ImportError("Error: failed to import module %s. Check if the \
                 plugin's package was added." % plugin_service_module_name)
        else:
            for member in getmembers(plugin_sevice_module):
                if issubclass(member[1], PluginService):
                    return member[1]
        
    def run(self, args=None):
        """
        Parse the arguments passed to the manager and perform the appropriate action.
        """
        options = self.parser.parse_args(args)
        if options.add:
            self.add_plugin(options.name)
        elif options.remove:
            self.remove_plugin(options.name)
        elif options.modify:
            self.register_plugin_modification(options.name)
        self.args = options
        
    def add_plugin(self, name):
        """
        Register/add a new plugin.
        """
        plugin_service_class = self._get_plugin_service_class(name)
        plugin_service = plugin_service_class()
        plugin_repr = plugin_service.getJSONRepresentation()
        # add plugin to the db
        plugin = Plugin()
        plugin.name = plugin_repr.name
        plugin.type = plugin_repr.type
        plugin.save()
        for params in plugin_repr.parameters:
            # add plugin parameter to the db
            plugin_param = PluginParameter()
            plugin_param.plugin = plugin
            plugin_param.name = params.name
            plugin_param.type = params.type
            plugin_param.optional = params.optional
            plugin_param.save()
                  
    def remove_plugin(self, name):
        """
        Remove an existing plugin.
        """
        plugin = Plugin.objects.get(name=name)
        plugin.delete()

    def register_plugin_modification(self, name):
        """
        Register current date as a new plugin modification date.
        """
        plugin = Plugin.objects.get(name=name)
        plugin.modification_date = timezone.now()
        plugin.save()


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    try:
        manager.run()
    except Exception as e:
        print(e)

