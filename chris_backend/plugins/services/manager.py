"""
Plugin manager module that provides functionality to add, modify and delete plugins to the
plugins django app. There is also functionality to run and check the execution status of a
plugin's app.
"""

import os, sys
from importlib import import_module
from argparse import ArgumentParser
from inspect import getmembers

import time

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    # django needs to be loaded (eg. when this script is run from the command line)
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django
    django.setup()

from django.utils import timezone

from plugins.models import Plugin, PluginParameter, TYPES, PLUGIN_TYPE_CHOICES, STATUS_TYPES
from plugins.services import charm

# define the python package for the plugins' apps
_APPS_PACKAGE = 'plugins.services'


class PluginManager(object):

    def __init__(self):
        parser = ArgumentParser(description='Manage plugins')
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-a", "--add", help="add a new plugin", metavar='PluginName')
        group.add_argument("-r", "--remove", help="remove an existing plugin", metavar='PluginName')
        group.add_argument("-m", "--modify", help="register NOW as modification date", metavar='PluginName')
        self.parser = parser

        # Debug specifications
        self.b_quiet            = False
        self.b_useDebug         = True
        self.str_debugFile      = '%s/tmp/debug-charm.log' % os.environ['HOME']

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

    def get_plugin_app_representation(self, name):
        """
        Get a plugin's app representation given the plugin's name.
        """
        plugin_app_class = self._get_plugin_app_class(name)
        app = plugin_app_class()
        app_repr = app.get_json_representation()
        plugin_types = [plg_type[0] for plg_type in PLUGIN_TYPE_CHOICES]
        if app_repr['type'] not in plugin_types:
            raise ValueError("A plugin's TYPE can only be any of %s. Please fix it in %s"
                             % (plugin_types, plugin_app_class))
        return app_repr

    def _save_plugin_param(self, plugin, param):
        """
        Internal method to save a plugin parameter into the DB.
        """
        # add plugin parameter to the db
        plugin_param = PluginParameter()
        plugin_param.plugin = plugin
        plugin_param.name = param['name']
        plg_type = param['type']
        plugin_param.type = [key for key in TYPES if TYPES[key]==plg_type][0]
        plugin_param.optional = param['optional']
        if param['default'] is None:
            plugin_param.default = ""
        else:
            plugin_param.default = str(param['default'])
        plugin_param.help = param['help']
        plugin_param.save()
        
    def add_plugin(self, name):
        """
        Register/add a new plugin to the system.
        """
        # check wether the plugin already exist
        existing_plugin_names = [plugin.name for plugin in Plugin.objects.all()]
        if name in existing_plugin_names:
            raise ValueError("Plugin '%s' already exists in the system" % name)
        # get representation from the corresponding app
        app_repr = self.get_plugin_app_representation(name)
        # add plugin to the db
        plugin = Plugin()
        plugin.name = name
        plugin.type = app_repr['type']
        plugin.save()
        # add plugin's parameters to the db
        params = app_repr['parameters']
        for param in params:
            self._save_plugin_param(plugin, param)

    def get_plugin(self, name):
        """
        Get an existing/registered plugin.
        """
        try:
            plugin = Plugin.objects.get(name=name)
        except Plugin.DoesNotExist:
            raise NameError("Couldn't find '%s' plugin in the system" % name)
        return plugin
                  
    def remove_plugin(self, name):
        """
        Remove an existing/registered plugin from the system.
        """
        plugin = self.get_plugin(name)
        plugin.delete()

    def register_plugin_app_modification(self, name):
        """
        Register/add new parameters to a plugin from the corresponding plugin's app.
        Also add the current date as a new plugin modification date.
        """
        plugin = self.get_plugin(name)
        # get the new representation from the corresponding app
        app_repr = self.get_plugin_app_representation(name)
        new_params = app_repr['parameters']
        existing_param_names = [parameter.name for parameter in plugin.parameters.all()]
        for param in new_params:
            if param['name'] not in existing_param_names:
                self._save_plugin_param(plugin, param)
        plugin.modification_date = timezone.now()
        plugin.save()

    def run(self, args=None):
        """
        Parse the arguments passed to the manager and perform the appropriate action.
        """
        options = self.parser.parse_args(args)
        if options.add:
            self.add_plugin(options.add)
        elif options.remove:
            self.remove_plugin(options.remove)
        elif options.modify:
            self.register_plugin_app_modification(options.modify)
        self.args = options

    def run_plugin_app(self, plugin_inst, parameter_dict, **kwargs):
        """
        Run a plugin's app.
        """

        for k, v in kwargs.items():
            if k == 'useDebug':     self.b_useDebug     = v
            if k == 'debugFile':    self.str_debugFile  = v
            if k == 'quiet':        self.b_quiet        = v

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

        # run the app via the pman server...
        chris2pman   = charm.Charm(
            app_args    = app_args,
            d_args      = parameter_dict,
            plugin_inst = plugin_inst,
            plugin_repr = plugin_repr,
            app         = app,
            inputdir    = inputdir,
            outputdir   = outputdir
        )

        #
        # Some dev notes...
        #
        # To run the app directly on the CLI via 'crunner', use
        #         chris2pman.app_manage(method = 'crunner')
        # Note that this call blocks until the CLI process returns.
        #
        # To run the app 'internally', i.e. not as a CLI but by calling the app run() method directly in python:
        #         chris2pman.app_manage(method = 'internal')
        # Again, this blocks on the app run() method.
        #
        # The call to "method = 'pman'" does not block but dispatches to a completely asynchronous external
        # pman server process and returns immediately. The check on output is performed when views are updated,
        # again by talking to the pman server.
        #

        chris2pman.app_manage(method = 'pman')

        #
        # Finally, any output files generated by the app need to be registered in the DB.
        # This is handled by the app_manage() method, and in asynchronous cases (i.e. via the pman server)
        # registration occurs via a call to the overloaded retrieve() method in PluginInstanceDetail in
        # plugins/views.py.
        #

    def startup_apps_exec_server(self, **kwargs):
        """
        Shutdown a pman instance
        :return:
        """

        # pudb.set_trace()

        chris2pman   = charm.Charm(**kwargs)
        chris2pman.app_pman_checkIfAvailable()
        # Wait a bit for transients
        time.sleep(5)

    def shutdown_apps_exec_server(self, **kwargs):
        """
        Shutdown a pman instance
        :return:
        """
        chris2pman   = charm.Charm(**kwargs)
        chris2pman.app_pman_shutdown()
        # Wait a bit for transients
        time.sleep(5)

    def check_plugin_app_exec_status(self, plugin_inst, **kwargs):
        """
        Check a plugin's app execution status. It connects to pman to determine job
        status.
        """
        chris2pman   = charm.Charm(
            plugin_inst = plugin_inst,
            **kwargs
        )
        chris2pman.app_statusCheckAndRegister()        


# ENTRYPOINT
if __name__ == "__main__":
    manager = PluginManager()
    manager.run()


