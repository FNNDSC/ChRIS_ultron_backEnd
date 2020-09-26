
from django.db.models import Q

from celery import shared_task

from .models import PluginInstance
from .services.manager import PluginInstanceManager


@shared_task
def run_plugin_instance(plg_inst_id):
    """
    Run the app corresponding to this plugin instance.
    """
    #from celery.contrib import rdb;rdb.set_trace()
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plg_inst_manager = PluginInstanceManager(plugin_inst)
    plg_inst_manager.run_plugin_instance_app()


@shared_task
def check_plugin_instance_exec_status(plg_inst_id):
    """
    Check the execution status of the app corresponding to this plugin instance.
    """
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plg_inst_manager = PluginInstanceManager(plugin_inst)
    plg_inst_manager.check_plugin_instance_app_exec_status()


@shared_task
def cancel_plugin_instance(plg_inst_id):
    """
    Cancel the execution of the app corresponding to this plugin instance.
    """
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plg_inst_manager = PluginInstanceManager(plugin_inst)
    plg_inst_manager.cancel_plugin_instance_app_exec()


@shared_task
def check_scheduled_plugin_instances_exec_status():
    """
    Check the execution status of the apps corresponding to all the plugin instances
    with 'started' or 'waitingForPrevious' DB status.
    """
    lookup = Q(status='started') | Q(status='waitingForPrevious')
    instances = PluginInstance.objects.filter(lookup)
    for plg_inst in instances:
        if plg_inst.status == 'waitingForPrevious':
            if plg_inst.previous.status == 'finishedSuccessfully':
                plg_inst.status = 'scheduled'
                plg_inst.save()
                run_plugin_instance.delay(plg_inst.id)  # call async task
            elif plg_inst.previous.status in ('finishedWithError', 'cancelled'):
                plg_inst.status = 'cancelled'
                plg_inst.save()
        else:
            check_plugin_instance_exec_status.delay(plg_inst.id)  # call async task


@shared_task  # toy task for testing celery stuff
def sum(x, y):
    return x + y
