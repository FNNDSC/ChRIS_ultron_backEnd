"""
DICOM-tag query parser for QIDO-RS (PS3.18 §F.7).

Translates URL query parameters (hex tags or DICOM keywords) into Django ORM
filter expressions. Handles: multi-value OR, date ranges, wildcards, limit/offset.

Usage::

    from dicomweb.query import QueryFilter, TAG_MAP_SERIES

    qf = QueryFilter(TAG_MAP_SERIES)
    qs = qf.apply(PACSSeries.objects.all(), request.query_params)
    page, total, limit = qf.paginate(qs, request.query_params)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pydicom.datadict
from django.db.models import Q, QuerySet
from django.http import QueryDict


# ---------------------------------------------------------------------------
# Tag descriptor types
# ---------------------------------------------------------------------------

@dataclass
class ModelField:
    orm_path: str       # e.g. 'PatientName' or 'series__StudyInstanceUID'
    vr: str             # DICOM VR ('PN', 'DA', 'UI', 'CS', ...)
    range_: bool = False   # DA/TM range syntax supported
    wildcard: bool = False  # wildcard ('*' / '?') supported


@dataclass
class Aggregation:
    """Tags handled by view-level .annotate()/.filter(); skipped here."""
    name: str


# ---------------------------------------------------------------------------
# Static tag maps
# ---------------------------------------------------------------------------

TAG_MAP_STUDY = {
    '00100010': ModelField('PatientName', vr='PN', wildcard=True),
    '00100020': ModelField('PatientID', vr='LO', wildcard=True),
    '00100030': ModelField('PatientBirthDate', vr='DA', range_=True),
    '00100040': ModelField('PatientSex', vr='CS'),
    '0020000D': ModelField('StudyInstanceUID', vr='UI'),
    '00080020': ModelField('StudyDate', vr='DA', range_=True),
    '00080030': ModelField('StudyTime', vr='TM', range_=True),
    '00080050': ModelField('AccessionNumber', vr='SH', wildcard=True),
    '00081030': ModelField('StudyDescription', vr='LO', wildcard=True),
    # Aggregation tags — handled in view, not here
    '00080061': Aggregation('ModalitiesInStudy'),
    '00201206': Aggregation('NumberOfStudyRelatedSeries'),
    '00201208': Aggregation('NumberOfStudyRelatedInstances'),
}

TAG_MAP_SERIES = {
    '0020000E': ModelField('SeriesInstanceUID', vr='UI'),
    '00200011': ModelField('SeriesNumber', vr='IS'),
    '00080060': ModelField('Modality', vr='CS'),
    '0008103E': ModelField('SeriesDescription', vr='LO', wildcard=True),
    '00180015': ModelField('BodyPartExamined', vr='CS'),
    '00080070': ModelField('Manufacturer', vr='LO', wildcard=True),
    '00181030': ModelField('ProtocolName', vr='LO', wildcard=True),
    # Study-level pass-through
    '0020000D': ModelField('StudyInstanceUID', vr='UI'),
    '00100010': ModelField('PatientName', vr='PN', wildcard=True),
    '00100020': ModelField('PatientID', vr='LO'),
}

TAG_MAP_INSTANCE = {
    '00080018': ModelField('SOPInstanceUID', vr='UI'),
    '00080016': ModelField('SOPClassUID', vr='UI'),
    '00200013': ModelField('InstanceNumber', vr='IS'),
    '00280010': ModelField('Rows', vr='US'),
    '00280011': ModelField('Columns', vr='US'),
    '00280100': ModelField('BitsAllocated', vr='US'),
    '00280008': ModelField('NumberOfFrames', vr='IS'),
    # Series pass-through
    '0020000E': ModelField('series__SeriesInstanceUID', vr='UI'),
    '0020000D': ModelField('series__StudyInstanceUID', vr='UI'),
}


# ---------------------------------------------------------------------------
# QueryFilter
# ---------------------------------------------------------------------------

_RESERVED_PARAMS = frozenset({'limit', 'offset', 'includefield', 'fuzzymatching', 'orderby'})


class QueryFilter:
    """
    Translates QIDO-RS URL parameters into ORM filter expressions.

    Unsupported tags are silently dropped (PS3.18 §F.7: servers may ignore
    unsupported match attributes).
    """
    HARD_LIMIT = 5000
    DEFAULT_LIMIT = 50

    def __init__(self, tag_map: dict):
        self.tag_map = tag_map
        self._kw_to_hex = {}
        for hex_tag in tag_map:
            if len(hex_tag) != 8:
                continue
            try:
                kw = pydicom.datadict.keyword_for_tag(int(hex_tag, 16))
                if kw:
                    self._kw_to_hex[kw] = hex_tag
            except Exception:
                pass

    def apply(self, qs: QuerySet, params) -> QuerySet:
        """Apply DICOM match parameters from ``params`` to ``qs``."""
        if isinstance(params, QueryDict):
            items = params.items()
        else:
            items = params.items() if hasattr(params, 'items') else params

        for key, value in items:
            if key in _RESERVED_PARAMS:
                continue
            if not value:
                # PS3.18 §F.7: empty value → no restriction on that attribute
                continue
            hex_tag = self._resolve_tag(key)
            if hex_tag is None:
                continue
            descriptor = self.tag_map.get(hex_tag)
            if descriptor is None or isinstance(descriptor, Aggregation):
                continue
            qs = self._apply_field(qs, descriptor, value)
        return qs

    def paginate(self, qs: QuerySet, params):
        """Return (page_qs, total_count, effective_limit)."""
        raw_limit = params.get('limit', self.DEFAULT_LIMIT) if hasattr(params, 'get') else self.DEFAULT_LIMIT
        raw_offset = params.get('offset', 0) if hasattr(params, 'get') else 0
        try:
            limit = min(int(raw_limit), self.HARD_LIMIT)
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        try:
            offset = max(int(raw_offset), 0)
        except (TypeError, ValueError):
            offset = 0
        total = qs.count()
        return qs[offset:offset + limit], total, limit

    # ── Private helpers ──────────────────────────────────────────────────────

    def _resolve_tag(self, key: str) -> Optional[str]:
        """Return 8-hex-char tag from either hex form or DICOM keyword."""
        upper = key.upper()
        if len(upper) == 8 and all(c in '0123456789ABCDEF' for c in upper):
            return upper
        return self._kw_to_hex.get(key)  # case-sensitive keyword lookup

    def _apply_field(self, qs: QuerySet, descriptor: ModelField, raw_value: str) -> QuerySet:
        field = descriptor.orm_path
        vr = descriptor.vr
        values = raw_value.split(',')  # multi-value → OR semantics

        # Date/time range: only activate for DA/TM VRs with a single value containing '-'
        if vr in ('DA', 'TM', 'DT') and descriptor.range_ and '-' in raw_value and len(values) == 1:
            return self._apply_range(qs, field, vr, raw_value)

        q = Q()
        for v in values:
            if descriptor.wildcard and ('*' in v or '?' in v):
                like_val = v.replace('*', '%').replace('?', '_')
                q |= Q(**{f'{field}__icontains': like_val.strip('%_')}) if like_val in ('%', '_') else Q(**{f'{field}__iregex': _like_to_regex(like_val)})
            elif vr == 'PN':
                # PN: stored as 'FAMILY^GIVEN'; support exact or alphabetic-component prefix
                q |= Q(**{f'{field}__iexact': v}) | Q(**{f'{field}__istartswith': v})
            else:
                q |= Q(**{f'{field}': v})
        return qs.filter(q)

    def _apply_range(self, qs: QuerySet, field: str, vr: str, raw_value: str) -> QuerySet:
        parts = raw_value.split('-', 1)
        start_str = parts[0].strip()
        end_str = parts[1].strip() if len(parts) > 1 else ''
        start = _parse_da(start_str) if start_str else None
        end = _parse_da(end_str) if end_str else None
        if start:
            qs = qs.filter(**{f'{field}__gte': start})
        if end:
            qs = qs.filter(**{f'{field}__lte': end})
        return qs


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _parse_da(s: str):
    """Parse DICOM DA string (YYYYMMDD) to Python date, or None on failure."""
    try:
        return datetime.strptime(s[:8], '%Y%m%d').date()
    except (ValueError, TypeError):
        return None


def _like_to_regex(like_val: str) -> str:
    """Convert SQL LIKE pattern (with % and _) to a Python regex string."""
    import re
    parts = re.split(r'([%_])', like_val)
    result = []
    for part in parts:
        if part == '%':
            result.append('.*')
        elif part == '_':
            result.append('.')
        else:
            result.append(re.escape(part))
    return ''.join(result)
