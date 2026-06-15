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

# Maximum depth to walk up the folder tree when looking for a PACSSeries.
# oxidicom nests files at most a few levels deep; 16 guards against corrupt state.
_MAX_FOLDER_WALK = 16


def _find_series_for_file(pacs_file: PACSFile):
    """Walk parent folders until one owns a PACSSeries."""
    folder = pacs_file.parent_folder
    for _ in range(_MAX_FOLDER_WALK):
        if folder is None:
            return None
        try:
            return folder.pacs_series
        except PACSSeries.DoesNotExist:
            folder = folder.parent
    return None  # pragma: no cover — cycle/pathological-state guard


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
    # DICOM TM VR allows truncation at HH, HHMM, or HHMMSS.
    # Dispatch on length rather than trusting strptime's greedy matching.
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


def _transfer_syntax_uid(ds) -> str:
    """Return the TransferSyntaxUID string from DICOM file meta, empty if absent."""
    try:
        if ds.file_meta is not None:
            return str(ds.file_meta.TransferSyntaxUID)
    except AttributeError:
        pass
    return ''


def _trunc(n):
    return lambda v: str(v)[:n] if v else None


# Descriptor table for _backfill_series_tags.
# Each entry: (series_attr, is_empty_fn, ds_attr, transform_fn)
# is_empty_fn  — True when the series field should be filled.
# transform_fn — converts the raw DICOM value; return None to skip the field.
_BACKFILL_FIELDS = [
    ('StudyTime',                       lambda v: not v,     'StudyTime',                       _parse_dicom_time),
    ('SeriesNumber',                    lambda v: v is None, 'SeriesNumber',                    _as_int),
    ('Manufacturer',                    lambda v: not v,     'Manufacturer',                    _trunc(64)),
    ('BodyPartExamined',                lambda v: not v,     'BodyPartExamined',                _trunc(16)),
    ('PerformedProcedureStepStartDate', lambda v: v is None, 'PerformedProcedureStepStartDate', _parse_dicom_date),
    ('PerformedProcedureStepStartTime', lambda v: v is None, 'PerformedProcedureStepStartTime', _parse_dicom_time),
]


def _backfill_series_tags(series: PACSSeries, ds) -> None:
    """
    Populate QIDO-RS tags on PACSSeries that the original ingest path didn't
    capture. Only writes empty/null columns; never overwrites existing values
    (the ingest path is authoritative for what it sets).
    """
    updates = {}
    for attr, is_empty, ds_attr, transform in _BACKFILL_FIELDS:
        if is_empty(getattr(series, attr)):
            val = transform(getattr(ds, ds_attr, None))
            if val is not None:
                updates[attr] = val
    if updates:
        PACSSeries.objects.filter(pk=series.pk).update(**updates)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def index_pacs_instance(self, pacs_file_id):
    """
    Read the DICOM header for pacs_file_id, upsert PACSInstance, and backfill
    any QIDO-relevant tags on PACSSeries that weren't set at ingest time.
    Idempotent: safe to retry and safe to run via reindex_pacs_instances.
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
        return

    series = _find_series_for_file(pacs_file)
    if series is None:
        logger.warning('index_pacs_instance: no parent PACSSeries for file=%s', fname)
        return

    storage = connect_storage(settings)
    try:
        raw = storage.download_obj(fname)
    except Exception as exc:
        logger.error('index_pacs_instance: storage read failed for %s: %s', fname, exc)
        raise self.retry(exc=exc)

    try:
        ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True, force=True)
    except Exception as exc:
        logger.error('index_pacs_instance: pydicom failed on %s: %s', fname, exc)
        return

    sop_instance_uid = getattr(ds, 'SOPInstanceUID', None)
    if not sop_instance_uid:
        logger.warning('index_pacs_instance: missing SOPInstanceUID in %s', fname)
        return

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
                # DICOM mandates NumberOfFrames for multi-frame; absent means 1.
                NumberOfFrames=_as_int(getattr(ds, 'NumberOfFrames', None)) or 1,
                TransferSyntaxUID=_transfer_syntax_uid(ds),
            ),
        )
        _backfill_series_tags(series, ds)
