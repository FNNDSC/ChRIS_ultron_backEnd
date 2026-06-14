import io
import logging
from datetime import datetime

import pydicom
from celery import shared_task
from django.conf import settings
from django.db import transaction

from core.storage import connect_storage
from pacsfiles.models import PACSFile, PACSSeries

from .models import PACSInstance

logger = logging.getLogger(__name__)


def _find_series_for_file(pacs_file: PACSFile):
    """
    Walk parent folders until we reach the one that owns a ``PACSSeries``.

    ``oxidicom`` and the existing PACS ingest path nest files under the series
    folder (sometimes through one or more intermediate sub-folders), so the
    immediate ``parent_folder`` of a ``PACSFile`` is not always the series
    folder. Walk up the chain until we hit a folder whose reverse
    ``pacs_series`` accessor resolves.
    """
    folder = pacs_file.parent_folder
    for _ in range(16):  # bound the walk in case of cycles / bad state
        if folder is None:
            return None
        try:
            return folder.pacs_series
        except PACSSeries.DoesNotExist:
            folder = folder.parent
    return None


def _parse_dicom_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), '%Y%m%d').date()
    except (TypeError, ValueError):
        return None


def _parse_dicom_time(value):
    if not value:
        return None
    raw = str(value).split('.', 1)[0]  # strip fractional seconds
    # DICOM TM VR is HHMMSS.FFFFFF, but allows truncation at HH, HHMM, HHMMSS.
    # We can't trust strptime's greedy matching on bare digit specs, so
    # dispatch on length explicitly.
    fmt_for_len = {6: '%H%M%S', 4: '%H%M', 2: '%H'}
    fmt = fmt_for_len.get(len(raw))
    if fmt is None:
        return None
    try:
        return datetime.strptime(raw, fmt).time()
    except ValueError:
        return None


def _as_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def index_pacs_instance(self, pacs_file_id):
    """
    Read the DICOM header for ``pacs_file_id``, upsert the matching
    ``PACSInstance``, and backfill any QIDO-relevant tags on the parent
    ``PACSSeries`` that aren't already populated.

    Idempotent: safe to retry, safe to run via the
    ``reindex_pacs_instances`` management command (Phase D) over the
    existing PACS file tree.
    """
    try:
        pacs_file = (PACSFile.objects
                     .select_related('parent_folder')
                     .get(pk=pacs_file_id))
    except PACSFile.DoesNotExist:
        logger.warning('index_pacs_instance: PACSFile id=%s not found', pacs_file_id)
        return

    fname = pacs_file.fname.name
    if not fname.endswith('.dcm'):
        # Non-DICOM sidecar in the PACS tree (e.g. JSON manifest). Skip.
        return

    series = _find_series_for_file(pacs_file)
    if series is None:
        logger.warning('index_pacs_instance: no parent PACSSeries for file=%s',
                       fname)
        return

    storage = connect_storage(settings)
    try:
        raw = storage.download_obj(fname)
    except Exception as exc:
        logger.error('index_pacs_instance: storage read failed for %s: %s',
                     fname, exc)
        raise self.retry(exc=exc)

    try:
        ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True,
                             force=True)
    except Exception as exc:
        logger.error('index_pacs_instance: pydicom failed on %s: %s', fname, exc)
        return  # don't retry on parse failures — they won't get better

    sop_instance_uid = getattr(ds, 'SOPInstanceUID', None)
    if not sop_instance_uid:
        logger.warning('index_pacs_instance: missing SOPInstanceUID in %s', fname)
        return

    transfer_syntax = ''
    try:
        if ds.file_meta is not None:
            transfer_syntax = str(ds.file_meta.TransferSyntaxUID)
    except AttributeError:
        pass

    with transaction.atomic():
        PACSInstance.objects.update_or_create(
            series=series,
            SOPInstanceUID=str(sop_instance_uid),
            defaults=dict(
                pacs_file=pacs_file,
                SOPClassUID=str(getattr(ds, 'SOPClassUID', '') or ''),
                InstanceNumber=_as_int(getattr(ds, 'InstanceNumber', None)),
                Rows=_as_int(getattr(ds, 'Rows', None)),
                Columns=_as_int(getattr(ds, 'Columns', None)),
                BitsAllocated=_as_int(getattr(ds, 'BitsAllocated', None)),
                NumberOfFrames=_as_int(getattr(ds, 'NumberOfFrames', None)) or 1,
                TransferSyntaxUID=transfer_syntax,
            ),
        )

        _backfill_series_tags(series, ds)


def _backfill_series_tags(series: PACSSeries, ds) -> None:
    """
    Populate QIDO-RS tags on PACSSeries that the original ingest path didn't
    capture. Only writes empty/null columns; never overwrites existing values
    (the ingest path is authoritative for what it sets).
    """
    updates = {}

    if not series.StudyTime:
        st = _parse_dicom_time(getattr(ds, 'StudyTime', None))
        if st is not None:
            updates['StudyTime'] = st

    if series.SeriesNumber is None:
        sn = _as_int(getattr(ds, 'SeriesNumber', None))
        if sn is not None:
            updates['SeriesNumber'] = sn

    if not series.Manufacturer:
        m = getattr(ds, 'Manufacturer', None)
        if m:
            updates['Manufacturer'] = str(m)[:64]

    if not series.BodyPartExamined:
        bp = getattr(ds, 'BodyPartExamined', None)
        if bp:
            updates['BodyPartExamined'] = str(bp)[:16]

    if series.PerformedProcedureStepStartDate is None:
        d = _parse_dicom_date(getattr(ds, 'PerformedProcedureStepStartDate', None))
        if d is not None:
            updates['PerformedProcedureStepStartDate'] = d

    if series.PerformedProcedureStepStartTime is None:
        t = _parse_dicom_time(getattr(ds, 'PerformedProcedureStepStartTime', None))
        if t is not None:
            updates['PerformedProcedureStepStartTime'] = t

    if updates:
        PACSSeries.objects.filter(pk=series.pk).update(**updates)
