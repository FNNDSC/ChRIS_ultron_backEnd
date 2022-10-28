
import logging

from django.conf import settings
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.swiftmanager import SwiftManager

from .models import Service, ServiceFile
from .models import REGISTERED_SERVICES


logger = logging.getLogger(__name__)


class ServiceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Service
        fields = ('url', 'id', 'identifier')


class ServiceFileSerializer(serializers.HyperlinkedModelSerializer):
    file_resource = ItemLinkField('get_file_link')
    path = serializers.CharField(write_only=True)
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    service_identifier = serializers.ReadOnlyField(source='service.identifier')
    service_name = serializers.CharField(write_only=True)

    class Meta:
        model = ServiceFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'path',
                  'service_identifier', 'service_name', 'file_resource')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def create(self, validated_data):
        """
        Overriden to associate a Swift storage path with the newly created pacs file.
        """
        # remove path as it is not part of the model and compute fname
        path = validated_data.pop('path')
        validated_data['fname'] = path
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
        try:
            Service.objects.get(identifier=service_name)
        except Service.DoesNotExist:
            # validate new Service identifier
            service_serializer = ServiceSerializer(
                data={'identifier': service_name})
            try:
                service_serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                raise serializers.ValidationError(e.detail['identifier'])
        return service_name

    def validate(self, data):
        """
        Overriden to check whether the provided path is under SERVICES/<service_name>/
        path and already registered.
        """
        # remove service_name as it is not part of the model
        service_name = data.pop('service_name')
        # verify that the file path is correct
        path = data.get('path')
        path = path.strip(' ').strip('/')
        prefix = 'SERVICES/%s/' % service_name
        if not path.startswith(prefix):
            error_msg = "File path must start with '%s'." % prefix
            raise serializers.ValidationError([error_msg])
        # verify that the file is indeed already in Swift
        swift_manager = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        try:
            swift_path_exists = swift_manager.obj_exists(path)
        except Exception as e:
            logger.error('Swift storage error, detail: %s' % str(e))
            raise serializers.ValidationError(
                {'path': ["Could not find this path."]})
        if not swift_path_exists:
            raise serializers.ValidationError(
                {'path': ["Could not find this path."]})
        # verify that the file has not already been registered
        try:
            ServiceFile.objects.get(fname=path)
        except ServiceFile.DoesNotExist:
            pass
        else:
            error_msg = "File has already been registered."
            raise serializers.ValidationError({'path': [error_msg]})
        # update validated data
        (service, tf) = Service.objects.get_or_create(identifier=service_name)
        data.update({'path': path, 'service': service})
        return data
