
import logging

from django.conf import settings
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.swiftmanager import SwiftManager

from .models import PACS, PACSFile


logger = logging.getLogger(__name__)


class PACSSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = PACS
        fields = ('url', 'id', 'identifier')


class PACSFileSerializer(serializers.HyperlinkedModelSerializer):
    file_resource = ItemLinkField('get_file_link')
    path = serializers.CharField(write_only=True)
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    pacs_identifier = serializers.ReadOnlyField(source='pacs.identifier')
    pacs_name = serializers.CharField(write_only=True)

    class Meta:
        model = PACSFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'path', 'PatientID',
                  'PatientName', 'PatientBirthDate', 'PatientAge', 'PatientSex',
                  'StudyDate', 'AccessionNumber', 'Modality', 'ProtocolName',
                  'StudyInstanceUID', 'StudyDescription', 'SeriesInstanceUID',
                  'SeriesDescription', 'pacs_identifier', 'pacs_name', 'file_resource')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def create(self, validated_data):
        """
        Overriden to associate a Swift storage path with the newly created pacs file.
        """
        # remove path as it is not part of the model and then compute fname
        path = validated_data.pop('path')
        pacs_file = super(PACSFileSerializer, self).create(validated_data)
        pacs_file.fname.name = path
        pacs_file.save()
        return pacs_file

    def validate_pacs_name(self, pacs_name):
        """
        Overriden to check whether the provided PACS name is a valid PACS identifier.
        """
        try:
            PACS.objects.get(identifier=pacs_name)
        except PACS.DoesNotExist:
            # validate new PACS identifier
            pacs_serializer = PACSSerializer(data={'identifier': pacs_name})
            try:
                pacs_serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                raise serializers.ValidationError(e.detail['identifier'])
        return pacs_name

    def validate_path(self, path):
        """
        Overriden to check whether the provided path is under SERVICES/PACS/ path.
        """
        path = path.strip(' ').strip('/')
        if not path.startswith('SERVICES/PACS/'):
            raise serializers.ValidationError(
                ["File path must start with 'SERVICES/PACS/'."])
        # verify that the file is indeed already in Swift
        swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        try:
            swift_path_exists = swift_manager.obj_exists(path)
        except Exception as e:
            logger.error('Swift storage error, detail: %s' % str(e))
            raise serializers.ValidationError(["Could not find this path."])
        if not swift_path_exists:
            raise serializers.ValidationError(["Could not find this path."])
        return path

    def validate(self, data):
        """
        Overriden to validate calculated API descriptors from the provided and check
        whether the provided path is already registered.
        """
        # remove pacs_name as it is not part of the model
        pacs_name = data.pop('pacs_name')
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
        # update validated data with a pacs object
        (pacs, tf) = PACS.objects.get_or_create(identifier=pacs_name)
        data.update({'pacs': pacs})
        return data
