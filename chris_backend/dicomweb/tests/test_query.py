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

    def test_fuzzymatching_flag_alone_adds_no_filter(self):
        from pacsfiles.models import PACSSeries
        qf = QueryFilter(TAG_MAP_SERIES)
        qs = PACSSeries.objects.none()
        # fuzzymatching is a request-wide modifier, not a match key — on its own
        # (no PN attribute) it must not raise or apply any filter.
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


class FuzzyMatchingSqlShapeTest(TestCase):
    """
    Fuzzy Person-Name matching (PS3.18 §8.3.4.2) must compile to pg_trgm's ``%``
    similarity operator (Django ``__trigram_similar``), which is GIN-index-backed.

    Django renders that operator as the escaped literal ``%%`` in the compiled
    SQL (``TrigramSimilar.postgres_operator``), whereas the exact/wildcard paths
    (``=``, ``LIKE``, ``~*``) do not — so the presence of ``%%`` is a reliable
    discriminator for "used the trigram operator".
    """

    def setUp(self):
        self.qf = QueryFilter(TAG_MAP_SERIES)

    def _sql(self, querystring):
        from pacsfiles.models import PACSSeries
        qs = self.qf.apply(PACSSeries.objects.all(), QueryDict(querystring))
        sql, _params = qs.query.sql_with_params()
        return sql

    def test_fuzzy_pn_uses_trigram_operator(self):
        self.assertIn('%%', self._sql('PatientName=DOE&fuzzymatching=true'))

    def test_fuzzy_false_uses_exact_not_trigram(self):
        self.assertNotIn('%%', self._sql('PatientName=DOE&fuzzymatching=false'))

    def test_fuzzy_absent_uses_exact_not_trigram(self):
        self.assertNotIn('%%', self._sql('PatientName=DOE'))

    def test_fuzzy_true_variants_all_enable_trigram(self):
        for variant in ('true', '1', 'yes', 'TRUE', 'Yes'):
            with self.subTest(variant=variant):
                self.assertIn('%%',
                              self._sql(f'PatientName=DOE&fuzzymatching={variant}'))

    def test_fuzzy_gated_on_pn_only(self):
        # Modality (CS VR, fuzzy=False) must not use trigram even with the flag on.
        self.assertNotIn('%%', self._sql('Modality=CT&fuzzymatching=true'))

    def test_wildcard_takes_precedence_over_fuzzy(self):
        sql = self._sql('PatientName=DOE*&fuzzymatching=true')
        self.assertNotIn('%%', sql)   # not the trigram operator
        self.assertIn('~*', sql)       # the iregex wildcard path

    def test_multivalue_fuzzy_ors_each_value(self):
        sql = self._sql('PatientName=DOE,SMITH&fuzzymatching=true')
        self.assertEqual(sql.count('%%'), 2)


class FuzzyMatchingBehaviorTest(TestCase):
    """
    End-to-end fuzzy matching against the Postgres test DB, where migration
    ``0002_pg_trgm`` has created the ``pg_trgm`` extension + GIN indexes and the
    ``pg_trgm.similarity_threshold`` GUC is set per connection via DATABASES OPTIONS.
    """

    def setUp(self):
        from datetime import date
        from django.contrib.auth.models import User
        from core.models import ChrisFolder
        from pacsfiles.models import PACS, PACSSeries

        self.user = User.objects.get(username='chris')
        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/FUZZPACS', owner=self.user)
        self.pacs, _ = PACS.objects.get_or_create(
            folder=pacs_folder, identifier='FUZZPACS')

        def make_series(patient_name, series_uid):
            folder, _ = ChrisFolder.objects.get_or_create(
                path=f'SERVICES/PACS/FUZZPACS/{series_uid}', owner=self.user)
            return PACSSeries.objects.create(
                PatientID='P1', PatientName=patient_name, StudyDate=date(2023, 1, 1),
                StudyInstanceUID='1.2.3', SeriesInstanceUID=series_uid,
                folder=folder, pacs=self.pacs)

        make_series('DOE^JANE', '1.1')
        make_series('SMITH^JOHN', '1.2')
        self.qf = QueryFilter(TAG_MAP_SERIES)

    # Query 'JOE^JANE' is a one-character transposition of the stored 'DOE^JANE':
    # literal iexact/istartswith matching misses it, but trigram similarity catches
    # it — so it cleanly demonstrates what fuzzy adds over literal matching.
    def test_fuzzy_matches_near_miss_and_excludes_dissimilar(self):
        from pacsfiles.models import PACSSeries
        result = self.qf.apply(
            PACSSeries.objects.all(),
            QueryDict('PatientName=JOE^JANE&fuzzymatching=true'))
        names = set(result.values_list('PatientName', flat=True))
        self.assertIn('DOE^JANE', names)       # near-miss matches
        self.assertNotIn('SMITH^JOHN', names)  # dissimilar excluded

    def test_non_fuzzy_literal_does_not_match_near_miss(self):
        from pacsfiles.models import PACSSeries
        result = self.qf.apply(
            PACSSeries.objects.all(),
            QueryDict('PatientName=JOE^JANE'))  # no fuzzymatching → exact/startswith
        self.assertEqual(list(result.values_list('PatientName', flat=True)), [])


class ThresholdGucWiringTest(TestCase):
    """The DICOMWEB_FUZZY_THRESHOLD setting must reach the DB session as the
    pg_trgm.similarity_threshold GUC (wired via DATABASES OPTIONS)."""

    def test_similarity_threshold_guc_matches_setting(self):
        from django.conf import settings
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SHOW pg_trgm.similarity_threshold')
            value = cur.fetchone()[0]
        self.assertAlmostEqual(float(value), settings.DICOMWEB_FUZZY_THRESHOLD)


class GinTrigramIndexTest(TestCase):
    """Regression guard: migration 0002_pg_trgm must leave the 3 GIN trigram
    indexes on pacsfiles_pacsseries in place (they back both wildcard and fuzzy)."""

    def test_trgm_indexes_exist(self):
        from django.db import connection
        expected = {
            'pacsseries_patientname_trgm_idx',
            'pacsseries_patientid_trgm_idx',
            'pacsseries_studydescription_trgm_idx',
        }
        with connection.cursor() as cur:
            cur.execute(
                'SELECT indexname FROM pg_indexes WHERE tablename = %s',
                ['pacsfiles_pacsseries'])
            names = {row[0] for row in cur.fetchall()}
        self.assertTrue(expected.issubset(names),
                        f'missing GIN trigram indexes: {expected - names}')
