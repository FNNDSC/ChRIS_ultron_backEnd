
import logging
import os
import time

from django.contrib.auth.models import Group
from django.conf import settings
from rest_framework import serializers

from core.models import ChrisFolder
from core.storage import connect_storage
from core.serializers import ChrisFileSerializer

from .models import PACS, PACSSeries, PACSFile


logger = logging.getLogger(__name__)


class PACSSerializer(serializers.HyperlinkedModelSerializer):
    folder_path = serializers.ReadOnlyField(source='folder.path')
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    pacs_series_list = serializers.HyperlinkedIdentityField(
        view_name='pacs-specific-series-list')

    class Meta:
        model = PACS
        fields = ('url', 'id', 'identifier', 'active', 'folder_path', 'folder',
                  'pacs_series_list')


class PACSSeriesSerializer(serializers.HyperlinkedModelSerializer):
    path = serializers.CharField(max_length=1024, write_only=True)
    folder_path = serializers.ReadOnlyField(source='folder.path')
    ndicom = serializers.IntegerField(write_only=True)
    pacs_name = serializers.CharField(max_length=20, write_only=True)
    pacs_identifier = serializers.ReadOnlyField(source='pacs.identifier')
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)

    class Meta:
        model = PACSSeries
        fields = ('url', 'id', 'creation_date', 'path', 'folder_path', 'ndicom',
                  'PatientID', 'PatientName', 'PatientBirthDate', 'PatientAge',
                  'PatientSex', 'StudyDate', 'AccessionNumber', 'Modality',
                  'ProtocolName', 'StudyInstanceUID', 'StudyDescription',
                  'SeriesInstanceUID', 'SeriesDescription', 'pacs_name',
                  'pacs_identifier', 'folder')

    def create(self, validated_data):
        """
        Overriden to create a PACS object and its folder if they don't already exist.
        Also to register pacs files and their parent folder in bulk.
        """
        owner = validated_data.pop('owner')
        pacs_name = validated_data.pop('pacs_name')
        (pacs_grp, _) = Group.objects.get_or_create(name='pacs_users')

        try:
            pacs = PACS.objects.get(identifier=pacs_name)
        except PACS.DoesNotExist:
            folder_path = f'SERVICES/PACS/{pacs_name}'
            (pacs_folder, tf) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                  owner=owner)
            if tf:
                pacs_folder.grant_group_permission(pacs_grp, 'r')

            pacs = PACS(folder=pacs_folder, identifier=pacs_name)
            pacs.save()  # create a PACS object

        SeriesInstanceUID = validated_data['SeriesInstanceUID']
        try:
            PACSSeries.objects.get(pacs=pacs, SeriesInstanceUID=SeriesInstanceUID)
        except PACSSeries.DoesNotExist:
            path = validated_data.pop('path')
            (series_folder, _) = ChrisFolder.objects.get_or_create(path=path, owner=owner)

            validated_data['pacs'] = pacs
            validated_data['folder'] = series_folder

            files_in_storage = validated_data.pop('files_in_storage')
            files = []
            for obj_name in files_in_storage:
                parent_folder = series_folder
                folder_path = os.path.dirname(obj_name)

                if folder_path != path:
                    (parent_folder, _) = ChrisFolder.objects.get_or_create(
                        path=folder_path, owner=owner)

                pacs_file = PACSFile(owner=owner, parent_folder=parent_folder)
                pacs_file.fname.name = obj_name
                files.append(pacs_file)

            PACSFile.objects.bulk_create(files)

            # grant group permission from the highest folder ancestor without it
            current = series_folder
            while not current.parent.has_group_permission(pacs_grp):
                current = current.parent
            current.grant_group_permission(pacs_grp, 'r')

        else:
            error_msg = (f'A DICOM series with SeriesInstanceUID={SeriesInstanceUID} '
                         f'already registered for pacs {pacs_name}')
            raise serializers.ValidationError([error_msg])

        return super(PACSSeriesSerializer, self).create(validated_data)

    def validate_path(self, path):
        """
        Overriden to check whether the provided path is under SERVICES/PACS/ path.
        """
        path = path.strip(' ').strip('/')
        if not path.startswith('SERVICES/PACS/'):
            raise serializers.ValidationError(
                ["This field must start with 'SERVICES/PACS/'."])
        return path

    def validate_ndicom(self, ndicom):
        """
        Overriden to check whether the provided ndicom value is a positive integer.
        """
        if ndicom < 1:
            raise serializers.ValidationError(
                [f'This field must be a postive integer. Got {ndicom}.'])
        return ndicom

    def validate(self, data):
        """
        Overriden to validate whether the provided path starts with
        'SERVICES/PACS/<pacs_name>' and whether all expected DICOM files are already
        in storage.
        """
        pacs_name = data.get('pacs_name')
        path = data.get('path')
        prefix = f'SERVICES/PACS/{pacs_name}/'

        if not path.startswith(prefix):
            error_msg = "The path field must start with '%s'." % prefix
            raise serializers.ValidationError([error_msg])

        # verify files are already in storage
        ndicom = data.pop('ndicom')
        nfiles = 0
        files_in_storage = []
        storage_manager = connect_storage(settings)

        for i in range(30):  # check for 30 seconds at 1-sec intervals
            try:
                files_in_storage = storage_manager.ls(path)
            except Exception as e:
                logger.error(f'[Error while listing storage files in {path}, '
                             f'detail: {str(e)}')
            else:
                nfiles = len([f for f in files_in_storage if f.endswith('.dcm')])

            if nfiles == ndicom:
                data['files_in_storage'] = files_in_storage
                break

            if nfiles > ndicom:
                error_msg = (f'The number of DICOM files found under {path}({nfiles})'
                             f' was different from the ndicom({ndicom}) field')
                raise serializers.ValidationError([error_msg])

            if i == 29:
                error_msg = (f'The number of DICOM files found under {path}({nfiles})'
                             f' was different from the ndicom({ndicom}) field')
                raise serializers.ValidationError([error_msg])
            time.sleep(1)
        return data


class PACSFileSerializer(ChrisFileSerializer):
    fname = serializers.FileField(use_url=False, required=True)

    class Meta:
        model = PACSFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'public',
                  'owner_username', 'file_resource', 'parent_folder', 'owner')
