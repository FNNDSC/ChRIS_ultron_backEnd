from django.test import TestCase
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User, Group

from core.models import ChrisFolder
from pacsfiles.models import PACS, PACSSeries, PACSFile
from dicomweb.models import PACSInstance, PACSStudy


class PACSInstanceModelTests(TestCase):

    def setUp(self):
        owner = User.objects.get(username='chris')
        pacs_grp, _ = Group.objects.get_or_create(name='pacs_users')

        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS', owner=owner)
        pacs = PACS(folder=pacs_folder, identifier='MODELPACS')
        pacs.save()

        self.series_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS/P001/study/series', owner=owner)
        self.series, _ = PACSSeries.objects.get_or_create(
            PatientID='P001',
            PatientName='Test^Patient',
            PatientSex='O',
            StudyDate='2023-01-01',
            StudyInstanceUID='1.2.3.model.study',
            SeriesInstanceUID='1.2.3.model.series',
            pacs=pacs,
            folder=self.series_folder,
        )
        pacs_file = PACSFile(owner=owner, parent_folder=self.series_folder)
        pacs_file.fname.name = 'SERVICES/PACS/MODELPACS/P001/study/series/0001.dcm'
        pacs_file.save()
        self.pacs_file = pacs_file

    def test_str_returns_sop_instance_uid(self):
        instance = PACSInstance(
            series=self.series,
            pacs_file=self.pacs_file,
            SOPClassUID='1.2.840.10008.5.1.4.1.1.2',
            SOPInstanceUID='1.2.3.4.5.sop',
        )
        self.assertEqual(str(instance), '1.2.3.4.5.sop')

    def test_ordering_by_instance_number(self):
        owner = User.objects.get(username='chris')

        # Create a second PACSFile for the second instance
        pacs_file2 = PACSFile(owner=owner, parent_folder=self.series_folder)
        pacs_file2.fname.name = 'SERVICES/PACS/MODELPACS/P001/study/series/0002.dcm'
        pacs_file2.save()

        PACSInstance.objects.create(
            series=self.series,
            pacs_file=self.pacs_file,
            SOPClassUID='1.2.840.10008.5.1.4.1.1.2',
            SOPInstanceUID='1.2.3.4.5.sop.b',
            InstanceNumber=5,
        )
        PACSInstance.objects.create(
            series=self.series,
            pacs_file=pacs_file2,
            SOPClassUID='1.2.840.10008.5.1.4.1.1.2',
            SOPInstanceUID='1.2.3.4.5.sop.a',
            InstanceNumber=2,
        )
        numbers = list(
            PACSInstance.objects.filter(series=self.series)
            .values_list('InstanceNumber', flat=True)
        )
        self.assertEqual(numbers, [2, 5])


class PACSStudyModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.get(username='chris')
        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS', owner=self.owner)
        self.pacs = PACS.objects.create(folder=pacs_folder, identifier='MODELPACS')

    def test_str_returns_study_instance_uid(self):
        self.assertEqual(str(PACSStudy(StudyInstanceUID='1.2.3.study')), '1.2.3.study')

    def test_default_ordering_by_patientid_then_studydate(self):
        """Meta.ordering returns studies sorted by PatientID, then StudyDate."""
        # Created out of order on purpose; expect (PatientID asc, StudyDate asc) back.
        p2 = PACSStudy.objects.create(
            pacs=self.pacs, StudyInstanceUID='u.p2',
            PatientID='P002', StudyDate='2025-05-05')
        p1_late = PACSStudy.objects.create(
            pacs=self.pacs, StudyInstanceUID='u.p1.late',
            PatientID='P001', StudyDate='2026-02-02')
        p1_early = PACSStudy.objects.create(
            pacs=self.pacs, StudyInstanceUID='u.p1.early',
            PatientID='P001', StudyDate='2025-01-01')

        self.assertEqual(
            list(PACSStudy.objects.filter(pacs=self.pacs)),
            [p1_early, p1_late, p2],
        )

    def test_unique_together_pacs_and_studyinstanceuid(self):
        """(pacs, StudyInstanceUID) is unique; the same UID under another PACS is OK."""
        PACSStudy.objects.create(pacs=self.pacs, StudyInstanceUID='dup.study')

        # A duplicate (pacs, StudyInstanceUID) is rejected by the DB constraint.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PACSStudy.objects.create(pacs=self.pacs, StudyInstanceUID='dup.study')

        # The constraint is the (pacs, StudyInstanceUID) pair, not StudyInstanceUID
        # alone, so a different PACS may hold the same StudyInstanceUID.
        pacs2_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS2', owner=self.owner)
        pacs2 = PACS.objects.create(folder=pacs2_folder, identifier='MODELPACS2')
        PACSStudy.objects.create(pacs=pacs2, StudyInstanceUID='dup.study')

        self.assertEqual(
            PACSStudy.objects.filter(StudyInstanceUID='dup.study').count(), 2)
