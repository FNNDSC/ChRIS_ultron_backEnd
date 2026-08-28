"""
Unit tests for dicomweb.dicomnative (native-model builder) and dicomweb.renderers
(DICOM JSON Model encoding, PS3.18 §F).
"""
import json
from datetime import date, datetime, time, timedelta, timezone

from django.test import SimpleTestCase

from dicomweb.dicomnative import (
    DicomAttribute,
    dataset,
    dicom_attribute,
    normalize_tag,
)
from dicomweb.renderers import DicomJsonEncoder, DicomJsonRenderer


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


class DicomJsonEncoderTest(SimpleTestCase):
    """Temporal wire-string encoding, including fractional seconds."""

    def _encode(self, obj):
        return json.loads(json.dumps(obj, cls=DicomJsonEncoder))

    def test_datetime_with_microseconds(self):
        self.assertEqual(
            self._encode(datetime(2023, 1, 2, 14, 30, 5, 123456)),
            '20230102143005.123456',
        )

    def test_time_with_microseconds(self):
        self.assertEqual(self._encode(time(14, 30, 5, 123456)), '143005.123456')

    def test_tz_aware_datetime_gets_offset_suffix(self):
        # DICOM DT "&ZZXX" UTC-offset suffix (§F / PS3.5 DT VR).
        east = datetime(2023, 1, 2, 14, 30, 5, tzinfo=timezone(timedelta(hours=5)))
        self.assertEqual(self._encode(east), '20230102143005+0500')
        west = datetime(2023, 1, 2, 14, 30, 5, 123456,
                        tzinfo=timezone(timedelta(hours=-4, minutes=-30)))
        self.assertEqual(self._encode(west), '20230102143005.123456-0430')

    def test_naive_datetime_has_no_offset(self):
        self.assertEqual(self._encode(datetime(2023, 1, 2, 14, 30, 5)),
                         '20230102143005')

    def test_unknown_type_defers_to_drf_encoder(self):
        # A type this encoder does not handle falls through to DRF's encoder,
        # which serializes a set as a JSON array.
        self.assertEqual(self._encode({'X'}), ['X'])

    def test_dicom_attribute_encoded_as_json_model_object(self):
        # A DicomAttribute reaching the encoder is emitted as its JSON Model
        # object {"TAG": {"vr": …, "Value": […]}} (§F.2.2). An empty attribute
        # emits only "vr" — no Value/BulkDataURI/InlineBinary key (§F.2.5).
        self.assertEqual(
            self._encode(DicomAttribute('00100010', 'PN',
                                        person_name=[{'Alphabetic': 'DOE^JANE'}])),
            {'00100010': {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]}},
        )
        self.assertEqual(
            self._encode(DicomAttribute('00080060', 'CS')),
            {'00080060': {'vr': 'CS'}},
        )

    def test_dicom_attribute_bulk_data_uri(self):
        # bulk_data → BulkDataURI string (§F.2.6). Not reachable from the
        # QIDO dataset path (binary VRs are rejected in _render_dataset);
        # exercised directly for the future WADO-RS surface.
        self.assertEqual(
            self._encode(DicomAttribute('7FE00010', 'OW', bulk_data='http://x/bulk')),
            {'7FE00010': {'vr': 'OW', 'BulkDataURI': 'http://x/bulk'}},
        )

    def test_dicom_attribute_inline_binary(self):
        # inline_binary → InlineBinary base64 string (§F.2.7).
        self.assertEqual(
            self._encode(DicomAttribute('7FE00010', 'OW', inline_binary=b'\x00\x01')),
            {'7FE00010': {'vr': 'OW', 'InlineBinary': 'AAE='}},
        )


class DicomJsonRendererTest(SimpleTestCase):
    """The renderer applies all DICOM JSON Model encoding (PS3.18 §F)."""

    def _render(self, data):
        raw = DicomJsonRenderer().render(data)
        self.assertIsInstance(raw, bytes)
        return json.loads(raw.decode('utf-8'))

    def _element(self, tag, vr, value):
        return self._render(dataset([(tag, vr, value)]))[0][tag]

    def test_single_dataset_wrapped_in_array(self):
        parsed = self._render(dataset([('00100010', 'PN', 'DOE^JANE')]))
        self.assertEqual(
            parsed,
            [{'00100010': {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]}}],
        )

    def test_bare_attribute_wrapped_in_array(self):
        # A bare DicomAttribute is a one-attribute dataset — still an array.
        parsed = self._render(DicomAttribute('00080060', 'CS', value=['CT']))
        self.assertEqual(parsed, [{'00080060': {'vr': 'CS', 'Value': ['CT']}}])

    def test_scalar_value_rendered_as_single_element_list(self):
        # A hand-built DicomAttribute with an unwrapped scalar value still
        # renders as a one-element Value array.
        parsed = self._render([
            DicomAttribute('00080060', 'CS', value='CT'),
            DicomAttribute('00100010', 'PN', person_name={'Alphabetic': 'DOE^JANE'}),
        ])
        self.assertEqual(parsed, [{
            '00080060': {'vr': 'CS', 'Value': ['CT']},
            '00100010': {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]},
        }])

    def test_pn_encoded_as_alphabetic_object(self):
        self.assertEqual(
            self._element('00100010', 'PN', 'DOE^JANE'),
            {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]},
        )

    def test_multi_valued_pn_rendered_as_array_of_objects(self):
        self.assertEqual(
            self._element('00100010', 'PN', ['DOE^JANE', 'SMITH^JOHN']),
            {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'},
                                   {'Alphabetic': 'SMITH^JOHN'}]},
        )

    def test_cs_single_and_multi(self):
        self.assertEqual(self._element('00080060', 'CS', 'CT')['Value'], ['CT'])
        self.assertEqual(
            self._element('00080060', 'CS', ['CT', 'MR'])['Value'], ['CT', 'MR']
        )

    def test_integer_vrs_encoded_as_int(self):
        # IS/US/SV/UV (and UL/SL/SS) → JSON integer (pydicom INT_VR minus AT).
        for tag, vr in [('00200013', 'IS'), ('00280010', 'US'),
                        ('00000000', 'SV'), ('00000000', 'UV')]:
            value = self._element(tag, vr, '42')['Value']
            self.assertEqual(value, [42])
            self.assertIsInstance(value[0], int)

    def test_float_vrs_encoded_as_float(self):
        # DS/FL/FD → JSON float. §F.2.3 lists DS/IS/SV/UV as "Number or String";
        # per the atlas QIDO reference we follow pydicom and emit numbers, so a
        # DS decimal string is coerced to float (precision not preserved).
        self.assertEqual(self._element('00189306', 'FD', '2.5')['Value'], [2.5])
        value = self._element('00181164', 'DS', '3.140000')['Value']
        self.assertEqual(value, [3.14])
        self.assertIsInstance(value[0], float)

    def test_at_encoded_as_hex_string(self):
        # AT is in pydicom INT_VR but DICOM JSON encodes it as an 8-char hex
        # string. Tag() makes it idempotent across int / hex-string / tuple input.
        self.assertEqual(
            self._element('00280009', 'AT', 0x00100010)['Value'], ['00100010']
        )
        self.assertEqual(
            self._element('00280009', 'AT', '00100010')['Value'], ['00100010']
        )

    def test_binary_vr_rejected(self):
        # Bulk data must not reach the QIDO surface; rejected here, not in the
        # native builder. Fires even for an empty binary attribute.
        for vr in ('OW', 'OV', 'OB', 'UN'):
            with self.assertRaises(ValueError):
                self._render(dataset([('7FE00010', vr, b'\x00')]))
        with self.assertRaises(ValueError):
            self._render(dataset([('7FE00010', 'OW', None)]))

    def test_string_vrs_not_rejected_as_binary(self):
        # UR/UC/UT are string VRs, not binary. RetrieveURL (0008,1190) is VR UR,
        # a standard QIDO return attribute — must render as a string.
        self.assertEqual(self._element('00081190', 'UR', 'http://x')['Value'],
                         ['http://x'])
        self.assertEqual(self._element('00081196', 'UT', 't')['Value'], ['t'])
        self.assertEqual(self._element('00080104', 'UC', 'c')['Value'], ['c'])

    def test_sq_empty_omits_value(self):
        # SQ is a structured VR, not binary — an empty sequence just omits Value.
        self.assertEqual(self._element('00081115', 'SQ', None), {'vr': 'SQ'})

    def test_sq_renders_nested_datasets(self):
        # §F.2.2: a sequence Value is an array of DICOM JSON objects, one per
        # item; each item is a dataset (list[DicomAttribute]) rendered recursively.
        item = dataset([('00080060', 'CS', 'CT'), ('0020000E', 'UI', '1.2.3')])
        self.assertEqual(
            self._element('00081115', 'SQ', [item]),
            {'vr': 'SQ', 'Value': [{
                '00080060': {'vr': 'CS', 'Value': ['CT']},
                '0020000E': {'vr': 'UI', 'Value': ['1.2.3']},
            }]},
        )

    def test_sq_multiple_items_and_empty_item(self):
        # Multiple items preserved in order; an empty item → {} (§F.2.5).
        item = dataset([('00080060', 'CS', 'CT')])
        self.assertEqual(
            self._element('00081115', 'SQ', [item, []])['Value'],
            [{'00080060': {'vr': 'CS', 'Value': ['CT']}}, {}],
        )

    def test_sq_bare_item_dataset_rendered_as_single_item(self):
        # A bare item dataset is wrapped as one sequence item.
        item = dataset([('00080060', 'CS', 'CT')])
        self.assertEqual(
            self._element('00081115', 'SQ', item)['Value'],
            [{'00080060': {'vr': 'CS', 'Value': ['CT']}}],
        )

    def test_sq_explicit_empty_item_rendered_as_empty_object(self):
        # [[]] is one empty item → Value: [{}] (§F.2.5) — distinct from an
        # empty sequence, which omits Value entirely.
        self.assertEqual(
            self._element('00081115', 'SQ', [[]]),
            {'vr': 'SQ', 'Value': [{}]},
        )

    def test_sq_nested_sequence(self):
        # Recursion: a sequence item that itself contains a sequence.
        inner = dataset([('00080060', 'CS', 'CT')])
        outer_item = dataset([('00081140', 'SQ', [inner])])   # ReferencedImageSequence
        self.assertEqual(
            self._element('00081115', 'SQ', [outer_item])['Value'],
            [{'00081140': {'vr': 'SQ',
                           'Value': [{'00080060': {'vr': 'CS', 'Value': ['CT']}}]}}],
        )

    def test_temporal_values_rendered_as_wire_strings(self):
        parsed, = self._render(dataset([
            ('00080020', date(2023, 1, 2)),
            ('00080030', time(14, 30, 5)),
            ('0008002A', datetime(2023, 1, 2, 14, 30, 5)),   # DT
        ]))
        self.assertEqual(parsed['00080020'], {'vr': 'DA', 'Value': ['20230102']})
        self.assertEqual(parsed['00080030'], {'vr': 'TM', 'Value': ['143005']})
        self.assertEqual(
            parsed['0008002A'], {'vr': 'DT', 'Value': ['20230102143005']}
        )

    def test_attributes_sorted_lexicographically(self):
        # §F.2.2 "shall": attribute objects ordered by property name ascending,
        # regardless of construction order. json.loads preserves document
        # order, so asserting on the key sequence really checks the wire form.
        parsed, = self._render(dataset([
            ('0020000D', 'UI', '1.2.3'),      # StudyInstanceUID
            ('00100010', 'PN', 'DOE^JANE'),   # PatientName
            ('00080020', 'DA', date(2023, 1, 1)),
        ]))
        self.assertEqual(list(parsed), ['00080020', '00100010', '0020000D'])

    def test_nested_sequence_items_sorted_lexicographically(self):
        # SQ items recurse through _render_dataset, so nested attribute
        # objects are sorted too.
        item = dataset([
            ('0020000E', 'UI', '1.2.3.4'),    # SeriesInstanceUID
            ('00080060', 'CS', 'CT'),
        ])
        parsed, = self._render(dataset([('00081115', 'SQ', [item])]))
        self.assertEqual(list(parsed['00081115']['Value'][0]),
                         ['00080060', '0020000E'])

    def test_preformatted_temporal_string_passes_through(self):
        self.assertEqual(self._element('00080020', 'DA', '20230102')['Value'],
                         ['20230102'])

    def test_datetime_narrowed_to_date_for_da(self):
        # A datetime supplied for a DA attribute is narrowed to its date —
        # the full 14-char DT wire form is not a valid DA value.
        self.assertEqual(
            self._element('00080020', 'DA', datetime(2023, 1, 2, 14, 30, 5))['Value'],
            ['20230102'],
        )
        self.assertEqual(
            self._element('00080020', 'DA', datetime(2023, 1, 2, 14, 30, 5, 123456))['Value'],
            ['20230102'],
        )

    def test_datetime_narrowed_to_time_for_tm(self):
        # A datetime supplied for a TM attribute is narrowed to its time;
        # fractional seconds are preserved per the TM wire form.
        self.assertEqual(
            self._element('00080030', 'TM', datetime(2023, 1, 2, 14, 30, 5))['Value'],
            ['143005'],
        )
        self.assertEqual(
            self._element('00080030', 'TM', datetime(2023, 1, 2, 14, 30, 5, 123456))['Value'],
            ['143005.123456'],
        )

    def test_empty_attribute_omits_value_key(self):
        for empty in (None, '', []):
            element = self._element('00100010', 'PN', empty)
            self.assertEqual(element, {'vr': 'PN'})
            self.assertNotIn('Value', element)

    def test_multivalued_empty_element_rendered_as_json_null(self):
        # §F.2.5: empty elements are null, not dropped and never "".
        self.assertEqual(
            self._element('00080060', 'CS', ['CT', '', 'MR'])['Value'],
            ['CT', None, 'MR'],
        )

    def test_all_empty_multivalue_preserves_multiplicity_as_nulls(self):
        # §F.2.5: a multi-valued attribute with one or more empty values keeps
        # them as null array elements — VM and position preserved even when
        # every element is empty (Value Length > 0 in the binary encoding).
        self.assertEqual(
            self._element('00080060', 'CS', ['', None])['Value'],
            [None, None],
        )
        self.assertEqual(
            self._element('00080060', 'CS', ['', ''])['Value'],
            [None, None],
        )

    def test_single_empty_multivalue_element_is_empty_attribute(self):
        # A single empty element is VM=1 with Value Length 0 — an empty
        # attribute (§F.2.5), not a one-element [null] array.
        element = self._element('00080060', 'CS', [''])
        self.assertEqual(element, {'vr': 'CS'})
        self.assertNotIn('Value', element)

    def test_non_numeric_value_raises_at_render(self):
        # Bad data for a numeric VR fails during serialization, not silently.
        with self.assertRaises(ValueError):
            self._render(dataset([('00200013', 'IS', 'not-a-number')]))

    def test_multiple_datasets(self):
        parsed = self._render([
            dataset([('00080060', 'CT')]),
            dataset([('00080060', 'MR')]),
        ])
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][0]['00080060']['Value'], ['CT'])
        self.assertEqual(parsed[1][0]['00080060']['Value'], ['MR'])

    def test_empty_result_is_empty_array(self):
        self.assertEqual(self._render([]), [])

    def test_non_list_payload_passed_through(self):
        # A non-list payload (e.g. a DRF error dict) is passed through untouched
        # rather than treated as a dataset — avoids a KeyError on data[0].
        self.assertEqual(self._render({'detail': 'not found'}), {'detail': 'not found'})
