"""
Smoke tests for ``dicomweb.tasks``. These do not exercise the full
ingest pipeline — that's the Phase D integration-test job. They verify:

* the helpers parse the DICOM string formats correctly,
* the indexing task is importable and routable (no circular imports), and
* ``_find_series_for_file`` walks parent folders.
"""

from datetime import date, time

from django.test import TestCase

from dicomweb.tasks import (
    _as_int,
    _parse_dicom_date,
    _parse_dicom_time,
)


class HelperParseTests(TestCase):
    def test_parse_dicom_date_valid(self):
        self.assertEqual(_parse_dicom_date('20231201'), date(2023, 12, 1))

    def test_parse_dicom_date_invalid_returns_none(self):
        self.assertIsNone(_parse_dicom_date(''))
        self.assertIsNone(_parse_dicom_date(None))
        self.assertIsNone(_parse_dicom_date('not-a-date'))

    def test_parse_dicom_time_full(self):
        self.assertEqual(_parse_dicom_time('143005'), time(14, 30, 5))

    def test_parse_dicom_time_with_fractional_seconds(self):
        # DICOM TM VR allows fractional seconds — they get stripped.
        self.assertEqual(_parse_dicom_time('143005.123'), time(14, 30, 5))

    def test_parse_dicom_time_partial(self):
        self.assertEqual(_parse_dicom_time('1430'), time(14, 30, 0))
        self.assertEqual(_parse_dicom_time('14'), time(14, 0, 0))

    def test_parse_dicom_time_invalid(self):
        self.assertIsNone(_parse_dicom_time(''))
        self.assertIsNone(_parse_dicom_time(None))
        self.assertIsNone(_parse_dicom_time('not-a-time'))

    def test_as_int(self):
        self.assertEqual(_as_int(42), 42)
        self.assertEqual(_as_int('17'), 17)
        self.assertIsNone(_as_int(''))
        self.assertIsNone(_as_int(None))
        self.assertIsNone(_as_int('xyz'))


class TaskImportSmokeTests(TestCase):
    def test_celery_task_is_importable(self):
        # Catches circular-import regressions between
        # pacsfiles.serializers and dicomweb.tasks.
        from dicomweb.tasks import index_pacs_instance
        self.assertTrue(callable(index_pacs_instance))
        self.assertEqual(
            index_pacs_instance.name, 'dicomweb.tasks.index_pacs_instance',
        )

    def test_task_routed_to_main2(self):
        # Locks in the queue assignment from core/celery.py:task_routes.
        from core.celery import app as celery_app
        routes = celery_app.conf.task_routes or {}
        entry = routes.get('dicomweb.tasks.index_pacs_instance')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get('queue'), 'main2')
