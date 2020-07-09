"""
Pipeline instance manager module that provides functionality to run and check the
execution status of a pipeline instance.
"""

import time

from django.conf import settings


class PipelineInstanceManager(object):

    @staticmethod
    def run_pipeline_instance(pipeline_inst, parameter_dict):
        """
        Run a pipeline instance.
        """
        pass

    @staticmethod
    def check_pipeline_instance_exec_status(plugin_inst):
        """
        Check a pipeline instance execution status. It connects to the remote
        service to determine pipeline's jobs status.
        """
        pass

    @staticmethod
    def cancel_pipeline_instance_exec(plugin_inst):
        """
        Cancel a pipeline instance execution. It connects to the remote service to
        cancel pipeline's jobs.
        """
        pass
