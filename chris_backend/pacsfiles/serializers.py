
from django.conf import settings
from rest_framework import serializers

import swiftclient

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link

from .models import PACSFile


class PACSFileSerializer(serializers.HyperlinkedModelSerializer):
    file_resource = ItemLinkField('get_file_link')
    path = serializers.CharField(write_only=True)
    fname = serializers.FileField(use_url=False, required=False)

    class Meta:
        model = PACSFile
        fields = ('url', 'id', 'fname', 'mrn', 'patient_name', 'study', 'series', 'name',
                  'path', 'file_resource')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def create(self, validated_data):
        """
        Overriden to associate a path in Swift with the newly created pacs file.
        """
        path = validated_data.pop('path')
        pacs_file = super(PACSFileSerializer, self).create(validated_data)
        pacs_file.fname.name = path
        pacs_file.save()
        return pacs_file

    def validate_path(self, path):
        """
        Overriden to check that the provided path is under /PACS path.
        """
        path = path.strip(' ').strip('/')
        if not path.startswith('PACS'):
            raise serializers.ValidationError(
                ["You do not have permission to access this path."])
        if len(path.split('/')) != 5:
            raise serializers.ValidationError(
                ["Missing components! Path must be of the form:"
                 "PACS/<MRN>-<PATIENTNAME>/<STUDY>/<SERIES>/<actualDICOMfile>."])
        # verify that the file is indeed already in Swift
        conn = swiftclient.Connection(user=settings.SWIFT_USERNAME,
                                      key=settings.SWIFT_KEY,
                                      authurl=settings.SWIFT_AUTH_URL)
        object_list = conn.get_container(settings.SWIFT_CONTAINER_NAME, prefix=path)[1]
        if not object_list:
            raise serializers.ValidationError(["Could not find this path!"])
        return path

    def validate(self, data):
        """
        Overriden to validate the calculated API descriptors from the provided path
        and check whether the path is already registered.
        """
        path = data.get('path')
        path_parts = path.split('/')
        mrn = path_parts[1].split('-')[0]
        patient_name = path_parts[1].split('-')[1]
        study = path_parts[2]
        series = path_parts[3]
        name = path_parts[4]
        expanded_data = {'mrn': mrn,
                         'patient_name': patient_name,
                         'study': study,
                         'series': series,
                         'name': name}
        # update the request data and validate the expanded data
        data.update(expanded_data)
        serializer = PACSFileSerializer(data=data)
        serializer.validate = lambda x: x  # do not rerun this validate
        serializer.is_valid(raise_exception=True)
        try:
            PACSFile.objects.get(**expanded_data)
        except PACSFile.DoesNotExist:
            pass
        else:
            error_msg = "Path has already been registered!"
            raise serializers.ValidationError({'path': [error_msg]})
        return data
