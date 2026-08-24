"""
DRF renderers for the DICOMweb surface.

``DicomJsonRenderer`` encodes the native-model representation built by
:mod:`dicomweb.dicomnative` (a dataset ``list[DicomAttribute]`` or a list of such
datasets) into a DICOM JSON Model response (PS3.18 §F, ``application/dicom+json``).
It subclasses DRF's ``JSONRenderer`` so it plugs into content negotiation and
reuses DRF's JSON machinery.

The DICOM JSON Model encoding rules that belong to the JSON Model (rather than
the native model) live here:

  * binary/bulk VRs (OB, OW, …) rejected — they must never appear at the QIDO
    metadata surface (§F.2.2 encodes them as BulkDataURI / InlineBinary)
  * IS/SL/SS/SV/UL/US/UV → JSON integer; DS/FL/FD → JSON float. §F.2.3 lists
    DS/IS/SV/UV as "Number or String"; we follow pydicom and emit numbers.
  * AT → 8-char uppercase hex string
  * DA/TM/DT → DICOM wire strings, produced from the stdlib datetime type by
    ``DicomJsonEncoder``
  * empty attribute → no ``"Value"`` key; empty element of a multi-valued
    attribute → JSON ``null`` (never ``""``; §F.2.5)

PN already arrives as its native Alphabetic mapping from :mod:`dicomweb.dicomnative`
and is passed through unchanged.
"""
from datetime import date, datetime, time

import pydicom.valuerep
from pydicom.tag import Tag
from rest_framework.renderers import JSONRenderer
from rest_framework.utils.encoders import JSONEncoder

from dicomweb.dicomnative import DicomAttribute

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
    DT ``YYYYMMDDHHMMSS[.FFFFFF][&ZZXX]``) rather than ISO-8601. Everything else
    defers to DRF's encoder.
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
        if isinstance(obj, DicomAttribute):
            tag = f"{Tag(obj.tag):08X}"
            encoded_attr = {
                "vr": obj.vr,
            }
            if (value := obj.get_value()) is not None:
                encoded_attr["Value"] = value
            elif (bulk_data := obj.bulk_data) is not None:
                # TODO: Fix this stub when implementing WADO-RS
                encoded_attr["BulkDataURI"] = bulk_data
            elif (inline_binary := obj.get_inline_binary()) is not None:
                encoded_attr["InlineBinary"] = inline_binary.decode("utf-8")
            return super().default({tag: encoded_attr})
        return super().default(obj)


class DicomJsonRenderer(JSONRenderer):
    """
    Render QIDO-RS / WADO-RS responses as the DICOM JSON Model (PS3.18 §F).

    Accepts either a single dataset (``list[DicomAttribute]``) or a list of
    datasets (``list[list[DicomAttribute]]``) and always emits a top-level JSON
    array of DICOM JSON objects.
    """
    media_type = 'application/dicom+json'
    format = 'dicom+json'
    encoder_class = DicomJsonEncoder

    def render(self, data, accepted_media_type=None, renderer_context=None):
        payload = _to_json_model(data)
        if renderer_context is None:
            renderer_context = {}
        renderer_context.get('encoder_kwargs', {})['sort_keys'] = True
        return super().render(payload, accepted_media_type, renderer_context)


class ApplicationJsonDicomRenderer(DicomJsonRenderer):
    """
    The same DICOM JSON Model bytes advertised as ``application/json``. QIDO-RS
    requires ``Accept: application/json`` be treated as equivalent to
    ``application/dicom+json`` (PS3.18 §10.6.2), and it is handy for curl.
    """
    media_type = 'application/json'
    format = 'json'


def _to_json_model(data):
    """Convert DicomAttribute datasets into DICOM JSON Model objects."""
    if isinstance(data, DicomAttribute):
        return _render_dataset([data])
    # Anything not a list is not a dataset, so pass through
    if not isinstance(data, list):
        return data
    if not data:
        return []
    # List of datasets
    if all(isinstance(elem, DicomAttribute) for elem in data):
        return [_render_dataset(data)]
    # Anything else, map over the list
    return [_to_json_model(elem) for elem in data]

    # A bare dataset (list of DicomAttribute) → wrap as a single-element array.
    datasets = [data] if isinstance(data[0], DicomAttribute) else data
    return [_render_dataset(ds) for ds in datasets]


def _render_dataset(attributes):
    result = {}
    for attr in attributes:
        if attr.VR in _BINARY_VRS:
            # TODO: BulkDataURI, InlineBinary
            raise ValueError(f'Binary VR {attr.VR!r} not supported in dicomweb')
        element = {'vr': attr.VR}
        coerced = _coerce(attr.VR, attr.get_value())
        if coerced is not None:
            element['Value'] = coerced if isinstance(coerced, list) else [coerced]
        result[attr.tag] = element
    return result


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
        # position. A wholly empty list is an empty attribute (Value omitted).
        coerced = [_coerce_scalar(vr, v) for v in value]
        if all(c is None for c in coerced):
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
        return f'{Tag(value):08X}'
    if vr in _TEMPORAL_VRS:
        # Kept as the stdlib datetime type the caller supplies; DicomJsonEncoder
        # renders the wire form. An already-formatted string passes through and
        # is emitted verbatim.
        return value
    if vr in _INT_VRS:
        # int()/float() raise here on bad data: failing during serialization
        # points at the offending attribute rather than emitting a wrong type.
        return int(value)
    if vr in _FLOAT_VRS:
        return float(value)
    return str(value)
