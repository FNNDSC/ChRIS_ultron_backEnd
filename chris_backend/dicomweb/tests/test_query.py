"""
Unit tests for ``dicomweb.query`` — the QIDO-RS DICOM-tag query parser
(PS3.18 §10.6 Search Transaction; matching semantics per PS3.4 §C.2.2.2).
"""
from datetime import date, time, datetime
import unittest

from django.http import QueryDict
from django.test import TestCase, SimpleTestCase

from dicomweb.query import (
    SearchQuery, QueryFilter, Attribute, RangeValue, Tag,
    _parse_da, _parse_tm, _parse_dt, _parse_temporal, _wildcard_to_regex,
)


# ===========================================================================
# SearchQuery
# ===========================================================================
class ParseBoolTest(SimpleTestCase):

    def test_truthy_values(self):
        for v in ('true', '1', 'yes', 'TRUE', 'True', 'Yes', 'YES'):
            with self.subTest(v=v):
                self.assertTrue(SearchQuery._parse_bool(v))

    def test_falsy_values(self):
        for v in ('false', '0', 'no', 'FALSE', 'False', 'No', 'NO', '', 'nope'):
            with self.subTest(v=v):
                self.assertFalse(SearchQuery._parse_bool(v))


class FromQueryDictTest(SimpleTestCase):

    def test_keyword_and_hex_resolve_to_same_tag(self):
        kw = SearchQuery.from_query_dict(QueryDict('PatientName=DOE'))
        hexq = SearchQuery.from_query_dict(QueryDict('00100010=DOE'))
        self.assertIn(Tag('PatientName'), kw.match)
        self.assertIn(Tag('PatientName'), hexq.match)
        self.assertEqual(kw.match[Tag('PatientName')], ['DOE'])

    def test_repeated_param_collected_as_list(self):
        sq = SearchQuery.from_query_dict(QueryDict('Modality=CT&Modality=MR'))
        self.assertEqual(sq.match[Tag('Modality')], ['CT', 'MR'])

    def test_reserved_params_excluded_from_match(self):
        sq = SearchQuery.from_query_dict(
            QueryDict('PatientName=DOE&limit=5&offset=2&fuzzymatching=true'))
        self.assertEqual(list(sq.match), [Tag('PatientName')])

    def test_includefield_all(self):
        sq = SearchQuery.from_query_dict(QueryDict('includefield=all'))
        self.assertEqual(sq.includefield, 'all')

    def test_includefield_list_repeated_form(self):
        # Repeated-parameter form collects each resolved tag, in order.
        sq = SearchQuery.from_query_dict(
            QueryDict('includefield=Modality&includefield=00080061'))
        self.assertEqual(sq.includefield,
                         [Tag('Modality'), Tag('00080061')])

    def test_includefield_absent_is_none(self):
        search_query = SearchQuery.from_query_dict(QueryDict(''))
        self.assertIsNone(search_query.includefield)

    def test_limit_and_offset_parsed_as_int(self):
        sq = SearchQuery.from_query_dict(QueryDict('limit=25&offset=10'))
        self.assertEqual((sq.limit, sq.offset), (25, 10))

    def test_limit_offset_absent_are_none(self):
        sq = SearchQuery.from_query_dict(QueryDict(''))
        self.assertEqual((sq.limit, sq.offset), (None, None))

    def test_bool_flags_parsed(self):
        sq = SearchQuery.from_query_dict(QueryDict(
            'fuzzymatching=true'
            '&emptyvaluematching=1'
            '&multiplevaluematching=yes'))
        self.assertTrue(sq.fuzzymatching)
        self.assertTrue(sq.emptyvaluematching)
        self.assertTrue(sq.multiplevaluematching)

    def test_bool_flags_default_false(self):
        sq = SearchQuery.from_query_dict(QueryDict(''))
        self.assertFalse(sq.fuzzymatching)
        self.assertFalse(sq.emptyvaluematching)
        self.assertFalse(sq.multiplevaluematching)

    def test_unknown_hex_tag_is_kept_verbatim(self):
        # A syntactically-valid but unsupported tag survives parsing (it is
        # dropped later, in QueryFilter.apply).
        sq = SearchQuery.from_query_dict(QueryDict('99990001=x'))
        self.assertIn(Tag('99990001'), sq.match)

    def test_unknown_keyword_dropped(self):
        # An unresolvable keyword is caught (ValueError/OverflowError) and
        # silently dropped from the match set.
        sq = SearchQuery.from_query_dict(QueryDict('NotARealTag=x'))
        self.assertEqual(list(sq.match), [])

    def test_comma_joined_includefield(self):
        sq = SearchQuery.from_query_dict(QueryDict('includefield=00080060,Modality'))
        self.assertEqual(sq.includefield, [Tag('00080060'), Tag('Modality')])

    def test_include_unknown_field(self):
        # Unkown fields are silently dropped in both csv and
        # single-value forms
        sq = SearchQuery.from_query_dict(QueryDict('includefield=XxNoSuchFieldxX,Modality'))
        self.assertEqual(sq.includefield, [Tag('Modality')])
        sq = SearchQuery.from_query_dict(QueryDict('includefield=XxNoSuchFieldxX'))
        self.assertEqual(sq.includefield, [])

    def test_non_integer_limit_raises(self):
        with self.assertRaises(ValueError):
            SearchQuery.from_query_dict(QueryDict('limit=notanumber'))

    def test_non_integer_offset_raises(self):
        with self.assertRaises(ValueError):
            SearchQuery.from_query_dict(QueryDict('offset=notanumber'))


# ===========================================================================
# Attribute descriptor
# ===========================================================================
class AttributeTest(SimpleTestCase):

    def test_orm_field_defaults_to_keyword(self):
        self.assertEqual(Attribute('PatientName').orm_field, 'PatientName')

    def test_orm_field_explicit_is_preserved(self):
        a = Attribute('SeriesInstanceUID', orm_field='series__SeriesInstanceUID')
        self.assertEqual(a.orm_field, 'series__SeriesInstanceUID')

    def test_tag_and_vr_resolved(self):
        a = Attribute('PatientName')
        self.assertEqual(a.tag, Tag(0x00100010))
        self.assertEqual(a.vr, 'PN')

    def test_cap_wildcard(self):
        self.assertTrue(Attribute('Wildcard', tag='wc', vr='PN', vm='1').cap_wildcard())
        self.assertFalse(Attribute('NoWildcard', tag='wc', vr='UI', vm='1').cap_wildcard())
        self.assertTrue(Attribute('PatientName').cap_wildcard())   # PN
        self.assertTrue(Attribute('Modality').cap_wildcard())      # CS
        self.assertFalse(Attribute('StudyInstanceUID').cap_wildcard())  # UI

    def test_cap_range(self):
        self.assertTrue(Attribute('StudyDate').cap_range())        # DA
        self.assertTrue(Attribute('StudyTime').cap_range())        # TM
        self.assertFalse(Attribute('PatientName').cap_range())     # PN

    def test_cap_multi_value_honors_vr_and_vm(self):
        # Multi-capable only when the VR is a multi-value VR AND VM != 1.
        self.assertTrue(
            Attribute('MultiVr', tag='multi', vr='AE', vm='1-n').cap_multi_value())
        self.assertFalse(
            Attribute('SingleVm', tag='single', vr='AE', vm='1').cap_multi_value())   # VM=1
        self.assertFalse(
            Attribute('NonMultiVr', tag='nm', vr='UI', vm='1-n').cap_multi_value())    # VR not multi

    # -- parse dispatch ----------------------------------------------------- #
    def test_parse_single_non_temporal_returns_raw(self):
        self.assertEqual(Attribute('PatientName').parse_single('DOE'), 'DOE')

    def test_parse_single_temporal_coerces(self):
        self.assertEqual(Attribute('StudyDate').parse_single('20230101'),
                         date(2023, 1, 1))
        self.assertEqual(Attribute('StudyTime').parse_single('120000'),
                         time(12, 0, 0))

    def test_parse_range_returns_rangevalue(self):
        rv = Attribute('StudyDate').parse_range('20230101-20231231')
        self.assertEqual(rv, RangeValue(date(2023, 1, 1), date(2023, 12, 31)))

    def test_parse_range_without_dash_raises(self):
        with self.assertRaises(ValueError):
            Attribute('StudyDate').parse_range('20230101')

    def test_parse_range_open_ended(self):
        open_start = Attribute('StudyDate').parse_range('-20260713')
        open_end =  Attribute('StudyDate').parse_range('20260713-')
        self.assertEqual(open_start, RangeValue(None, date(2026,7,13)))
        self.assertEqual(open_end, RangeValue(date(2026,7,13), None))

    def test_parse_range_no_values_raises(self):
        with self.assertRaises(ValueError):
            Attribute('StudyDate').parse_range('-')

    def test_parse_multiple_splits_on_comma_and_backslash(self):
        self.assertEqual(Attribute('Modality').parse_multiple('CT,MR').values,
                         ['CT', 'MR'])
        self.assertEqual(Attribute('Modality').parse_multiple('CT\\MR').values,
                         ['CT', 'MR'])

    def test_parse_dispatch_range(self):
        self.assertEqual(Attribute('StudyDate').parse('20230101-20231231'),
                         RangeValue(date(2023, 1, 1), date(2023, 12, 31)))

    def test_parse_dispatch_multiple_multi(self):
        # ModalitiesInStudy (CS, VM 1-n) is genuinely multi-valued; Modality is
        # VM=1 and would not take the multi path.
        result = Attribute('ModalitiesInStudy').parse('CT,MR', multi_value=True)
        self.assertEqual(result.values, ['CT', 'MR'])

    def test_parse_dispatch_multiple_single_element_unwrapped(self):
        # A single value with multiplevaluematching returns the scalar, not a
        # MultipleValue wrapper (needs a VM>1 attribute so the multi path runs).
        self.assertEqual(
            Attribute('ModalitiesInStudy').parse('CT', multi_value=True), 'CT')

    def test_parse_dispatch_single(self):
        self.assertEqual(Attribute('PatientName').parse('DOE'), 'DOE')


# ===========================================================================
# QueryFilter — construction
# ===========================================================================
class QueryFilterInitTest(SimpleTestCase):

    def test_map_keyed_by_tag(self):
        self.assertIn(Tag('SeriesNumber'), QueryFilter('series').tag_map)

    def test_unknown_resource_type_raises(self):
        with self.assertRaises(ValueError):
            QueryFilter('bogus')


# ===========================================================================
# QueryFilter.apply — compiled-SQL shape (no rows needed)
# ===========================================================================
class ApplySqlShapeTest(TestCase):

    def _sql(self, resource, querystring):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(resource)
        sq = SearchQuery.from_query_dict(QueryDict(querystring))
        qs = qf.apply(PACSSeries.objects.all(), sq)
        return qs.query.sql_with_params()[0]

    def _has_where(self, resource, querystring):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(resource)
        sq = SearchQuery.from_query_dict(QueryDict(querystring))
        qs = qf.apply(PACSSeries.objects.all(), sq)
        return 'WHERE' in str(qs.query)

    def test_exact_match_uses_equality(self):
        sql = self._sql('series', 'Modality=CT')
        self.assertIn('"Modality" = ', sql)

    def test_unsupported_tag_produces_no_filter(self):
        # Valid-but-unsupported tag (9999,0001) is silently dropped.
        self.assertFalse(self._has_where('series', '99990001=x'))

    def test_fuzzy_pn_uses_trigram_operator(self):
        # pg_trgm '%' operator renders as escaped '%%' in compiled SQL.
        self.assertIn('%%', self._sql('series', 'PatientName=DOE&fuzzymatching=true'))

    def test_fuzzy_not_applied_without_flag(self):
        self.assertNotIn('%%', self._sql('series', 'PatientName=DOE'))

    def test_fuzzy_gated_on_fuzzy_eligible_attribute(self):
        # Modality (fuzzy=False) must not use the trigram operator even with the flag.
        self.assertNotIn('%%', self._sql('series', 'Modality=CT&fuzzymatching=true'))

    def test_wildcard_precedence_over_fuzzy(self):
        # Documented: with fuzzymatching on, a PN value is sent through the fuzzy
        # branch even when it contains a wildcard char (fuzzy is checked first).
        self.assertNotIn('%%', self._sql('series', 'PatientName=DOE*&fuzzymatching=true'))

    def test_range_emits_gte_and_lte(self):
        sql = self._sql('study', 'StudyDate=20230101-20231231')
        self.assertIn('>=', sql)
        self.assertIn('<=', sql)

    def test_multiple_value_emits_in(self):
        # The multiplevaluematching-gated multi path (VR in MULTI_VALUE_VRS with
        # VM>1) has no such field in the resource maps, so drive it with a
        # synthetic ModalitiesInStudy (CS VM 1-n) mapped onto a real column. The
        # ungated UID-list IN path is covered separately by the real-map tests.
        from dicomweb.models import PACSStudy
        qf = QueryFilter('study')

        # TODO: remove monkeypatch after ModalitiesInStudy implemented
        attr = Attribute('ModalitiesInStudy', orm_field='PatientName')
        qf.tag_map = {attr.tag: attr}

        sq = SearchQuery.from_query_dict(
            QueryDict('ModalitiesInStudy=CT,MR&multiplevaluematching=true'))
        sql, params = qf.apply(PACSStudy.objects.all(), sq).query.sql_with_params()
        self.assertIn(' AND ', sql)
        self.assertIn(' LIKE ', sql)
        self.assertIn('%CT%', params)
        self.assertIn('%MR%', params)

    def test_quoted_empty_skipped_without_flag(self):
        self.assertFalse(self._has_where('series', 'PatientName=""'))

    def test_quoted_empty_matched_with_flag(self):
        sql = self._sql('series', 'PatientName=""&emptyvaluematching=true')
        self.assertIn('"PatientName" IS NULL', sql)

    def test_distinct_attributes_are_anded(self):
        sql = self._sql('series', 'PatientName=DOE&Modality=CT')
        self.assertIn(' AND ', sql)

    def test_instance_resource_passthrough_orm_field(self):
        # The instance map routes SeriesInstanceUID through the series__ FK path,
        # so it filters via a JOIN to the series table.
        from dicomweb.models import PACSInstance
        qf = QueryFilter('instance')
        sq = SearchQuery.from_query_dict(QueryDict('SeriesInstanceUID=1.2.3'))
        sql = qf.apply(PACSInstance.objects.all(), sq).query.sql_with_params()[0]
        self.assertIn('pacsfiles_pacsseries', sql)          # joined series table
        self.assertIn('"SeriesInstanceUID" = ', sql)

    def test_instance_empty_value_follows_fk_relation(self):
        # Empty-value matching on the instance map's series__ pass-through field
        # must follow the FK relation to resolve the target column type. This is
        # the only path that reaches the relation-following branch of
        # _is_text_column; SeriesInstanceUID is text, so the compiled filter is
        # the NULL-or-empty pair (`IS NULL` OR `= ''`).
        from dicomweb.models import PACSInstance
        qf = QueryFilter('instance')
        sq = SearchQuery.from_query_dict(
            QueryDict('SeriesInstanceUID=""&emptyvaluematching=true'))
        sql, params = qf.apply(PACSInstance.objects.all(), sq).query.sql_with_params()
        self.assertIn('"SeriesInstanceUID" IS NULL', sql)
        self.assertIn(' OR ', sql)          # text column → empty-string alternative
        self.assertIn('"SeriesInstanceUID" = ', sql)
        self.assertIn('', params)

    def test_uid_list_emits_in(self):
        self.assertIn('IN (', self._sql('study', 'StudyInstanceUID=1.2.3,4.5.6'))

    def test_uid_list_emits_in_on_instance_passthrough(self):
        # Same ungated UID-list path through the instance map's
        # series__StudyInstanceUID FK pass-through field.
        from dicomweb.models import PACSInstance
        qf = QueryFilter('instance')
        sq = SearchQuery.from_query_dict(QueryDict('StudyInstanceUID=1.2.3,4.5.6'))
        sql = qf.apply(PACSInstance.objects.all(), sq).query.sql_with_params()[0]
        self.assertIn('IN (', sql)

    def test_temporal_empty_is_universal_matching(self):
        # PS3.4 §C.2.2.2.3: a zero-length value is universal matching (no
        # restriction) — including temporal VRs, whose empty value yields a
        # UniversalValue sentinel and must not emit `StudyDate IS NULL`.
        self.assertFalse(self._has_where('study', 'StudyDate='))


# ===========================================================================
# QueryFilter.apply — behavior against real rows
# ===========================================================================
class ApplyBehaviorTest(TestCase):

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import ChrisFolder
        from pacsfiles.models import PACS
        self.user = User.objects.get(username='chris')
        folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/QTEST', owner=self.user)
        self.pacs, _ = PACS.objects.get_or_create(folder=folder, identifier='QTEST')
        self._n = 0
        self.qf = QueryFilter('series')

    def _series(self, **overrides):
        from core.models import ChrisFolder
        from pacsfiles.models import PACSSeries
        self._n += 1
        uid = f'1.2.{self._n}'
        folder, _ = ChrisFolder.objects.get_or_create(
            path=f'SERVICES/PACS/QTEST/{uid}', owner=self.user)
        fields = dict(PatientID='P', PatientName='X^Y', StudyDate=date(2023, 1, 1),
                      StudyInstanceUID='1.2', SeriesInstanceUID=uid,
                      folder=folder, pacs=self.pacs)
        fields.update(overrides)
        return PACSSeries.objects.create(**fields)

    def _study(self, **overrides):
        from dicomweb.models import PACSStudy
        fields = dict(PatientID='P', PatientName='X^Y', StudyDate=date(2023, 1, 1),
                      StudyInstanceUID='1.2', pacs=self.pacs)
        fields.update(overrides)
        return PACSStudy.objects.create(**fields)

    def _names(self, querystring, resource='series'):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(resource)
        sq = SearchQuery.from_query_dict(QueryDict(querystring))
        return set(qf.apply(PACSSeries.objects.all(), sq)
                   .values_list('PatientName', flat=True))

    def test_exact_match(self):
        self._series(PatientName='DOE^JANE', Modality='CT')
        self._series(PatientName='SMITH^JOHN', Modality='MR')
        self.assertEqual(self._names('Modality=CT'), {'DOE^JANE'})

    def test_pn_match_case(self):
        self._series(PatientName='DOE^JANE')
        self._series(PatientName='SMITH^JOHN')
        self.assertEqual(self._names('PatientName=Doe^Jane'), {'DOE^JANE'})

    @unittest.expectedFailure   # ModalitiesInStudy missing
    def test_multiple_value_matching(self):
        # multiple value matching asserts that all values of a
        # comma-separated list appear in the matched object. We can
        # test this by querying multiple values on ModalitiesInStudy.
        # We should only get back studies that series with all modalities
        from dicomweb.models import PACSStudy
        self._study(PatientName='A', StudyInstanceUID='A.1', ModalitiesInStudy=r'CT\MR')
        self._study(PatientName='A', StudyInstanceUID='A.2', ModalitiesInStudy=r'CT')
        self._study(PatientName='A', StudyInstanceUID='A.3', ModalitiesInStudy=r'PT')
        self._study(PatientName='B', StudyInstanceUID='B.3', ModalitiesInStudy=r'CT')
        self._study(PatientName='B', StudyInstanceUID='B.3', ModalitiesInStudy=r'MR')
        qf = QueryFilter('study')
        sq = SearchQuery.from_query_dict(
            QueryDict('ModalitiesInStudy=CT,MR&multiplevaluematching=true'))
        study_instance_uids = set(qf.apply(PACSStudy.objects.all(), sq)
                                  .values_list('StudyInstanceUID', flat=True))
        self.assertEqual(study_instance_uids, {'A.1'})

    def test_multiple_value_matching_monkeypatch(self):
        # Workaround to exercise the currently-inaccessible
        # multi-value matching path.
        # TODO: remove this once the above expected failure is passing
        from pacsfiles.models import PACSSeries
        self._series(PatientName='A', StudyInstanceUID='A.1', Modality=r'CT\MR')
        self._series(PatientName='B', StudyInstanceUID='B.1', Modality=r'US')
        attr = Attribute('ModalitiesInStudy', orm_field='Modality')
        qf = QueryFilter('series')
        qf.tag_map = {attr.tag: attr}
        sq = SearchQuery.from_query_dict(
            QueryDict('ModalitiesInStudy=CT,MR&multiplevaluematching=true'))
        names = set(qf.apply(PACSSeries.objects.all(), sq)
                    .values_list('PatientName', flat=True))
        self.assertEqual(names, {'A'})

    def test_uid_list_matches_multiple_rows(self):
        # StudyInstanceUID=<uid>,<uid> (UI VR, ungated IN path via UID_LIST_VRS)
        # matches every listed study
        self._series(PatientName='A', StudyInstanceUID='1')
        self._series(PatientName='B', StudyInstanceUID='2')
        self._series(PatientName='C', StudyInstanceUID='3')
        self.assertEqual(self._names('StudyInstanceUID=1,2', 'study'),
                         {'A', 'B'})

    def test_date_range_matching(self):
        self._series(PatientName='IN', StudyDate=date(2023, 6, 1))
        self._series(PatientName='OUT', StudyDate=date(2024, 1, 1))
        self.assertEqual(self._names('StudyDate=20230101-20231231', 'study'), {'IN'})

    def test_single_value_exact_date(self):
        self._series(PatientName='HIT', StudyDate=date(2023, 1, 1))
        self._series(PatientName='MISS', StudyDate=date(2024, 6, 15))
        self.assertEqual(self._names('StudyDate=20230101', 'study'), {'HIT'})

    def test_time_range_matching(self):
        self._series(PatientName='LOW', StudyTime=time(11, 0))
        self._series(PatientName='MID', StudyTime=time(12, 30))
        self._series(PatientName='HIGH', StudyTime=time(14, 0))
        self.assertEqual(self._names('StudyTime=120000-130000', 'study'), {'MID'})

    def test_fuzzy_matches_near_miss_and_excludes_dissimilar(self):
        # 'JOE^JANE' is a one-char transposition of stored 'DOE^JANE': literal
        # matching misses it, trigram similarity catches it.
        self._series(PatientName='DOE^JANE')
        self._series(PatientName='SMITH^JOHN')
        names = self._names('PatientName=JOE^JANE&fuzzymatching=true')
        self.assertIn('DOE^JANE', names)
        self.assertNotIn('SMITH^JOHN', names)

    def test_non_fuzzy_literal_misses_near_miss(self):
        self._series(PatientName='DOE^JANE')
        self.assertEqual(self._names('PatientName=JOE^JANE'), set())

    def test_wildcard_prefix_matching(self):
        self._series(PatientName='DOE^JANE')
        self._series(PatientName='MCDOE^JOHN')
        names = self._names('PatientName=DOE*')
        self.assertIn('DOE^JANE', names)
        self.assertNotIn('MCDOE^JOHN', names)

    def test_bare_equals_universal_matching(self):
        from pacsfiles.models import PACSSeries
        self._series(PatientName='DOE^JANE')
        self._series(PatientName='JOHN^SMITH')
        all_names = sorted(
            PACSSeries.objects.all()
            .values_list('PatientName', flat=True)
        )
        returned_names = sorted(self._names('PatientName='))
        self.assertEqual(returned_names, all_names)

    def test_empty_value_matching(self):
        self._series(Modality='', StudyTime=None, PatientName='EMPTY')
        self._series(Modality='CT', StudyTime=time(12,0,0), PatientName='NOT^EMPTY')
        self.assertEqual(self._names('Modality=""&emptyvaluematching=true&PatientName=NOT^EMPTY'), set())
        self.assertEqual(self._names('Modality=""&emptyvaluematching=false&PatientName=NOT^EMPTY'), {'NOT^EMPTY'})
        self.assertEqual(self._names('Modality=""&emptyvaluematching=true'), {'EMPTY'})
        self.assertEqual(self._names('Modality=""&emptyvaluematching=false'), {'NOT^EMPTY', 'EMPTY'})
        self.assertEqual(self._names('Modality=""'), {'NOT^EMPTY', 'EMPTY'})

        # Check nullable column
        self.assertEqual(self._names('StudyTime=""&emptyvaluematching=false', 'study'), {'NOT^EMPTY', 'EMPTY'})
        self.assertEqual(self._names('StudyTime=""&emptyvaluematching=true', 'study'), {'EMPTY'})


# ===========================================================================
# QueryFilter.paginate
# ===========================================================================
class PaginateTest(TestCase):

    def setUp(self):
        self.qf = QueryFilter('series')

    def _paginate(self, querystring):
        from pacsfiles.models import PACSSeries
        sq = SearchQuery.from_query_dict(QueryDict(querystring))
        return self.qf.paginate(PACSSeries.objects.none(), sq)

    def test_default_limit(self):
        _, _, limit = self._paginate('')
        self.assertEqual(limit, self.qf.DEFAULT_LIMIT)

    def test_limit_clipped_to_hard_limit(self):
        _, _, limit = self._paginate('limit=9999')
        self.assertEqual(limit, self.qf.HARD_LIMIT)

    def test_explicit_limit_within_bounds(self):
        _, _, limit = self._paginate('limit=10')
        self.assertEqual(limit, 10)

    def test_negative_limit_clipped_to_zero(self):
        page, _, limit = self._paginate('limit=-5')
        self.assertEqual(limit, 0)
        self.assertEqual(list(page), [])  # negative slice must not raise

    def test_zero_limit(self):
        _, _, limit = self._paginate('limit=0')
        self.assertEqual(limit, 0)

    def test_negative_offset_clipped_to_zero(self):
        # Offset is floored at 0; the query must still build and slice cleanly.
        page, _, _ = self._paginate('offset=-3&limit=5')
        self.assertEqual(list(page), [])

    def test_total_count_returned(self):
        from pacsfiles.models import PACSSeries
        sq = SearchQuery.from_query_dict(QueryDict('limit=5'))
        _, total, _ = self.qf.paginate(PACSSeries.objects.all(), sq)
        self.assertEqual(total, 0)

    def _make_series(self, n):
        from django.contrib.auth.models import User
        from core.models import ChrisFolder
        from pacsfiles.models import PACS, PACSSeries
        user = User.objects.get(username='chris')
        pfolder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/PGT', owner=user)
        pacs, _ = PACS.objects.get_or_create(folder=pfolder, identifier='PGT')
        for i in range(n):
            f, _ = ChrisFolder.objects.get_or_create(
                path=f'SERVICES/PACS/PGT/1.{i}', owner=user)
            PACSSeries.objects.create(
                PatientID='P', PatientName=f'N{i}', StudyDate=date(2023, 1, 1),
                StudyInstanceUID='1', SeriesInstanceUID=f'1.{i}',
                folder=f, pacs=pacs)

    def test_offset_and_limit_slice(self):
        from pacsfiles.models import PACSSeries
        self._make_series(5)
        sq = SearchQuery.from_query_dict(QueryDict('limit=2&offset=1'))
        page, total, limit = self.qf.paginate(
            PACSSeries.objects.all().order_by('SeriesInstanceUID'), sq)
        self.assertEqual(total, 5)
        self.assertEqual(limit, 2)
        self.assertEqual([item.SeriesInstanceUID for item in page], ['1.1', '1.2'])



# ===========================================================================
# Temporal parsing helpers
# ===========================================================================
class ParseDaTest(SimpleTestCase):

    def test_valid(self):
        self.assertEqual(_parse_da('20230102'), date(2023, 1, 2))

    def test_truncates_trailing(self):
        self.assertEqual(_parse_da('20230102120000'), date(2023, 1, 2))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            _parse_da('not-a-date')

class ParseTmTest(SimpleTestCase):

    def test_full_hhmmss(self):
        self.assertEqual(_parse_tm('120000'), time(12, 0, 0))

    def test_hhmm(self):
        self.assertEqual(_parse_tm('1230'), time(12, 30))

    def test_hh(self):
        self.assertEqual(_parse_tm('12'), time(12))

    def test_fractional_seconds_stripped(self):
        self.assertEqual(_parse_tm('120000.500000'), time(12, 0, 0))

    def test_unsupported_length_raises(self):
        with self.assertRaises(ValueError):
            _parse_tm('123')

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            _parse_tm('9999')

class ParseDtTest(SimpleTestCase):

    def test_full(self):
        self.assertEqual(_parse_dt('20230101120000'), datetime(2023, 1, 1, 12, 0, 0))

    def test_truncated_to_hour(self):
        # 10-char HH form: must not be mis-parsed by a shorter/longer format.
        self.assertEqual(_parse_dt('2023010112'), datetime(2023, 1, 1, 12))

    def test_truncated_to_minute(self):
        # 12-char HHMM form.
        self.assertEqual(_parse_dt('202301011230'), datetime(2023, 1, 1, 12, 30))

    def test_date_only(self):
        self.assertEqual(_parse_dt('20230101'), datetime(2023, 1, 1))

    def test_fractional_stripped(self):
        self.assertEqual(_parse_dt('20230101120000.5'), datetime(2023, 1, 1, 12, 0, 0))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            _parse_dt('garbage')


class ParseTemporalTest(SimpleTestCase):

    def test_da(self):
        self.assertEqual(_parse_temporal('DA', '20230101'), date(2023, 1, 1))

    def test_tm(self):
        self.assertEqual(_parse_temporal('TM', '120000'), time(12, 0, 0))

    def test_dt(self):
        self.assertEqual(_parse_temporal('DT', '20230101'), datetime(2023, 1, 1))

    def test_other_vr_raises(self):
        with self.assertRaises(TypeError):
            _parse_temporal('PN', 'DOE^JANE')


# ===========================================================================
# _wildcard_to_regex
# ===========================================================================
class WildcardToRegexTest(SimpleTestCase):

    def test_plain_value_is_anchored(self):
        self.assertEqual(_wildcard_to_regex('plain'), '^plain$')

    def test_star_becomes_dotstar(self):
        self.assertEqual(_wildcard_to_regex('DOE*'), '^DOE.*$')

    def test_leading_star(self):
        self.assertEqual(_wildcard_to_regex('*ANNE'), '^.*ANNE$')

    def test_question_becomes_dot(self):
        self.assertEqual(_wildcard_to_regex('A?C'), '^A.C$')

    def test_multiple_wildcards(self):
        self.assertEqual(_wildcard_to_regex('A?C?E*'), '^A.C.E.*$')
