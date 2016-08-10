"""
Plugin manager module that provides functionality to add and delete plugins to the
plugins django app. The last modification date of a plugin can also be registered.
"""

import os, sys
from importlib import import_module
from argparse import ArgumentParser
from inspect import getmembers

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # django needs to be loaded (eg. when this script is run from the command line)
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.utils import timezone

from plugins.models import Plugin, PluginParameter, TYPES

_APPS_PACKAGE = 'plugins.services'


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

    def _get_plugin_app_class(self, name):
        """
        Internal method to get a plugin's app class name given the plugin's name.
        """
        # an _apps_package_name.name.name package structure is assumed for the plugin app
        plugin_app_module_name = "%s.%s.%s" % (_APPS_PACKAGE, name, name)
        try:
            plugin_app_module = import_module(plugin_app_module_name)
        except ImportError as e:
            raise ImportError("Error: failed to import module %s. Check if the \
                 plugin's app package was added." % plugin_app_module_name)
        else:
            for member in getmembers(plugin_app_module):
                if (hasattr(member[1], 'run') and
                    hasattr(member[1], 'define_parameters') and
                    hasattr(member[1], 'get_json_representation') and
                    not (member[0]=='ChrisApp')):
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
        plugin_app_class = self._get_plugin_app_class(name)
        app = plugin_app_class()
        plugin_repr = app.get_json_representation()
        # add plugin to the db
        plugin = Plugin()
        plugin.name = name
        plugin.type = plugin_repr['type']
        plugin.save()
        params = plugin_repr['parameters']
        for param in params:
            # add plugin parameter to the db
            plugin_param = PluginParameter()
            plugin_param.plugin = plugin
            plugin_param.name = param['name']
            plg_type = param['type']
            plugin_param.type = [key for key in TYPES if TYPES[key]==plg_type][0]
            plugin_param.optional = param['optional']
            plugin_param.save()
                  
    def remove_plugin(self, name):
        """
        Remove an existing plugin.
        """
        try:
            plugin = Plugin.objects.get(name=name)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find %s plugin in the system" % name)
        plugin.delete()

    def register_plugin_modification(self, name):
        """
        Register current date as a new plugin modification date.
        """
        try:
            plugin = Plugin.objects.get(name=name)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find %s plugin in the system" % name)
        plugin.modification_date = timezone.now()
        plugin.save()

    def run_plugin_app(self, plugin_inst, parameter_dict):
        """
        Run a plugin's app.
        """
        # instantiate the plugin's app
        plugin_app_class = self._get_plugin_app_class(plugin_inst.plugin.name)
        app = plugin_app_class()
        plugin_repr = app.get_json_representation()
        # get input dir
        inputdir = ""
        if plugin_inst.previous:
            inputdir = plugin_inst.previous.get_output_path()
        # get output dir
        outputdir = plugin_inst.get_output_path()
        app_args = []
        # append input dir to app's argument list (only for ds plugins)
        if plugin_repr['type'] == 'ds' and inputdir:
            app_args.append(inputdir)
        # append output dir to app's argument list
        app_args.append(outputdir)
        # append options file path (options are saved to this file) 
        app_args.append("--saveopts")
        app_args.append(os.path.join(os.path.dirname(outputdir), "opts.json"))
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
        # run the app with all the arguments
        app.launch(app_args)
        # register output files with the system
        plugin_inst.register_output_files()
                


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    manager.run()


