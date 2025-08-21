
import os
from logging.config import dictConfig
from django.conf import settings

from celery import Celery
from celery.signals import setup_logging

# set the default Django settings module for the 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('core')

# using a string here means the worker doesn't have to serialize
# the configuration object to child processes
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# load task modules from all registered Django app configs.
app.autodiscover_tasks()

# define the the queue for each task
# the default 'celery' queue is exclusively used for the automated tests
task_routes = {
    'plugininstances.tasks.sum': {'queue': 'main1'},
    'plugininstances.tasks.run_plugin_instance': {'queue': 'main1'},
    'plugininstances.tasks.check_plugin_instance_exec_status': {'queue': 'main2'},
    'plugininstances.tasks.cancel_plugin_instance': {'queue': 'main2'},
    'plugininstances.tasks.delete_plugin_instance_job_from_remote': {'queue': 'main2'},
    'plugininstances.tasks.schedule_waiting_plugin_instances':
        {'queue': 'periodic'},
    'plugininstances.tasks.check_started_plugin_instances_exec_status':
        {'queue': 'periodic'},
    'plugininstances.tasks.cancel_waiting_plugin_instances':
        {'queue': 'periodic'},
    'plugininstances.tasks.cancel_plugin_instances_stuck_in_lock':
        {'queue': 'periodic'},
    'plugininstances.tasks.delete_plugin_instances_jobs_from_remote':
        {'queue': 'periodic'},
    'pacsfiles.tasks.send_pacs_query': {'queue': 'main2'},
    'pacsfiles.tasks.register_pacs_series': {'queue': 'main2'}
}
app.conf.update(task_routes=task_routes)


# Note: django settings cannot be used here for not-understood module dependency resasons.
POLL_INTERVAL = float(os.getenv('CUBE_CELERY_POLL_INTERVAL', '5.0'))
"""
How often to poll for plugin instance status changes.
"""

# setup periodic tasks
app.conf.beat_schedule = {
    'schedule-waiting-plugin-instances-every-45-seconds': {
        'task': 'plugininstances.tasks.schedule_waiting_plugin_instances',
        'schedule': POLL_INTERVAL,
    },
    'check-started-plugin-instances-exec-status-every-30-seconds': {
        'task': 'plugininstances.tasks.check_started_plugin_instances_exec_status',
        'schedule': POLL_INTERVAL,
    },
    'cancel-waiting-plugin-instances-every-30-seconds': {
        'task': 'plugininstances.tasks.cancel_waiting_plugin_instances',
        'schedule': POLL_INTERVAL,
    },
    'cancel-plugin-instances-stuck-in-lock-every-7200-seconds': {
        'task': 'plugininstances.tasks.cancel_plugin_instances_stuck_in_lock',
        'schedule': 7200.0,
    },
    'delete-plugin-instances-jobs-from-remote-every-7200-seconds': {
        'task': 'plugininstances.tasks.delete_plugin_instances_jobs_from_remote',
        'schedule': 7200.0,
    },
}

# use logging settings in Django settings
@setup_logging.connect
def config_loggers(*args, **kwags):
    dictConfig(settings.LOGGING)

# example task that is passed info about itself
@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
