"""
DICOM native-model helpers.

Builds a framework-free, natively-typed intermediate representation of a DICOM
dataset — a ``list[DicomAttribute]`` — which ``dicomweb.renderers`` encodes into
the DICOM JSON Model (PS3.18 §F, ``application/dicom+json``). Values are stored
as the caller supplies them (raw strings, numbers, ``datetime`` objects, …),
always in their multi-value shape: a single value is wrapped as a
single-element list. Person Names are represented as a component-group
mapping (``{"Alphabetic": "DOE^JANE"}``, plus ``Ideographic`` / ``Phonetic``
when present), likewise wrapped.
The remaining JSON-Model encoding — IS/DS-as-number, empty/null handling and
the temporal wire-string form — lives in the renderer, since those rules belong
to the JSON Model, not the native model. Keeping this layer free of Django/DRF
makes it unit-testable in isolation.

VR classification is taken from pydicom (generated from PS3.5) so it never drifts
from the standard.
"""
import base64
import logging
from dataclasses import dataclass
from typing import Optional, Any

from pydicom.datadict import dictionary_VR
from pydicom.tag import Tag, TagType
from pydicom.valuerep import BYTES_VR, VR

logger = logging.getLogger(__name__)

# pydicom's VR enumeration (PS3.5-derived, includes the ambiguous
# data-dictionary combinations, which _check_vr's length check rejects).
_VALID_VRS = frozenset(VR)


def _check_vr(vr):
    if not isinstance(vr, str) or len(vr) != 2 or vr not in _VALID_VRS:
        # Every standard DICOM VR is a two-character member of pydicom's
        # PS3.5-derived VR set. The length check rejects the ambiguous
        # data-dictionary VRs ('US or SS', 'OB or OW') that the caller must
        # resolve; the membership check rejects bogus two-character strings
        # (e.g. a value bound into the vr slot); the type check rejects
        # non-strings (e.g. raw bytes). Unreachable for the fixed QIDO
        # attribute set.
        raise ValueError(f'Ambiguous or invalid VR {vr!r}; a concrete 2-char VR is '
                         f'required')


@dataclass
class DicomAttribute:
    tag: str
    VR: str
    value: Optional[list] = None
    item: Optional[list[list["DicomAttribute"]]] = None
    person_name: Optional[list[dict[str, str]]] = None
    bulk_data: Optional[str] = None     # uuid or uri
    inline_binary: Optional[bytes] = None

    def __post_init__(self):
        # Validated here, not only in dicom_attribute(), so a hand-built
        # attribute cannot carry a bogus VR into the renderer.
        _check_vr(self.VR)
        value_fields_count = sum([
            self.value is not None,
            self.item is not None,
            self.person_name is not None,
            self.bulk_data is not None,
            self.inline_binary is not None,
        ])
        if value_fields_count > 1:
            raise ValueError(f"Invalid DicomAttribute: {self}. Only one of [value, item, "
                             f"person_name, bulk_data, inline_binary] may be set.")

    def get_value(self):
        """
        Get the non-binary value if there is one
        """
        for val in [self.value, self.item, self.person_name]:
            if val is not None:
                return val
        return None

    def get_inline_binary(self) -> Optional[bytes]:
        data = self.inline_binary
        if data is None:
            return None
        return base64.b64encode(data)


def normalize_tag(tag: TagType) -> str:
    """
    Canonical 8-char uppercase hex for any tag ``pydicom.tag.Tag`` accepts:
    an int, a ``'00100010'`` hex string, a ``(group, elem)``
    tuple, or a DICOM keyword such as ``'PatientName'``.
    """
    return f'{Tag(tag):08X}'


def dicom_attribute(tag, value, vr=None) -> DicomAttribute:
    """
    Build a :class:`DicomAttribute` for ``tag``/``value``.

    ``vr`` defaults to the DICOM data-dictionary VR of ``tag``. The value is
    stored in its multi-value shape: a single value is wrapped as a
    single-element list, and PN is encoded to its native component-group
    mapping (wrapped the same way). An SQ value is stored in the ``item``
    field as a list of item datasets, a bare single-item dataset being wrapped
    as a one-item sequence. The renderer performs the remaining JSON-Model
    coercion (including rejecting binary VRs). Raises :class:`ValueError` for
    an unknown tag (VR lookup fails) or any VR outside pydicom's PS3.5 VR
    set — ambiguous data-dictionary VRs ('US or SS', 'OB or OW') and
    non-standard or non-string values included.
    """
    tag_hex = normalize_tag(tag)
    if vr is None:
        try:
            vr = dictionary_VR(tag)
        except KeyError:
            # Unknown/private tag (e.g. (0009,1001)) or group length —
            # unreachable for the fixed QIDO attribute set.
            err_msg = f'Unknown tag {tag!r}; no VR in the DICOM data dictionary'
            raise ValueError(err_msg) from None
    # Checked before the VR-specific branches, which assume a hashable VR.
    _check_vr(vr)
    if vr == 'PN':
        return DicomAttribute(tag_hex, vr, person_name=_as_value_list(_encode_pn(value)))
    if vr == 'SQ':
        return DicomAttribute(tag_hex, vr, item=_as_sq_items(value))
    if vr in BYTES_VR:
        return DicomAttribute(tag_hex, vr, inline_binary=value)
    # TODO: handle bulk data
    return DicomAttribute(tag_hex, vr, value=_as_value_list(value))


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
    component_groups = value.split('=')
    if len(component_groups) > len(component_labels):
        # PS3.5 §6.2 allows at most two "=" group delimiters. Keep the first
        # three groups, as pydicom does: PN values come from stored PACS data,
        # so raising would fail a whole QIDO response over one malformed name.
        # The value itself is PHI and is deliberately not logged.
        logger.warning('PN value has %d component groups; only the first %d are kept',
                       len(component_groups), len(component_labels))
    encoded_pn = {}
    for label, group in zip(component_labels, component_groups):
        # A non-empty group string is kept verbatim, delimiters included: a
        # group of empty components such as "^^^^" is a present Alphabetic
        # value, distinct from an absent group — §F.2.2 keeps the Data
        # Element representation (matches pydicom).
        if group:
            encoded_pn[label] = group
    return encoded_pn


def _as_value_list(value):
    """
    The value fields of :class:`DicomAttribute` are always lists (the DICOM
    JSON Model ``Value`` is an array): ``None`` (empty attribute) and lists
    pass through unchanged, tuples are converted to lists, and any other
    single value is wrapped as a single-element list.
    """
    if value is None or isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_sq_items(value):
    """
    SQ shape distinction: a sequence's items are themselves datasets
    (``list[DicomAttribute]``), so a bare single-item dataset — itself a
    list — is indistinguishable from a list of items by type alone. A list
    whose elements are all :class:`DicomAttribute` is therefore a bare item
    dataset, wrapped as a one-item sequence; a list of item datasets passes
    through unchanged. ``None`` and ``[]`` (empty sequence) stay as
    supplied — the renderer omits their ``Value`` (§F.2.5).
    """
    if (isinstance(value, list) and value
            and all(isinstance(elem, DicomAttribute) for elem in value)):
        return [value]
    return _as_value_list(value)


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
