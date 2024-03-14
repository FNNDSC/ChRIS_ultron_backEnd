
import logging
import os

from django.conf import settings
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.models import ChrisFolder
from core.utils import get_file_resource_link
from core.storage import connect_storage

from .models import Service, ServiceFile
from .models import REGISTERED_SERVICES


logger = logging.getLogger(__name__)


class ServiceSerializer(serializers.HyperlinkedModelSerializer):
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)

    class Meta:
        model = Service
        fields = ('url', 'id', 'identifier', 'folder')


class ServiceFileSerializer(serializers.HyperlinkedModelSerializer):
    file_resource = ItemLinkField('get_file_link')
    path = serializers.CharField(write_only=True)
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    service_identifier = serializers.ReadOnlyField(source='service.identifier')
    service_name = serializers.CharField(max_length=20, write_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ServiceFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'path',
                  'service_identifier', 'service_name', 'owner_username',
                  'file_resource', 'parent_folder', 'owner')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def create(self, validated_data):
        """
        Overriden to associate a storage path with the newly created service file and
        create a Service object and parent folder if they don't already exist.
        """
        owner = validated_data['owner']

        # remove pacs_name as it is not part of the model
        service_name = validated_data.pop('service_name')
        try:
            Service.objects.get(identifier=service_name)
        except Service.DoesNotExist:
            folder_path = f'SERVICES/{service_name}'
            (pacs_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                 owner=owner)
            service = Service(folder=pacs_folder, identifier=service_name)
            service.save()  # create a Service object

        # remove path as it is not part of the model and then compute fname
        path = validated_data.pop('path')
        validated_data['fname'] = path

        folder_path = os.path.dirname(path)
        (file_parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                    owner=owner)
        validated_data['parent_folder'] = file_parent_folder
        return super(ServiceFileSerializer, self).create(validated_data)

    def validate_service_name(self, service_name):
        """
        Overriden to check whether the provided service name is a valid service
        identifier.
        """
        if service_name in REGISTERED_SERVICES:
            error_msg = "This is the name of a registered service. Please use the " \
                        "service-specific API."
            raise serializers.ValidationError([error_msg])
        return service_name

    def validate(self, data):
        """
        Overriden to check whether the provided path is under SERVICES/<service_name>/
        path and already registered.
        """
        service_name = data.get('service_name')

        # verify that the file path is correct
        path = data.get('path')
        path = path.strip(' ').strip('/')
        prefix = 'SERVICES/%s/' % service_name
        if not path.startswith(prefix):
            error_msg = "File path must start with '%s'." % prefix
            raise serializers.ValidationError([error_msg])

        # verify that the file is indeed already in storage
        storage_manager = connect_storage(settings)
        try:
            storage_path_exists = storage_manager.obj_exists(path)
        except Exception as e:
            logger.error('Storage error, detail: %s' % str(e))
            raise serializers.ValidationError({'path': ["Could not find this path."]})
        if not storage_path_exists:
            raise serializers.ValidationError({'path': ["Could not find this path."]})

        # verify that the file has not already been registered
        try:
            ServiceFile.objects.get(fname=path)
        except ServiceFile.DoesNotExist:
            pass
        else:
            error_msg = "File has already been registered."
            raise serializers.ValidationError({'path': [error_msg]})

        # update validated data
        data.update({'path': path})
        return data
