"""
DICOM-tag query parser for QIDO-RS (PS3.18 §10.6.1.2 "Query Parameters"; matching
semantics per §8.3.4 and PS3.4 §C.2.2.2).

Translates URL query parameters (hex tags or DICOM keywords) into Django ORM
filter expressions. Handles: multi-value OR, date ranges, wildcards, fuzzy
Person-Name matching (§8.3.4.2), and limit/offset pagination (§8.3.4.4).

Usage::

    from django.http import QueryDict
    from dicomweb.query import QueryFilter, SearchQuery

    search_query = SearchQuery.from_query_dict(QueryDict('StudyInstanceUID=123'))
    qf = QueryFilter('series')
    qs = qf.apply(PACSSeries.objects.all(), search_query)
    page, total, limit = qf.paginate(qs, search_query)
"""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Self, Optional, Literal, Any, Union

import pydicom.datadict
import pydicom.tag
from django.db.models import CharField, TextField, Q, QuerySet
from django.http import QueryDict


# Alias
type TagType = pydicom.tag.TagType
Tag = pydicom.tag.Tag

# reserved words for search query parameters
_SEARCH_PARAMS = frozenset({
    'limit', 'offset', 'includefield', 'fuzzymatching',
    'orderby', 'emptyvaluematching', 'multiplevaluematching'
})


@dataclass
class SearchQuery:
    match: dict[TagType, list[str]]
    fuzzymatching: bool = False
    includefield: Optional[Union[list[TagType], Literal['all']]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    emptyvaluematching: bool = False
    multiplevaluematching: bool = False

    @staticmethod
    def _parse_bool(value: str) -> bool:
        return value.lower() in ('true', '1', 'yes')

    @classmethod
    def from_query_dict(cls, params: QueryDict) -> Self:
        # Split the query parameters into matches and search parameters
        match_pairs: dict[TagType, list[str]] = {}
        for param in params:
            if param not in _SEARCH_PARAMS:
                try:
                    tag = Tag(param)
                except (ValueError, OverflowError):
                    continue
                match_pairs[tag] = params.getlist(param)

        search_options: dict[str, Any] = {}
        if 'includefield' in params:
            # includefield can be passed multiple times and/or be a
            # comma-separated list. It may also include the special
            # 'all' value.
            includefield = []
            for item in params.getlist('includefield'):
                includefield.extend(item.split(","))
            if 'all' in includefield:
                search_options['includefield'] = 'all'
            else:
                _includefield = []
                for val in includefield:
                    try:
                        tag = Tag(val)
                    except (ValueError, OverflowError):
                        continue
                    _includefield.append(tag)
                search_options['includefield'] = _includefield
        if (limit := params.get('limit')) is not None:
            search_options['limit'] = int(limit)
        if (offset := params.get('offset')) is not None:
            search_options['offset'] = int(offset)
        for field in ['fuzzymatching', 'emptyvaluematching', 'multiplevaluematching']:
            if (field_value := params.get(field)) is not None:
                search_options[field] = cls._parse_bool(field_value)

        return cls(
            match=match_pairs,
            **search_options,
        )


# Matching types for VRs
WILDCARD_VRS = frozenset({'AE', 'CS', 'LO', 'LT', 'PN', 'SH', 'ST', 'UC',
                          'UR', 'UT'})
MULTI_VALUE_VRS = frozenset({'AE', 'AS', 'AT', 'CS', 'LO', 'PN', 'SH', 'UC'})
RANGE_VRS = frozenset({'DA', 'TM', 'DT'})
UID_LIST_VRS = frozenset({'UI'})

# ---------------------------------------------------------------------------
# Tag descriptor types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UniversalValue:
    """Sentinel for universal matching."""
    pass


@dataclass(frozen=True, slots=True)
class EmptyValue:
    """Sentinel for empty value matching."""
    pass


@dataclass
class RangeValue[T]:
    start: Optional[T]
    end: Optional[T]

    def __post_init__(self):
        # Validate open-ended ranges per PS3.4 §C.2.2.2.5.1
        if self.start is None and self.end is None:
            raise ValueError("Range must have at least one start or end value.")


@dataclass
class MultipleValue[T]:
    values: list[T]


@dataclass
class Attribute:
    keyword: str
    orm_field: str = ""         # Will default to keyword if unset
    tag: Optional[TagType] = None
    vr: Optional[str] = None
    vm: Optional[str] = None
    standard_lookup: str = 'exact'
    wildcard_lookup: str = 'regex'
    fuzzy: bool = False  # eligible for fuzzy PN matching (PS3.18 §8.3.4.2)
    fuzzy_lookup: str = "trigram_similar"

    def __post_init__(self):
        if self.orm_field == "":
            self.orm_field = self.keyword
        if self.tag is None:
            self.tag = pydicom.tag.Tag(self.keyword)
        if self.vr is None:
            self.vr = pydicom.datadict.dictionary_VR(self.tag)
        if self.vm is None:
            self.vm = pydicom.datadict.dictionary_VM(self.tag)
        if self.vr == 'PN':
            self.standard_lookup = 'iexact'
            self.wildcard_lookup = 'iregex'

    def cap_wildcard(self) -> bool:
        return self.vr in WILDCARD_VRS

    def cap_range(self) -> bool:
        return self.vr in RANGE_VRS

    def cap_multi_value(self) -> bool:
        # PS3.4 §C.2.2.2.8
        if self.vr not in MULTI_VALUE_VRS:
            return False
        return self.vm != '1'

    def parse(self, value: str, multi_value: bool = False) -> Any:
        if value == '':
            return UniversalValue()
        if value == '""':
            return EmptyValue()
        if self.cap_range() and "-" in value:
            return self.parse_range(value)
        if self.vr in UID_LIST_VRS or (self.cap_multi_value() and multi_value):
            parsed_value = self.parse_multiple(value)
            length = len(parsed_value.values)
            if length == 1:
                return parsed_value.values[0]
            return parsed_value
        return self.parse_single(value)

    def parse_single(self, value: str) -> Any:
        """Parse a single value from a query string. For range values, use parse_range."""
        if self.vr in ['DA', 'DT', 'TM']:
            return _parse_temporal(self.vr, value)
        return value

    def parse_range(self, value: str) -> RangeValue:
        if '-' not in value:
            raise ValueError(f'Invalid range value: {value}')
        start, end = value.split('-', maxsplit=1)
        result = RangeValue(
            self.parse_single(start) if start != '' else None,
            self.parse_single(end) if end != '' else None,
        )
        return result

    def parse_multiple(self, value: str) -> MultipleValue:
        return MultipleValue([self.parse_single(v) for v in re.split(r'[\\,]', value) if len(v) > 0])


# ---------------------------------------------------------------------------
# Supported Query fields
# ---------------------------------------------------------------------------

QUERY_FIELDS_STUDY = [
        Attribute('PatientName', fuzzy=True),
        Attribute('PatientID'),
        Attribute('PatientBirthDate'),
        Attribute('PatientSex'),
        Attribute('StudyInstanceUID'),
        Attribute('StudyDate'),
        Attribute('StudyTime'),
        Attribute('AccessionNumber'),
        Attribute('StudyDescription'),
        # Attribute('ModalitiesInStudy', aggregation=True),
        Attribute('NumberOfStudyRelatedSeries'),
        Attribute('NumberOfStudyRelatedInstances'),
    ]

QUERY_FIELDS_SERIES = [
    Attribute('SeriesInstanceUID'),
    Attribute('SeriesNumber'),
    Attribute('Modality'),
    Attribute('SeriesDescription'),
    Attribute('BodyPartExamined'),
    Attribute('Manufacturer'),
    Attribute('ProtocolName'),
    # Study-level pass-through
    Attribute('StudyInstanceUID'),
    Attribute('PatientName', fuzzy=True),
    Attribute('PatientID'),
]

QUERY_FIELDS_INSTANCE = [
    Attribute('SOPInstanceUID'),
    Attribute('SOPClassUID'),
    Attribute('InstanceNumber'),
    Attribute('Rows'),
    Attribute('Columns'),
    Attribute('BitsAllocated'),
    Attribute('NumberOfFrames'),
    # Series pass-through
    Attribute('SeriesInstanceUID', orm_field='series__SeriesInstanceUID'),
    Attribute('StudyInstanceUID', orm_field='series__StudyInstanceUID'),
]


# ---------------------------------------------------------------------------
# QueryFilter
# ---------------------------------------------------------------------------

class QueryFilter:
    """
    Translates QIDO-RS URL parameters into ORM filter expressions.

    Unsupported tags are silently dropped (PS3.18 §F.7: servers may ignore
    unsupported match attributes).
    """
    HARD_LIMIT = 5000
    DEFAULT_LIMIT = 50
    TAG_MAPS_BY_RESOURCE_TYPE = {
        'study': {field.tag: field for field in QUERY_FIELDS_STUDY},
        'series': {field.tag: field for field in QUERY_FIELDS_SERIES},
        'instance': {field.tag: field for field in QUERY_FIELDS_INSTANCE},
    }

    def __init__(self, target_resource_type: Literal['study', 'series', 'instance']):
        try:
            self.tag_map = self.TAG_MAPS_BY_RESOURCE_TYPE[target_resource_type]
        except KeyError:
            raise ValueError(f'Unsupported resource type: "{target_resource_type}"')

    def apply(self, qs: QuerySet, search_query: SearchQuery) -> QuerySet:
        """Filter a QuerySet according to a SearchQuery."""

        for tag, values in search_query.match.items():
            try:
                attribute = self.tag_map[tag]
            except KeyError:
                # Ignore any extra attributes
                continue

            q = Q()
            for raw_value in values:
                # Handle multiple and range values first
                match attribute.parse(raw_value, search_query.multiplevaluematching):
                    case RangeValue(start, end):
                        range_q = Q()
                        if start is not None:
                            range_q &= Q(**{f'{attribute.orm_field}__gte': start})
                        if end is not None:
                            range_q &= Q(**{f'{attribute.orm_field}__lte': end})
                        q |= range_q
                        continue
                    case MultipleValue(multi_values):
                        q |= Q(**{f'{attribute.orm_field}__in': multi_values})
                        continue
                    case UniversalValue():
                        # PS3.4 §C.2.2.2.3 Universal Matching
                        continue
                    case EmptyValue():
                        # PS3.4 §C.2.2.2.7 Empty value matching
                        if not search_query.emptyvaluematching:
                            # TODO: log warning
                            continue
                        # Match NULL or '' on text columns
                        q |= Q(**{f'{attribute.orm_field}__isnull': True})
                        if _is_text_column(qs.model, attribute.orm_field):
                            q |= Q(**{attribute.orm_field: ''})
                        continue
                    case single_value:
                        value = single_value

                # Single value handling
                if attribute.cap_wildcard() and ('*' in value or '?' in value):
                    # Wildcard matching
                    q |= Q(**{f'{attribute.orm_field}__{attribute.wildcard_lookup}': _wildcard_to_regex(value)})
                else:
                    if search_query.fuzzymatching and attribute.fuzzy:
                        # Fuzzy matching
                        q |= Q(**{f'{attribute.orm_field}__{attribute.fuzzy_lookup}': value})
                    q |= Q(**{f'{attribute.orm_field}__{attribute.standard_lookup}': value})

            qs = qs.filter(q)
        return qs

    def paginate(self, qs: QuerySet, search_query: SearchQuery):
        """Return a single page of a QuerySet using limit and offset
        specified in a SearchQuery.

        Return Value: (page_qs, total_count, effective_limit).
        """
        limit = self.DEFAULT_LIMIT if search_query.limit is None else search_query.limit
        offset = 0 if search_query.offset is None else search_query.offset

        # Clip limit to [0..HARD_LIMIT]
        limit = max(0, min(limit, self.HARD_LIMIT))

        # Ensure a non-negative offset
        offset = max(0, offset)

        total = qs.count()
        return qs[offset:offset + limit], total, limit


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _is_text_column(model, orm_field: str) -> bool:
    """Determine whether ``orm_field`` maps to a text column."""
    field = None
    for part in orm_field.split('__'):
        field = model._meta.get_field(part)
        if field.is_relation:
            model = field.related_model
    return isinstance(field, (CharField, TextField))


def _parse_da(s: str):
    """Parse DICOM DA string (YYYYMMDD) to Python date; raises ValueError on failure."""
    try:
        return datetime.strptime(s[:8], '%Y%m%d').date()
    except (ValueError, TypeError):
        raise ValueError(f'Unable to parse date value: {s}')


def _parse_tm(s: str):
    """Parse a DICOM TM string (HHMMSS[.ffffff], truncated forms allowed) to a
    Python time; raises ValueError on failure."""
    raw = s.split('.', 1)[0]
    fmt = {6: '%H%M%S', 4: '%H%M', 2: '%H'}.get(len(raw))
    if fmt is None:
        raise ValueError(f'Unable to parse time value: {s}')
    try:
        return datetime.strptime(raw, fmt).time()
    except (ValueError, TypeError):
        raise ValueError(f'Unable to parse time value: {s}')


def _parse_dt(s: str):
    """Parse a DICOM DT string (YYYYMMDD[HHMMSS], truncated forms allowed) to a
    Python datetime; raises ValueError on failure."""
    raw = s.split('.', 1)[0]
    for fmt in ('%Y%m%d', '%Y%m%d%H', '%Y%m%d%H%M', '%Y%m%d%H%M%S'):
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    raise ValueError(f'Unable to parse datetime value: {s}')


def _parse_temporal(vr: str, s: str):
    """Parse a DICOM DA/TM/DT string into its native type (date/time/datetime).
    Dispatches on VR so range and exact matching coerce correctly. Raises
    ValueError on malformed input, or TypeError on an unsupported VR."""
    if vr == 'DA':
        return _parse_da(s)
    if vr == 'TM':
        return _parse_tm(s)
    if vr == 'DT':
        return _parse_dt(s)
    raise TypeError(f'Invalid VR for temporal value: {vr}')


def _wildcard_to_regex(value: str) -> str:
    """Convert a wildcard pattern to POSIX regex."""
    parts = re.split(r'([*?])', value)
    result = []
    for part in parts:
        if part == '*':
            result.append('.*')
        elif part == '?':
            result.append('.')
        else:
            result.append(re.escape(part))
    # wrap in ^$ to ensure a full match
    result = ['^', *result, '$']
    return ''.join(result)
