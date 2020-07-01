"""
Plugin app manager module that provides functionality to run and check the execution
status of a plugin app.
"""

import time

from django.conf import settings


class PluginAppManager(object):

    @staticmethod
    def run_pipeline_instance(pipeline_inst, parameter_dict):
        """
        Run a pipeline instance.
        """
        pass

    @staticmethod
    def check_pipeline_inst_exec_status(plugin_inst):
        """
        Check a pipeline instance execution status. It connects to the remote
        service to determine job status.
        """
        pass

    @staticmethod
    def cancel_plugin_app_exec(plugin_inst):
        """
        Cancel a pipeline instance app execution. It connects to the remote
        service to cancel job.
        """
        pass
