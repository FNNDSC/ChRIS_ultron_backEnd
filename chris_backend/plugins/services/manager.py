"""
Plugin manager module that provides functionality to add and delete plugins to the
plugins app. The last modification date of a plugin can also be registered.
"""


from importlib import import_module
from argparse import ArgumentParser
from inspect import getmembers

from plugins import models

form .plugin import AbstractPlugin

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

    def _get_plugin_class(self, name):
            module_name = "%s.%s" % (name, name)
        try:
            plugin_module = import_module(module_name)
        except ImportError as e:
            raise ImportError("Error: failed to import module %s. Check if the \
                 plugin's package was added." % module_name)
        else:
            for member in getmembers(plugin_module):
                if issubclass(member[1], AbstractPlugin):
                    return member[1]
        return None
        
    def run(self, args=None):
        options = self.parser.parse_args(args)
        if options.add:
            self.add_plugin(options.name)
        elif options.remove:
            self.remove_plugin(options.name)
        elif options.modify:
            self.register_plugin_modification(options.name)
        self.args = options
        
    def add_plugin(self, name):
        plugin_class = self._get_plugin_class(name)
        if (plugin_class):
            plugin = plugin_class()
            plugin_repr = plugin.getJSON()
            # add plugin to the db
            db_pugin = models.Plugin()
            db_pugin.name = plugin_repr.name
            db_pugin.type = plugin_repr.type
            db_pugin.save()
            for params in plugin_repr.parameters:
                # add plugin parameter to the db
                db_plugin_param = models.PluginParameter()
                db_plugin_param.plugin = db_pugin
                db_plugin_param.name = params.name
                db_plugin_param.type = params.type
                db_plugin_param.optional = params.optional
                db_plugin_param.save()
        else:
            raise AttributeError("No subclass of plugin.AbstractPlugin was \
                 found in plugin module")
                     
    def remove_plugin(self, name):
        pass

    def register_plugin_modification(self, name):
        pass



# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    try:
        manager.run()
    except Exception as e:
        print(e)

