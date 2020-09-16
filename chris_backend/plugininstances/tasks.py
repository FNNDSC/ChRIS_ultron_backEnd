
from celery import shared_task

from .models import PluginInstance


@shared_task
def run_plugin_instance(plg_inst_id):
    """
    Run the app corresponding to this plugin instance.
    """
    #from celery.contrib import rdb;rdb.set_trace()
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plugin_inst.run()


@shared_task
def check_plugin_instance_exec_status(plg_inst_id):
    """
    Check the execution status of the app corresponding to this plugin instance.
    """
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plugin_inst.check_exec_status()


@shared_task
def check_started_plugin_instances_exec_status():
    """
    Check the execution status of the apps corresponding to all the plugin instances
    with 'started' DB status.
    """
    instances = PluginInstance.objects.filter(status='started')
    for plugin_inst in instances:
        check_plugin_instance_exec_status.delay(plugin_inst.id)  # call async task


@shared_task  # toy task for testing celery stuff
def sum(x, y):
    return x + y
