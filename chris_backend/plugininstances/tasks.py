
import logging
from functools import wraps

from django.db.models import Q

from celery import shared_task

from .models import PluginInstance
from .services.manager import PluginInstanceManager


logger = logging.getLogger(__name__)


def skip_if_running(f):
    """
    This decorator is supposed to ensure that a task is only running once across all
    workers.
    https://stackoverflow.com/questions/20894771/celery-beat-limit-to-single-task-instance-at-a-time
    """
    task_name = f'{f.__module__}.{f.__name__}'
    @wraps(f)
    def wrapped(self, *args, **kwargs):
        workers = self.app.control.inspect().active()
        for worker, tasks in workers.items():
            for task in tasks:
                if (task_name == task['name'] and tuple(args) == tuple(task['args']) and
                        kwargs == task['kwargs'] and self.request.id != task['id']):
                    logger.info('task %s (%s, %s) is running on %s, skipping',
                                task_name, args, kwargs, worker)
                    return None
        return f(self, *args, **kwargs)
    return wrapped


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


@shared_task(bind=True)
@skip_if_running
def run_waiting_for_previous_plugin_instances(self):  # task is passed info about itself
    """
    Run the app corresponding to all plugin instances in 'waitingForPrevious' DB status
    and whom previous plugin instance is in 'finishedSuccessfully' DB status.
    """
    instances = PluginInstance.objects.filter(status='waitingForPrevious',
                                              previous__status='finishedSuccessfully')
    for plg_inst in instances:
        plg_inst.status = 'scheduled'
        plg_inst.save()
        run_plugin_instance.delay(plg_inst.id)  # call async task


@shared_task
def check_started_plugin_instances_exec_status():
    """
    Check the execution status of the apps corresponding to all the plugin instances
    with 'started' DB status.
    """
    instances = PluginInstance.objects.filter(status='started')
    for plg_inst in instances:
        check_plugin_instance_exec_status.delay(plg_inst.id)  # call async task


@shared_task
def cancel_waiting_for_previous_plugin_instances():
    """
    Cancel the app corresponding to all plugin instances in 'waitingForPrevious' DB
    status when their previous plugin instance is in either 'finishedWithError' or
    'cancelled' DB status.
    """
    lookup = Q(previous__status='finishedWithError') | Q(previous__status='cancelled')
    instances = PluginInstance.objects.filter(status='waitingForPrevious').filter(lookup)
    for plg_inst in instances:
        plg_inst.status = 'cancelled'
        plg_inst.save()


@shared_task  # toy task for testing celery stuff
def sum(x, y):
    return x + y
