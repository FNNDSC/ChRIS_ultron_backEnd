"""
Unit tests for dicomweb.query — QIDO-RS DICOM-tag query parser.
"""
from django.http import QueryDict
from django.test import TestCase

from dicomweb.query import QueryFilter, TAG_MAP_SERIES, TAG_MAP_STUDY, _parse_da


class ParseDaTest(TestCase):

    def test_valid_date(self):
        from datetime import date
        self.assertEqual(_parse_da('20230102'), date(2023, 1, 2))

    def test_invalid_date_returns_none(self):
        self.assertIsNone(_parse_da('not-a-date'))

    def test_empty_returns_none(self):
        self.assertIsNone(_parse_da(''))


class QueryFilterTagResolutionTest(TestCase):

    def setUp(self):
        self.qf = QueryFilter(TAG_MAP_SERIES)

    def test_hex_tag_lookup(self):
        self.assertEqual(self.qf._resolve_tag('00100010'), '00100010')

    def test_keyword_lookup(self):
        # PatientName keyword → same hex as 00100010
        self.assertEqual(self.qf._resolve_tag('PatientName'), '00100010')

    def test_lowercase_hex_normalised(self):
        self.assertEqual(self.qf._resolve_tag('00100010'), '00100010')

    def test_unknown_returns_none(self):
        self.assertIsNone(self.qf._resolve_tag('99990001'))

    def test_unknown_keyword_returns_none(self):
        self.assertIsNone(self.qf._resolve_tag('NotARealTag'))


class QueryFilterApplyTest(TestCase):
    """
    These tests exercise the query filter logic against an in-memory queryset.
    They require a database (model instances) so they use TestCase.
    """

    def test_unsupported_tag_silently_ignored(self):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(TAG_MAP_SERIES)
        qs = PACSSeries.objects.none()
        result = qf.apply(qs, QueryDict('99990001=bogus'))
        # No exception; queryset unchanged
        self.assertEqual(list(result), [])

    def test_aggregation_tag_skipped(self):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(TAG_MAP_STUDY)
        qs = PACSSeries.objects.none()
        # ModalitiesInStudy (00080061) is an Aggregation — must not be applied as filter
        result = qf.apply(qs, QueryDict('00080061=CT'))
        self.assertEqual(list(result), [])

    def test_empty_value_skipped(self):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(TAG_MAP_SERIES)
        qs = PACSSeries.objects.none()
        result = qf.apply(qs, QueryDict('PatientName='))
        self.assertEqual(list(result), [])

    def test_fuzzymatching_ignored(self):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(TAG_MAP_SERIES)
        qs = PACSSeries.objects.none()
        # fuzzymatching is a reserved param — must not raise or apply as filter
        result = qf.apply(qs, QueryDict('fuzzymatching=true'))
        self.assertEqual(list(result), [])


class PaginateTest(TestCase):

    def setUp(self):
        self.qf = QueryFilter(TAG_MAP_SERIES)

    def test_limit_enforced(self):
        from pacsfiles.models import PACSSeries
        qs = PACSSeries.objects.none()
        _, _, limit = self.qf.paginate(qs, QueryDict('limit=9999'))
        self.assertLessEqual(limit, self.qf.HARD_LIMIT)

    def test_limit_default(self):
        from pacsfiles.models import PACSSeries
        qs = PACSSeries.objects.none()
        _, _, limit = self.qf.paginate(qs, QueryDict(''))
        self.assertEqual(limit, self.qf.DEFAULT_LIMIT)

    def test_invalid_limit_uses_default(self):
        from pacsfiles.models import PACSSeries
        qs = PACSSeries.objects.none()
        _, _, limit = self.qf.paginate(qs, QueryDict('limit=notanumber'))
        self.assertEqual(limit, self.qf.DEFAULT_LIMIT)
