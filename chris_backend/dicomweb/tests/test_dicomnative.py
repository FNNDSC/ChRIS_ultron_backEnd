"""
Unit tests for dicomweb.dicomnative (native-model builder).
"""
from datetime import date

from django.test import SimpleTestCase

from dicomweb.dicomnative import (
    DicomAttribute,
    dataset,
    dicom_attribute,
    normalize_tag,
)


class NormalizeTagTest(SimpleTestCase):

    def test_hex_string(self):
        self.assertEqual(normalize_tag('00100010'), '00100010')

    def test_int(self):
        self.assertEqual(normalize_tag(0x00100010), '00100010')

    def test_group_element_tuple(self):
        self.assertEqual(normalize_tag((0x0010, 0x0010)), '00100010')

    def test_keyword(self):
        self.assertEqual(normalize_tag('PatientName'), '00100010')

    def test_lowercase_is_uppercased(self):
        self.assertEqual(normalize_tag('7fe00010'), '7FE00010')


class DicomAttributeTest(SimpleTestCase):
    """The native-model builder normalizes the tag, resolves the VR, and stores
    the value in its multi-value shape (coercion is the renderer's job)."""

    def test_vr_derived_from_data_dictionary(self):
        attr = dicom_attribute('PatientName', 'DOE^JANE')
        self.assertEqual(attr, DicomAttribute('00100010', 'PN', person_name=[{'Alphabetic': 'DOE^JANE'}]))

    def test_pn_encoded_as_alphabetic_mapping(self):
        # PN is part of the native model — stored as its component mapping.
        self.assertEqual(
            dicom_attribute('00100010', 'DOE^JANE').person_name,
            [{'Alphabetic': 'DOE^JANE'}]
        )
        self.assertEqual(
            dicom_attribute('00100010', 'Yamada^Tarou=山田^太郎=やまだ^たろう').person_name,
            [{
                'Alphabetic': 'Yamada^Tarou',
                'Phonetic': 'やまだ^たろう',
                'Ideographic': '山田^太郎',
            }]
        )
        self.assertEqual(
            dicom_attribute('00100010', 'Yamada^Tarou==やまだ^たろう').person_name,
            [{
                'Alphabetic': 'Yamada^Tarou',
                'Phonetic': 'やまだ^たろう',
            }]
        )
        self.assertEqual(
            dicom_attribute('00100010', '==やまだ^たろう').person_name,
            [{'Phonetic': 'やまだ^たろう',}]
        )
        self.assertEqual(
            dicom_attribute('00100010', '=山田^太郎=').person_name,
            [{'Ideographic': '山田^太郎',}]
        )
        self.assertEqual(
            dicom_attribute('00100010', '=山田^太郎=').person_name,
            dicom_attribute('00100010', '=山田^太郎').person_name,
        )

    def test_multi_valued_pn_encoded_element_wise(self):
        # A multi-valued PN stays a list of component mappings.
        self.assertEqual(
            dicom_attribute('00100010', ['DOE^JANE', 'SMITH^JOHN']).person_name,
            [{'Alphabetic': 'DOE^JANE'}, {'Alphabetic': 'SMITH^JOHN'}]
        )

    def test_pn_mapping_value_passed_through(self):
        # An already-encoded component mapping round-trips unchanged (just
        # wrapped in its single-element list); unknown component groups are
        # rejected (PS3.5 §6.2 allows only the three groups).
        self.assertEqual(
            dicom_attribute('00100010', {'Alphabetic': 'DOE^JANE'}).person_name,
            [{'Alphabetic': 'DOE^JANE'}]
        )
        self.assertEqual(
            dicom_attribute('00100010', [{'Alphabetic': 'A'}, {'Phonetic': 'B'}]).person_name,
            [{'Alphabetic': 'A'}, {'Phonetic': 'B'}]
        )
        with self.assertRaises(ValueError):
            dicom_attribute('00100010', {'GivenName': 'DOE^JANE'})

    def test_pn_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            dicom_attribute('00100010', 42)

    def test_delimiter_only_pn_groups_kept_verbatim(self):
        # "^^^^" is a present Alphabetic group whose five components are all
        # empty — a non-empty group string, kept verbatim (§F.2.2 keeps the
        # Data Element representation; matches pydicom). "==" has only
        # absent groups, so it encodes as an empty object.
        self.assertEqual(
            dicom_attribute('00100010', '^^^^').person_name,
            [{'Alphabetic': '^^^^'}],
        )
        self.assertEqual(dicom_attribute('00100010', '==').person_name, [{}])

    def test_pn_extra_component_groups_dropped_with_warning(self):
        # PS3.5 §6.2 allows at most two "=" delimiters. Extra groups are
        # dropped as pydicom does (not folded into Phonetic), with a warning
        # that must not carry the name itself (PHI).
        with self.assertLogs('dicomweb.dicomnative', 'WARNING') as logs:
            person_name = dicom_attribute('00100010', 'a^x=b^y=c^z=d^w').person_name
        self.assertEqual(
            person_name,
            [{'Alphabetic': 'a^x', 'Ideographic': 'b^y', 'Phonetic': 'c^z'}],
        )
        self.assertEqual(len(logs.output), 1)
        self.assertNotIn('a^x', logs.output[0])
        self.assertNotIn('d^w', logs.output[0])

    def test_empty_pn_left_for_renderer(self):
        # Empty PN is not turned into a mapping — the renderer omits it (§F.2.5).
        self.assertIsNone(dicom_attribute('00100010', None).person_name)
        self.assertEqual(dicom_attribute('00100010', '').person_name, [''])

    def test_non_pn_value_stored_unchanged(self):
        # Value content is preserved — no int coercion, no empty→None — with
        # single values wrapped as single-element lists.
        self.assertEqual(dicom_attribute('00200013', '42').value, ['42'])
        self.assertEqual(dicom_attribute('00080020', date(2023, 1, 2)).value,
                         [date(2023, 1, 2)])
        self.assertEqual(dicom_attribute('00080060', ['CT', 'MR']).value, ['CT', 'MR'])
        self.assertEqual(dicom_attribute('00080060', ('CT', 'MR')).value, ['CT', 'MR'])

    def test_sq_value_stored_as_item(self):
        # SQ values live in the item field: a list of item datasets is stored
        # as supplied, an empty sequence stays empty (renderer omits Value).
        item = dataset([('00080060', 'CS', 'CT')])
        self.assertEqual(dicom_attribute('00081115', [item]).item, [item])
        self.assertIsNone(dicom_attribute('00081115', None).item)
        self.assertEqual(dicom_attribute('00081115', []).item, [])

    def test_sq_bare_item_dataset_wrapped_as_single_item(self):
        # A bare item dataset (list[DicomAttribute]) is one sequence item —
        # wrapped as a one-item sequence, since a list of items is a list of
        # datasets.
        item = dataset([('00080060', 'CS', 'CT')])
        self.assertEqual(dicom_attribute('00081115', item).item, [item])

    def test_binary_value_stored_as_inline_binary(self):
        # Binary VRs (pydicom BYTES_VR) are carried as raw bytes in
        # inline_binary, never in value — the renderer rejects them at the
        # QIDO surface.
        attr = dicom_attribute('7FE00010', b'\x00\x01', vr='OW')
        self.assertEqual(attr.inline_binary, b'\x00\x01')
        self.assertIsNone(attr.value)
        self.assertIsNone(attr.item)

    def test_multiple_value_fields_rejected(self):
        # At most one of [value, item, person_name, bulk_data, inline_binary].
        with self.assertRaises(ValueError):
            DicomAttribute('00100010', 'PN', value=['x'],
                           person_name=[{'Alphabetic': 'x'}])

    def test_get_inline_binary(self):
        # None when unset; base64 of the raw bytes otherwise (§F.2.7).
        self.assertIsNone(DicomAttribute('00100010', 'PN').get_inline_binary())
        self.assertEqual(
            DicomAttribute('7FE00010', 'OW', inline_binary=b'\x00\x01').get_inline_binary(),
            b'AAE=',
        )

    def test_explicit_vr_overrides_dictionary(self):
        self.assertEqual(dicom_attribute('00080016', 'x', vr='UI').VR, 'UI')

    def test_non_two_char_vr_raises(self):
        # Ambiguous data-dictionary VRs ('US or SS', 'OB or OW') must be rejected.
        with self.assertRaises(ValueError):
            dicom_attribute('7FE00010', b'\x00', vr='OB or OW')
        with self.assertRaises(ValueError):
            dicom_attribute('00280106', 0, vr='US or SS')

    def test_non_standard_vr_raises(self):
        # VRs are validated against pydicom's PS3.5-derived VR set, not just
        # by length: a two-character string that is not a VR (the dataset()
        # (tag, vr, value) misbinding trap) and non-string VRs both raise.
        with self.assertRaises(ValueError):
            dicom_attribute('00080060', 'MR', vr='CT')
        with self.assertRaises(ValueError):
            dicom_attribute('7FE00010', b'\x00\x01', vr=b'OW')
        with self.assertRaises(ValueError):
            dataset([('00080060', 'CT', 'MR')])   # meant Modality = CT and MR

    def test_hand_built_attribute_vr_validated(self):
        # The VR check lives in DicomAttribute itself, so an attribute built
        # without dicom_attribute() is held to it too — empty or not.
        for vr in ('XX', 'US or SS', b'CS', None):
            with self.assertRaises(ValueError):
                DicomAttribute('00080060', vr)
        with self.assertRaises(ValueError):
            DicomAttribute('00080060', 'XX', value=['CT'])

    def test_unknown_tag_raises_value_error(self):
        # A private/unknown tag has no data-dictionary VR — the documented
        # ValueError, not KeyError leaking from pydicom's dictionary_VR.
        with self.assertRaises(ValueError):
            dicom_attribute('00091001', 'x')


class DatasetTest(SimpleTestCase):

    def test_builds_attribute_list(self):
        result = dataset([
            ('00100010', 'PN', 'DOE^JANE'),   # (tag, vr, value)
            ('00080020', date(2023, 6, 1)),   # (tag, value) — VR derived
            ('00080060', 'CT'),
            DicomAttribute('00100010', 'PN', person_name=[{'Alphabetic': 'PATIENT^TWO'}]),
        ])
        self.assertEqual(
            result,
            [
                DicomAttribute('00100010', 'PN', person_name=[{'Alphabetic': 'DOE^JANE'}]),
                DicomAttribute('00080020', 'DA', value=[date(2023, 6, 1)]),
                DicomAttribute('00080060', 'CS', value=['CT']),
                DicomAttribute('00100010', 'PN', person_name=[{'Alphabetic': 'PATIENT^TWO'}]),
            ],
        )

    def test_prebuilt_dicom_attribute_passed_through(self):
        # A DicomAttribute is a length-3 tuple; it must not be re-encoded
        # (which would double-wrap a PN mapping).
        attr = dicom_attribute('00100010', 'DOE^JANE')
        self.assertEqual(dataset([attr]), [attr])
