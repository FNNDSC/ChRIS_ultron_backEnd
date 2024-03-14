
import logging
import os

from django.conf import settings
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.models import ChrisFolder
from core.utils import get_file_resource_link
from core.storage import connect_storage

from .models import PACS, PACSFile


logger = logging.getLogger(__name__)


class PACSSerializer(serializers.HyperlinkedModelSerializer):
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)

    class Meta:
        model = PACS
        fields = ('url', 'id', 'identifier', 'folder')


class PACSFileSerializer(serializers.HyperlinkedModelSerializer):
    file_resource = ItemLinkField('get_file_link')
    path = serializers.CharField(write_only=True)
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    pacs_name = serializers.CharField(max_length=20, write_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = PACSFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'path', 'PatientID',
                  'PatientName', 'PatientBirthDate', 'PatientAge', 'PatientSex',
                  'StudyDate', 'AccessionNumber', 'Modality', 'ProtocolName',
                  'StudyInstanceUID', 'StudyDescription', 'SeriesInstanceUID',
                  'SeriesDescription', 'pacs_name', 'owner_username', 'file_resource',
                  'parent_folder', 'owner')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def create(self, validated_data):
        """
        Overriden to associate a storage path with the newly created pacs file and
        create a PACS object and parent folder if they don't already exist.
        """
        owner = validated_data['owner']

        # remove pacs_name as it is not part of the model
        pacs_name = validated_data.pop('pacs_name')
        try:
            PACS.objects.get(identifier=pacs_name)
        except PACS.DoesNotExist:
            folder_path = f'SERVICES/PACS/{pacs_name}'
            (pacs_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                 owner=owner)
            pacs = PACS(folder=pacs_folder, identifier=pacs_name)
            pacs.save()  # create a PACS object

        # remove path as it is not part of the model and then compute fname
        path = validated_data.pop('path')
        validated_data['fname'] = path

        folder_path = os.path.dirname(path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=owner)
        validated_data['parent_folder'] = file_parent_folder
        return super(PACSFileSerializer, self).create(validated_data)


    def validate_path(self, path):
        """
        Overriden to check whether the provided path is under SERVICES/PACS/ path.
        """
        path = path.strip(' ').strip('/')
        if not path.startswith('SERVICES/PACS/'):
            raise serializers.ValidationError(
                ["File path must start with 'SERVICES/PACS/'."])

        # verify that the file is indeed already in storage
        storage_manager = connect_storage(settings)
        try:
            storage_path_exists = storage_manager.obj_exists(path)
        except Exception as e:
            logger.error('Storage error, detail: %s' % str(e))
            raise serializers.ValidationError(["Could not find this path."])
        if not storage_path_exists:
            raise serializers.ValidationError(["Could not find this path."])
        return path

    def validate(self, data):
        """
        Overriden to validate whether the provided path starts with
        'SERVICES/PACS/<pacs_name>' and whether the pacs file has already been registered.
        """
        pacs_name = data.get('pacs_name')
        path = data.get('path')
        prefix = 'SERVICES/PACS/%s/' % pacs_name

        if not path.startswith(prefix):
            error_msg = "File path must start with '%s'." % prefix
            raise serializers.ValidationError([error_msg])

        # verify that the file has not already been registered
        try:
            PACSFile.objects.get(fname=path)
        except PACSFile.DoesNotExist:
            pass
        else:
            error_msg = "File has already been registered."
            raise serializers.ValidationError({'path': [error_msg]})
        return data
