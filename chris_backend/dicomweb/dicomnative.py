"""
DICOM native-model helpers.

Builds a framework-free, natively-typed intermediate representation of a DICOM
dataset — a ``list[DicomAttribute]`` — which ``dicomweb.renderers`` encodes into
the DICOM JSON Model (PS3.18 §F, ``application/dicom+json``). Values are stored
as the caller supplies them (raw strings, numbers, ``datetime`` objects, …),
except Person Names, which the native model represents as a component mapping
(``{"Alphabetic": "DOE^JANE"}``; Alphabetic group only here). The remaining
JSON-Model encoding — IS/DS-as-number, empty/null handling and the temporal
wire-string form — lives in the renderer, since those rules belong to the JSON
Model, not the native model. Keeping this layer free of Django/DRF makes it
unit-testable in isolation.

VR classification is taken from pydicom (generated from PS3.5) so it never drifts
from the standard.
"""
from collections import namedtuple
from typing import Any

from pydicom.datadict import dictionary_VR
from pydicom.tag import Tag, TagType


# One attribute of a dataset: canonical 8-hex ``tag``, its ``VR``, and the raw
# ``Value`` (scalar, list, ``datetime``, or ``None``) exactly as supplied. The
# renderer performs all DICOM JSON Model coercion.
DicomAttribute = namedtuple('DicomAttribute', ['tag', 'VR', 'Value'])


def normalize_tag(tag: TagType) -> str:
    """
    Canonical 8-char uppercase hex for any tag ``pydicom.tag.Tag`` accepts:
    an int, a ``'0010,0010'`` / ``'00100010'`` hex string, a ``(group, elem)``
    tuple, or a DICOM keyword such as ``'PatientName'``.
    """
    return f'{Tag(tag):08X}'


def dicom_attribute(tag, value, vr=None) -> DicomAttribute:
    """
    Build a :class:`DicomAttribute` for ``tag``/``value``.

    ``vr`` defaults to the DICOM data-dictionary VR of ``tag``. ``Value`` is
    stored as supplied, except PN which is encoded to its native Alphabetic
    component mapping; the renderer performs the remaining JSON-Model coercion
    (including rejecting binary VRs). Raises :class:`ValueError` for any
    non-2-character (ambiguous/invalid) VR.
    """
    tag_hex = normalize_tag(tag)
    if vr is None:
        vr = dictionary_VR(tag)
    if len(vr) != 2:
        # Every standard DICOM VR is exactly two characters. Anything else is an
        # ambiguous data-dictionary VR (e.g. 'US or SS', 'OB or OW') that the
        # caller must resolve — unreachable for the fixed QIDO attribute set.
        raise ValueError(f'Ambiguous or invalid VR {vr!r}; a concrete 2-char VR is required')
    if vr == 'PN':
        value = _encode_pn(value)
    return DicomAttribute(tag_hex, vr, value)


def _encode_pn(value):
    """
    Native-model Person Name: the Alphabetic component mapping
    (``{"Alphabetic": "DOE^JANE"}``). Multi-valued input maps element-wise.
    Empty values are left untouched for the renderer's §F.2.5 empty/null
    handling.
    """
    if isinstance(value, (list, tuple)):
        return [_encode_pn(v) for v in value]
    if value is None or value == '':
        return value
    return {'Alphabetic': str(value)}


def dataset(
    attributes: list[DicomAttribute | tuple[TagType, Any] | tuple[TagType, str, Any]],
) -> list[DicomAttribute]:
    """
    Build a ``list[DicomAttribute]`` from an iterable of ``(tag, value)`` or
    ``(tag, vr, value)`` items. When VR is omitted it is looked up in the DICOM
    data dictionary. An already-built :class:`DicomAttribute` is passed through
    unchanged.
    """
    result = []
    for item in attributes:
        # A DicomAttribute is itself a length-3 tuple, so this must precede the
        # ``len(item) == 3`` unpacking or it would be re-encoded (double-wrapping
        # a PN mapping, in particular).
        if isinstance(item, DicomAttribute):
            result.append(item)
            continue
        if len(item) == 3:
            tag, vr, value = item
        else:
            (tag, value), vr = item, None
        result.append(dicom_attribute(tag, value, vr))
    return result
