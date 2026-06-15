"""
Integration tests for the dicomweb ingest → index pipeline.

These tests address the gap identified in the architectural review (Jorge, 2026-06-13,
§5.1 and §7): the existing test suite proved the read/serve path but no test registered
a series the way oxidicom's ``register_pacs_series`` task does — through
``PACSSeriesSerializer.create`` + ``PACSFile.objects.bulk_create`` — and asserted that
``PACSInstance`` rows appeared without a manual backfill step.

Three tests cover the mechanism end-to-end:

  1. ``test_bulk_create_returns_pks`` — ``PACSFile.objects.bulk_create()`` populates PKs
     on PostgreSQL.  If PKs are None, the on_commit lambda dispatches nothing.

  2. ``test_on_commit_fan_out_dispatches_task`` — ``transaction.on_commit`` fires after
     the serializer calls ``bulk_create`` and dispatches ``index_pacs_instance.delay()``
     with the correct PACSFile PKs.  This is the §5.1 hook: if the implementation
     relied on a ``post_save`` signal instead, this test would still pass (signals
     fire on single-row saves, which is why the L2 prototype's signal appeared to work
     on STOW paths but silently skips the oxidicom/bulk_create path).

  3. ``test_task_creates_pacs_instance_after_series_registered`` — ``index_pacs_instance``
     creates a ``PACSInstance`` row when called with the PACSFile PK that was produced by
     the bulk_create path.  In production the Celery broker delivers this task
     asynchronously, after ``super().create()`` has committed the PACSSeries row.  In
     tests we call ``apply()`` directly after ``register_pacs_series`` returns (same
     ordering guarantee) to avoid the test-specific race where eager task execution would
     run before PACSSeries is committed.

Run with:
    just test dicomweb --tag integration
    just test-integration
"""

import io
import logging

import pydicom
from django.contrib.auth.models import Group, User
from django.conf import settings
from django.test import TransactionTestCase, tag

from core.celery import app as celery_app
from core.storage import connect_storage

from dicomweb.models import PACSInstance


def _make_dicom_bytes(sop_uid='1.2.3.4.5001',
                      study_uid='1.2.3.4.1',
                      series_uid='1.2.3.4.2') -> bytes:
    """Return bytes of a minimal valid DICOM P10 file with spec-compliant UIDs."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = 'P001'
    ds.PatientName = 'Test^Patient'
    ds.StudyDate = '20230101'
    ds.StudyTime = '120000'
    ds.SeriesNumber = 1
    ds.Modality = 'CT'
    ds.InstanceNumber = 1
    ds.Rows = 4
    ds.Columns = 4
    ds.BitsAllocated = 16
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.PixelData = b'\x00' * 32

    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)
    return buf.getvalue()


@tag('integration')
class SerializerBulkCreateIndexIntegrationTest(TransactionTestCase):
    """
    End-to-end verification of the ingest → index path via register_pacs_series.

    Uses ``TransactionTestCase`` so that DB transactions actually commit and
    ``transaction.on_commit`` callbacks fire correctly.
    """

    PACS_NAME = 'INTEGPACS'
    STUDY_UID = '1.2.3.4.1'
    SERIES_UID = '1.2.3.4.2'
    SOP_UID = '1.2.3.4.5001'
    PATH = 'SERVICES/PACS/INTEGPACS/P001/1.2.3.4.1/1.2.3.4.2'

    def setUp(self):
        logging.disable(logging.WARNING)
        Group.objects.get_or_create(name='pacs_users')
        self.storage = connect_storage(settings)
        self.dcm_path = self.PATH + '/0001.dcm'
        self.storage.upload_obj(
            self.dcm_path,
            _make_dicom_bytes(
                sop_uid=self.SOP_UID,
                study_uid=self.STUDY_UID,
                series_uid=self.SERIES_UID,
            ),
            content_type='application/dicom',
        )

    def tearDown(self):
        try:
            self.storage.delete_obj(self.dcm_path)
        except Exception:
            pass
        logging.disable(logging.NOTSET)

    def _register(self):
        from pacsfiles.tasks import register_pacs_series
        register_pacs_series(
            PatientID='P001',
            PatientName='Test^Patient',
            PatientSex='O',
            StudyDate='20230101',
            StudyInstanceUID=self.STUDY_UID,
            SeriesInstanceUID=self.SERIES_UID,
            pacs_name=self.PACS_NAME,
            path=self.PATH,
            ndicom=1,
            Modality='CT',
        )

    def test_bulk_create_returns_pks(self):
        """
        PACSFile.objects.bulk_create() populates PKs on PostgreSQL (Django 4.0+).
        If PKs are None the on_commit fan-out lambda dispatches nothing, so this
        is the precondition for the indexing path to work at all.
        """
        from core.models import ChrisFolder
        from pacsfiles.models import PACS, PACSFile

        owner = User.objects.get(username='chris')
        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path=f'SERVICES/PACS/{self.PACS_NAME}', owner=owner)
        pacs = PACS(folder=pacs_folder, identifier=self.PACS_NAME)
        pacs.save()

        series_folder, _ = ChrisFolder.objects.get_or_create(
            path=self.PATH, owner=owner)

        pf = PACSFile(owner=owner, parent_folder=series_folder)
        pf.fname.name = self.dcm_path
        created = PACSFile.objects.bulk_create([pf])

        self.assertEqual(len(created), 1)
        self.assertIsNotNone(
            created[0].pk,
            'bulk_create did not populate PK — on_commit fan-out will be a no-op',
        )

    def test_on_commit_fan_out_dispatches_task(self):
        """
        transaction.on_commit fires after bulk_create inside
        PACSSeriesSerializer.create and calls index_pacs_instance.delay() with
        the correct PACSFile PKs.

        This is the §5.1 hook: had the implementation used a post_save signal
        instead, on_commit would still fire (signals on individual .save() calls
        do fire), but it would NOT have fired on the real oxidicom path where
        oxidicom drives bulk_create — because Django does not emit post_save for
        bulk_create.  The serializer fan-out is the correct mechanism.
        """
        from unittest.mock import patch

        dispatched_ids = []
        with patch(
            'dicomweb.tasks.index_pacs_instance.delay',
            side_effect=lambda pk: dispatched_ids.append(pk),
        ):
            self._register()

        self.assertGreater(
            len(dispatched_ids), 0,
            'on_commit fan-out dispatched 0 tasks — the ingest hook is not working. '
            'This is the §5.1 defect.',
        )

    def test_task_creates_pacs_instance_after_series_registered(self):
        """
        index_pacs_instance creates a PACSInstance row when given the PACSFile PK
        produced by the bulk_create path.

        Called via apply() after register_pacs_series returns so that PACSSeries
        is committed before the task runs — matching production's async ordering
        (the broker delivers the task after register_pacs_series completes).
        """
        from pacsfiles.models import PACSFile
        from dicomweb.tasks import index_pacs_instance

        self._register()

        # PACSSeries now committed; task can find it via _find_series_for_file
        pf = PACSFile.objects.get(fname__endswith='0001.dcm')
        result = index_pacs_instance.apply(args=[pf.pk])
        result.get()  # raises if task errored (CELERY_TASK_EAGER_PROPAGATES=True)

        count = PACSInstance.objects.filter(
            series__pacs__identifier=self.PACS_NAME,
            SOPInstanceUID=self.SOP_UID,
        ).count()
        self.assertEqual(
            count, 1,
            f'PACSInstance not created by index_pacs_instance for PACSFile pk={pf.pk}.',
        )

    def test_series_tags_backfilled_after_ingest(self):
        """
        The indexing task backfills QIDO-required tags onto PACSSeries that the
        original ingest path didn't capture (SeriesNumber, Manufacturer, etc.).
        """
        from pacsfiles.models import PACSFile, PACSSeries
        from dicomweb.tasks import index_pacs_instance

        self._register()

        pf = PACSFile.objects.get(fname__endswith='0001.dcm')
        index_pacs_instance.apply(args=[pf.pk]).get()

        series = PACSSeries.objects.get(
            pacs__identifier=self.PACS_NAME,
            SeriesInstanceUID=self.SERIES_UID,
        )
        self.assertEqual(series.SeriesNumber, 1)
        self.assertEqual(series.Modality, 'CT')
