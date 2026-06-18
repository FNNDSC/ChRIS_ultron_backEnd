"""
Unit tests for dicomweb.dicomjson — DICOM JSON Model (PS3.18 §F) helpers.
"""
from datetime import date, time

from django.test import SimpleTestCase

from dicomweb.dicomjson import dataset, tag_value
from dicomweb.renderers import DicomJsonRenderer


class TagValueTest(SimpleTestCase):

    def test_pn_encoding(self):
        result = tag_value('00100010', 'PN', 'DOE^JANE')
        self.assertEqual(result, {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]})

    def test_da_date_object(self):
        result = tag_value('00080020', 'DA', date(2023, 1, 2))
        self.assertEqual(result, {'vr': 'DA', 'Value': ['20230102']})

    def test_da_string_passthrough(self):
        result = tag_value('00080020', 'DA', '20230102')
        self.assertEqual(result, {'vr': 'DA', 'Value': ['20230102']})

    def test_tm_time_object(self):
        result = tag_value('00080030', 'TM', time(14, 30, 5))
        self.assertEqual(result, {'vr': 'TM', 'Value': ['143005']})

    def test_cs_single(self):
        result = tag_value('00080060', 'CS', 'CT')
        self.assertEqual(result, {'vr': 'CS', 'Value': ['CT']})

    def test_cs_multi(self):
        result = tag_value('00080060', 'CS', ['CT', 'MR'])
        self.assertEqual(result, {'vr': 'CS', 'Value': ['CT', 'MR']})

    def test_ui_value(self):
        uid = '1.2.840.10008.5.1.4.1.1.2'
        result = tag_value('00080016', 'UI', uid)
        self.assertEqual(result, {'vr': 'UI', 'Value': [uid]})

    def test_empty_string_omits_value(self):
        result = tag_value('00100010', 'PN', '')
        self.assertEqual(result, {'vr': 'PN'})
        self.assertNotIn('Value', result)

    def test_none_omits_value(self):
        result = tag_value('00080020', 'DA', None)
        self.assertEqual(result, {'vr': 'DA'})
        self.assertNotIn('Value', result)

    def test_binary_vr_raises(self):
        with self.assertRaises(ValueError):
            tag_value('7FE00010', 'OW', b'\x00\x00')

    def test_is_encodes_as_int(self):
        result = tag_value('00200013', 'IS', '42')
        self.assertEqual(result, {'vr': 'IS', 'Value': [42]})
        self.assertIsInstance(result['Value'][0], int)

    def test_ds_encodes_as_float(self):
        result = tag_value('00181164', 'DS', '3.14')
        self.assertAlmostEqual(result['Value'][0], 3.14)
        self.assertIsInstance(result['Value'][0], float)

    def test_dataset_builds_dict(self):
        pairs = [
            ('00100010', 'PN', 'DOE^JANE'),
            ('00080020', 'DA', date(2023, 6, 1)),
            ('00080060', 'CS', 'CT'),
        ]
        result = dataset(pairs)
        self.assertIn('00100010', result)
        self.assertIn('00080020', result)
        self.assertIn('00080060', result)
        self.assertEqual(result['00100010']['vr'], 'PN')
        self.assertEqual(result['00080020']['Value'], ['20230601'])

    def test_renderer_json_bytes(self):
        renderer = DicomJsonRenderer()
        data = [{'00100010': {'vr': 'PN', 'Value': [{'Alphabetic': 'DOE^JANE'}]}}]
        raw = renderer.render(data)
        self.assertIsInstance(raw, bytes)
        import json
        parsed = json.loads(raw.decode('utf-8'))
        self.assertEqual(parsed[0]['00100010']['vr'], 'PN')
