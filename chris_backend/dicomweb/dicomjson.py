"""
DICOM JSON Model (PS3.18 §F) serialization helpers.

Converts (tag_hex, vr, python_value) tuples into the canonical dict shape
that QIDO-RS responses use. Views call ``dataset()``; they do not format
individual tags.
"""
from datetime import date, time


_BINARY_VRS = frozenset({'OB', 'OD', 'OF', 'OL', 'OW', 'SQ', 'UN', 'UC', 'UR', 'UT'})


def tag_value(tag_hex: str, vr: str, value) -> dict:
    """
    Build one DICOM JSON Model tag entry.

    Args:
        tag_hex: 8-char uppercase hex string, e.g. '00100010'
        vr:      DICOM VR string, e.g. 'PN', 'DA', 'UI'
        value:   Python value (None, str, int, float, list, date, time)

    Returns:
        ``{"vr": "...", "Value": [...]}`` dict, or ``{"vr": "..."}`` if empty.

    Raises:
        ValueError: if ``vr`` is in _BINARY_VRS (pixel/bulk data — must never
                    appear in QIDO responses per PS3.18 §F.2.2).
    """
    if vr in _BINARY_VRS:
        raise ValueError(f'Binary VR {vr!r} must not be emitted in QIDO responses')

    if value is None or value == '' or value == []:
        return {'vr': vr}

    if vr == 'PN':
        return {'vr': 'PN', 'Value': [_encode_pn(value)]}

    if vr == 'DA':
        return {'vr': vr, 'Value': [_encode_date(value)]}

    if vr == 'TM':
        return {'vr': vr, 'Value': [_encode_time(value)]}

    if isinstance(value, (list, tuple)):
        return {'vr': vr, 'Value': [_scalar(vr, v) for v in value]}

    return {'vr': vr, 'Value': [_scalar(vr, value)]}


def dataset(tag_value_pairs: list) -> dict:
    """
    Build a DICOM JSON dataset dict from a list of (tag_hex, vr, value) tuples.

    Tags with None / empty values are included with no ``Value`` key (per spec:
    servers may omit the key for zero-length values; omitting reduces payload).
    """
    result = {}
    for tag_hex, vr, value in tag_value_pairs:
        result[tag_hex.upper()] = tag_value(tag_hex, vr, value)
    return result


def _encode_pn(value: str) -> dict:
    """
    PN values are ``FAMILY^GIVEN^MIDDLE^PREFIX^SUFFIX``.
    MVP: only the Alphabetic component group (PS3.18 §F.2.2).
    """
    return {'Alphabetic': str(value)}


def _encode_date(value) -> str:
    """DICOM DA wire form: YYYYMMDD (no separators)."""
    if isinstance(value, date):
        return value.strftime('%Y%m%d')
    return str(value)[:8]


def _encode_time(value) -> str:
    """DICOM TM wire form: HHMMSS[.FFFFFF] (no colons)."""
    if isinstance(value, time):
        return value.strftime('%H%M%S')
    return str(value).replace(':', '')[:6]


def _scalar(vr: str, value):
    """
    Scalar encoding for non-PN, non-DA, non-TM VRs.
    IS/integer VRs encode as JSON numbers; DS/float VRs as JSON floats;
    everything else as strings (per PS3.18 §F.2.2).
    """
    if vr in ('IS', 'SL', 'SS', 'UL', 'US', 'UV'):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if vr in ('DS', 'FL', 'FD'):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return str(value) if value is not None else None
