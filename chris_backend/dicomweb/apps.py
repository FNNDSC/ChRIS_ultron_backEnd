from django.apps import AppConfig


class DicomwebConfig(AppConfig):
    name = 'dicomweb'

    def ready(self):
        # Register the PACSStudy counter-maintenance signal receivers.
        from . import signals  # noqa: F401
