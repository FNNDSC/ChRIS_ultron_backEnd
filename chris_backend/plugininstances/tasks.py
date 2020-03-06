
from celery import shared_task

from .models import PluginInstance


@shared_task
def check_plugin_instance_exec_status(plg_inst_id):
    #from celery.contrib import rdb;rdb.set_trace()
    plugin_inst = PluginInstance.objects.get(pk=plg_inst_id)
    plugin_inst.check_exec_status()


@shared_task  # toy task for testing celery stuff
def sum(x, y):
    return x + y