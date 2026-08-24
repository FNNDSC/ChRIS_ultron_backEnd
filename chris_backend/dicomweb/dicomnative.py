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
import base64
from dataclasses import dataclass, field
from collections import namedtuple
from typing import Optional, Any

from pydicom.datadict import dictionary_VR
from pydicom.tag import Tag, TagType


@dataclass
class DicomAttribute:
    tag: str
    VR: str
    value: Optional[list] = None
    item: Optional[list["DicomAttribute"]] = None
    person_name: Optional[list[dict[str]]] = None
    bulk_data: Optional[str] = None     # uuid or uri
    inline_binary: Optional[bytes] = None

    def __post_init__(self):
        value_fields_count = sum([
            self.value is not None,
            self.item is not None,
            self.person_name is not None,
            self.bulk_data is not None,
            self.inline_binary is not None,
        ])
        if value_fields_count > 1:
            raise ValueError(f"Invalid DicomAttribute: {self}. Only one of [value, item, person_name, bulk_data, inline_binary] may be set.")

    def get_value(self):
        """Get the non-binary value if there is one"""
        for val in [self.value, self.item, self.person_name]:
            if val is not None:
                return val
        return None

    def get_inline_binary(self) -> bytes:
        data = self.inline_binary
        if data is None:
            return None
        return base64.b64encode(data)


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
        return DicomAttribute(tag_hex, vr, person_name=_encode_pn(val))
    return DicomAttribute(tag_hex, vr, value)


_PN_COMPONENT_LABELS = ['Alphabetic', 'Ideographic', 'Phonetic']


def _encode_pn(value):
    """
    Native-model Person Name: map of component groups to ^-delimited
    strings. Empty values are left untouched for the renderer's §F.2.5
    empty/null handling.
    """
    # Encode the string to a dict representation per PS 3.5 §6.2
    component_labels = _PN_COMPONENT_LABELS
    if not value:
        return value
    if isinstance(value, (list, tuple)):
        return [_encode_pn(elem) for elem in value]
    if isinstance(value, dict):
        for key in value.keys():
            if key not in component_labels:
                raise ValueError(f'Unexpected key in PN value: {key}')
        return value
    # At this point, we should only have a string
    if not isinstance(value, str):
        raise ValueError(f'Unable to encode PN value: {value}')
    component_groups = value.split('=', maxsplit=3)
    encoded_pn = {}
    for label, group in zip(component_labels, component_groups):
        components = group.split('^', maxsplit=5)
        if any(components):
            encoded_pn[label] = group
    return encoded_pn


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
        # Short-circuit already-constructed DicomAttribute
        if isinstance(item, DicomAttribute):
            result.append(item)
            continue
        if len(item) == 3:
            tag, vr, value = item
        else:
            (tag, value), vr = item, None
        result.append(dicom_attribute(tag, value, vr=vr))
    return result
