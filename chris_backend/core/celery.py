
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
    'plugininstances.tasks.sum': {'queue': 'main'},
    'plugininstances.tasks.check_plugin_instance_exec_status': {'queue': 'main'},
    'plugininstances.tasks.run_plugin_instance': {'queue': 'main'},
}
app.conf.update(task_routes=task_routes)

# use logging settings in Django settings
@setup_logging.connect
def config_loggers(*args, **kwags):
    dictConfig(settings.LOGGING)

# example task that is passed info about itself
@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
