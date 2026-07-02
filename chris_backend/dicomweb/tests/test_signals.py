from django.test import TestCase
from django.contrib.auth.models import User, Group

from core.models import ChrisFolder
from pacsfiles.models import PACS, PACSSeries, PACSFile
from dicomweb.models import PACSStudy, PACSInstance


class StudyCounterSignalTests(TestCase):
    """
    The denormalized PACSStudy counters must always equal the actual number of
    related rows (the whole point of the denormalization is to avoid joins).
    """

    def setUp(self):
        self.owner = User.objects.get(username='chris')
        Group.objects.get_or_create(name='pacs_users')

        self.pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/SIGPACS', owner=self.owner)
        self.pacs = PACS.objects.create(folder=self.pacs_folder, identifier='SIGPACS')
        self.study = PACSStudy.objects.create(
            pacs=self.pacs, StudyInstanceUID='1.sig.study', PatientID='P1')

    def _refreshed_study(self):
        self.study.refresh_from_db()
        return self.study

    def _make_series(self, idx, study):
        folder = ChrisFolder.objects.create(
            path=f'{self.pacs_folder.path}/P1/study/series{idx}', owner=self.owner)
        return PACSSeries.objects.create(
            PatientID='P1', PatientName='Sig^Test', PatientSex='O',
            StudyDate='2026-01-01', StudyInstanceUID='1.sig.study',
            SeriesInstanceUID=f'1.sig.series{idx}', pacs=self.pacs,
            folder=folder, study=study)

    def _make_instance(self, series, j):
        pacs_file = PACSFile(owner=self.owner, parent_folder=series.folder)
        pacs_file.fname.name = f'{series.folder.path}/{j:03d}.dcm'
        pacs_file.save()
        return PACSInstance.objects.create(
            series=series, pacs_file=pacs_file, SOPClassUID='test.class',
            SOPInstanceUID=f'{series.SeriesInstanceUID}.{j}', InstanceNumber=j)

    # --- series counter ---------------------------------------------------

    def test_series_count_increments_on_create(self):
        self._make_series(0, self.study)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedSeries, 1)
        self._make_series(1, self.study)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedSeries, 2)

    def test_series_count_unchanged_without_study(self):
        self._make_series(0, None)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedSeries, 0)

    def test_series_count_decrements_on_delete(self):
        series = self._make_series(0, self.study)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedSeries, 1)
        series.delete()
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedSeries, 0)

    # --- instance counter -------------------------------------------------

    def test_instance_count_increments_on_create(self):
        series = self._make_series(0, self.study)
        self._make_instance(series, 0)
        self._make_instance(series, 1)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedInstances, 2)

    def test_instance_count_unchanged_when_series_has_no_study(self):
        series = self._make_series(0, None)
        self._make_instance(series, 0)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedInstances, 0)

    def test_instance_count_decrements_on_delete(self):
        series = self._make_series(0, self.study)
        instance = self._make_instance(series, 0)
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedInstances, 1)
        instance.delete()
        self.assertEqual(self._refreshed_study().NumberOfStudyRelatedInstances, 0)

    # --- cascade ----------------------------------------------------------

    def test_series_delete_cascades_to_both_counters(self):
        series = self._make_series(0, self.study)
        self._make_instance(series, 0)
        self._make_instance(series, 1)
        study = self._refreshed_study()
        self.assertEqual(study.NumberOfStudyRelatedSeries, 1)
        self.assertEqual(study.NumberOfStudyRelatedInstances, 2)

        # Deleting the series cascades to its instances; both counters drop so
        # the study still reflects the (now zero) related-row counts.
        series.delete()
        study = self._refreshed_study()
        self.assertEqual(study.NumberOfStudyRelatedSeries, 0)
        self.assertEqual(study.NumberOfStudyRelatedInstances, 0)
