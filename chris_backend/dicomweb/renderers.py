"""
DRF renderers for the DICOMweb surface.

``DicomJsonRenderer`` encodes the native-model representation built by
:mod:`dicomweb.dicomnative` (a dataset ``list[DicomAttribute]`` or a list of such
datasets) into a DICOM JSON Model response (PS3.18 §F, ``application/dicom+json``).
It subclasses DRF's ``JSONRenderer`` so it plugs into content negotiation and
reuses DRF's JSON machinery.

The DICOM JSON Model encoding rules that belong to the JSON Model (rather than
the native model) live here, and ``_render_dataset`` is their single owner —
``DicomJsonEncoder`` only supplies the temporal wire forms:

  * binary/bulk VRs (OB, OW, …) and attributes carrying bulk data rejected —
    they must never appear at the QIDO metadata surface (§F.2.2 encodes them
    as BulkDataURI / InlineBinary)
  * IS/SL/SS/SV/UL/US/UV → JSON integer; DS/FL/FD → JSON float. §F.2.3 lists
    DS/IS/SV/UV as "Number or String"; we follow pydicom and emit numbers.
  * AT → 8-char uppercase hex string
  * DA/TM/DT → DICOM wire strings, produced from the stdlib datetime type by
    ``DicomJsonEncoder``
  * attribute objects ordered by property name in ascending lexicographic
    order (§F.2.2 "shall"), applied at encoding time so the wire order is
    independent of construction order
  * empty attribute → no ``"Value"`` key; empty element of a multi-valued
    attribute → JSON ``null`` (never ``""``; §F.2.5)

PN already arrives as its native component-group mapping from
:mod:`dicomweb.dicomnative` and is passed through unchanged.
"""
from datetime import date, datetime, time

import pydicom.valuerep
from rest_framework.renderers import JSONRenderer
from rest_framework.utils.encoders import JSONEncoder

from dicomweb.dicomnative import DicomAttribute, normalize_tag

# VR classes (pydicom, PS3.5-derived) used for JSON Model value coercion.
_BINARY_VRS = pydicom.valuerep.BYTES_VR
# PS3.18 §F.2.3 lists DS/IS/SV/UV as "Number or String"; per the atlas QIDO
# reference we align with pydicom, which emits them as numbers (DS→float,
# IS/SV/UV→int). AT is emitted separately as an 8-char hex string.
_INT_VRS = pydicom.valuerep.INT_VR - {'AT'}
_FLOAT_VRS = pydicom.valuerep.FLOAT_VR
# Temporal VRs whose values stay as stdlib datetime types (DA→date, TM→time,
# DT→datetime) until DicomJsonEncoder emits the DICOM wire form.
_TEMPORAL_VRS = frozenset({'DA', 'DT', 'TM'})


class DicomJsonEncoder(JSONEncoder):
    """
    JSON encoder that serializes temporal stdlib types to their DICOM wire
    forms (DA ``YYYYMMDD``, TM ``HHMMSS[.FFFFFF]``,
    DT ``YYYYMMDDHHMMSS[.FFFFFF][&ZZXX]``) rather than ISO-8601. Everything
    else defers to DRF's encoder, which cannot serialize a
    :class:`DicomAttribute`: attributes are encoded by ``_render_dataset``
    only, so one that escapes it fails loudly instead of being emitted
    without the JSON Model value rules.
    """

    def default(self, obj):
        # datetime is a subclass of date, so it must be checked first.
        if isinstance(obj, datetime):
            fmt = '%Y%m%d%H%M%S.%f' if obj.microsecond else '%Y%m%d%H%M%S'
            # DICOM DT allows a trailing "&ZZXX" UTC offset ("&" is "+"/"-"),
            # which strftime('%z') renders for tz-aware values and omits ('')
            # for naive ones.
            if obj.tzinfo is not None:
                fmt += '%z'
            return obj.strftime(fmt)
        if isinstance(obj, date):
            return obj.strftime('%Y%m%d')
        if isinstance(obj, time):
            if obj.microsecond:
                return obj.strftime('%H%M%S.%f')
            return obj.strftime('%H%M%S')
        return super().default(obj)


class DicomJsonRenderer(JSONRenderer):
    """
    Render QIDO-RS responses as the DICOM JSON Model (PS3.18 §F).

    Accepts a single dataset (``list[DicomAttribute]``), a bare
    :class:`DicomAttribute`, or a list of datasets
    (``list[list[DicomAttribute]]``) and always emits a top-level JSON
    array of DICOM JSON objects. Binary VRs and bulk data are rejected, so
    WADO-RS metadata (BulkDataURI / InlineBinary) is not covered yet.
    """
    media_type = 'application/dicom+json'
    format = 'dicom+json'
    encoder_class = DicomJsonEncoder

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Attribute ordering (§F.2.2) is applied in _render_dataset.
        return super().render(_to_json_model(data), accepted_media_type,
                              renderer_context)


class ApplicationJsonDicomRenderer(DicomJsonRenderer):
    """
    The same DICOM JSON Model bytes advertised as ``application/json``. QIDO-RS
    requires ``Accept: application/json`` be treated as equivalent to
    ``application/dicom+json`` (PS3.18 §10.6.2), and it is handy for curl.

    NOTE: DRF's built-in JSONRenderer also claims ``application/json`` and
    format ``json`` but cannot serialize a DicomAttribute payload, so it must
    not be on a dicomweb view. Use DicomWebRendererMixin.
    """
    media_type = 'application/json'
    format = 'json'


class DicomWebRendererMixin:
    """
    Renderers for the DICOMweb surface. Assigns (never appends to)
    ``renderer_classes``: DRF's built-in JSONRenderer cannot serialize a
    DicomAttribute payload, so it must not be inherited from
    DEFAULT_RENDERER_CLASSES on any dicomweb view. DicomJsonRenderer comes
    first so ``Accept: */*`` and a missing Accept header negotiate to
    ``application/dicom+json``.
    """
    renderer_classes = [DicomJsonRenderer, ApplicationJsonDicomRenderer]


def _is_dataset(data):
    """
    A DICOM Data Set is a list of DicomAttribute (§F.2.2).
    """
    return isinstance(data, list) and all(isinstance(elem, DicomAttribute) 
                                          for elem in data)


def _is_list_of_datasets(data):
    """
    A multi-result payload: a non-empty list whose every element is a dataset.
    """
    return (isinstance(data, list) and bool(data)
            and all(_is_dataset(elem) for elem in data))


def _to_json_model(data):
    """
    Convert a response payload into its DICOM JSON Model form.

    A top-level dataset (or bare attribute) becomes the response's top-level
    array holding its one DICOM JSON object (§F.2.1). Every other payload — a
    list of datasets, a DRF error value, a paginated dict — takes the form
    ``_to_json_model_object`` gives it.
    """
    rendered = _to_json_model_object(data)
    if isinstance(data, DicomAttribute) or (data and _is_dataset(data)):
        return [rendered]
    return rendered


def _to_json_model_object(data):
    """
    The JSON Model object form of an embedded value: a dataset or bare
    attribute becomes its tag→attribute object (§F.2.2), a list of datasets
    an array of such objects, containers are walked, and anything without
    DICOM content passes through unchanged.
    """
    if isinstance(data, DicomAttribute):
        return _render_dataset([data])
    if isinstance(data, (list, tuple)) and data:
        if _is_dataset(data):
            return _render_dataset(data)
        if _is_list_of_datasets(data):
            return [_render_dataset(elem) for elem in data]
        return [_to_json_model_object(elem) for elem in data]
    if isinstance(data, dict):
        return {key: _to_json_model_object(value) for key, value in data.items()}
    return data


def _render_dataset(attributes):
    """
    Render a dataset (``list[DicomAttribute]``) as its DICOM JSON object: a
    map of canonical tag to attribute object.
    """
    result = {normalize_tag(attr.tag): _render_attribute(attr) for attr in attributes}
    # §F.2.2 "shall": attribute objects ordered by property name ascending.
    # Tags are canonical 8-char uppercase hex, so lexicographic order
    # == numeric tag order.
    return dict(sorted(result.items()))


def _render_attribute(attr):
    """
    Render one attribute as its DICOM JSON attribute object (§F.2.2): its
    ``"vr"`` plus a ``"Value"`` array, omitted for an empty attribute (§F.2.5).
    """
    if (attr.VR in _BINARY_VRS or attr.bulk_data is not None
            or attr.inline_binary is not None):
        # TODO: BulkDataURI, InlineBinary (§F.2.6, §F.2.7) for WADO-RS
        raise ValueError(f'Binary VR or bulk data (VR {attr.VR!r}) not supported in '
                         f'dicomweb')

    element = {'vr': attr.VR}
    value = _coerce(attr.VR, attr.get_value())

    if value is not None:
        # A scalar coerces to a one-element Value.
        element['Value'] = value if isinstance(value, list) else [value]
    return element


def _coerce(vr, value):
    """
    Coerce a native value into its DICOM JSON Model form, or ``None`` when the
    attribute is empty (the caller then omits ``"Value"``).
    """
    if value is None or value == '' or value == []:
        return None
    if vr == 'SQ':
        # §F.2.2: a sequence's Value is an array of DICOM JSON objects, one per
        # item, where each item is itself a dataset (list[DicomAttribute]).
        # Render each item recursively (an empty item becomes {}, §F.2.5).
        return [_render_dataset(item) for item in value]
    if isinstance(value, (list, tuple)):
        # §F.2.5: empty elements of a multi-valued attribute are kept as JSON
        # null (never dropped, never ""), preserving value multiplicity and
        # position. One exception, per the binary encoding the list models:
        # a single empty element is VM=1 with Value Length 0 — an empty
        # attribute, rendered with no "Value" key.
        coerced = [_coerce_scalar(vr, v) for v in value]
        if all(c is None for c in coerced) and len(coerced) == 1:
            return None
        return coerced
    return _coerce_scalar(vr, value)


def _coerce_scalar(vr, value):
    if value is None or value == '':
        return None
    if vr == 'PN':
        return value  # already the native component mapping (dicomweb.dicomnative)
    if vr == 'AT':
        # AT is in pydicom's INT_VR (hence excluded from the local _INT_VRS);
        # DICOM JSON encodes it as an 8-char uppercase hex string, not a number.
        return normalize_tag(value)
    if vr in _TEMPORAL_VRS:
        # Kept as the stdlib datetime type the caller supplies; DicomJsonEncoder
        # renders the wire form. An already-formatted string passes through and
        # is emitted verbatim.
        # A datetime in a DA or TM slot is narrowed to its date or time: the
        # full DT wire form is not a valid DA or TM value. A date in a DT slot
        # is left as is and renders as YYYYMMDD, a valid DT whose trailing null
        # components mark it as precise to the day (PS3.5 §6.2).
        if isinstance(value, datetime):
            if vr == "DA":
                return value.date()
            if vr == "TM":
                return value.time()
        return value
    if vr in _INT_VRS:
        # int()/float() raise here on bad data: failing during serialization
        # points at the offending attribute rather than emitting a wrong type.
        return int(value)
    if vr in _FLOAT_VRS:
        return float(value)
    return str(value)
