from django.apps import AppConfig


class PluginsConfig(AppConfig):
    name = 'plugins'

    def ready(self):
        from plugins import handlers

