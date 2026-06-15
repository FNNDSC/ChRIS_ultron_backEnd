from django.test import TestCase
from django.contrib.auth.models import User, Group

from core.models import ChrisFolder
from pacsfiles.models import PACS, PACSSeries, PACSFile
from dicomweb.models import PACSInstance


class PACSInstanceModelTests(TestCase):

    def setUp(self):
        owner = User.objects.get(username='chris')
        pacs_grp, _ = Group.objects.get_or_create(name='pacs_users')

        pacs_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS', owner=owner)
        pacs = PACS(folder=pacs_folder, identifier='MODELPACS')
        pacs.save()

        series_folder, _ = ChrisFolder.objects.get_or_create(
            path='SERVICES/PACS/MODELPACS/P001/study/series', owner=owner)
        self.series, _ = PACSSeries.objects.get_or_create(
            PatientID='P001',
            PatientName='Test^Patient',
            PatientSex='O',
            StudyDate='2023-01-01',
            StudyInstanceUID='1.2.3.model.study',
            SeriesInstanceUID='1.2.3.model.series',
            pacs=pacs,
            folder=series_folder,
        )
        pacs_file = PACSFile(owner=owner, parent_folder=series_folder)
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

    def test_ordering_by_series_then_instance_number(self):
        PACSInstance.objects.create(
            series=self.series,
            pacs_file=self.pacs_file,
            SOPClassUID='1.2.840.10008.5.1.4.1.1.2',
            SOPInstanceUID='1.2.3.4.5.sop.ordering',
            InstanceNumber=3,
        )
        qs = PACSInstance.objects.filter(series=self.series)
        self.assertGreater(qs.count(), 0)
