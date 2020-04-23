
import os

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link

from .models import UploadedFile


class UploadedFileSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail',
                                               read_only=True)
    file_resource = ItemLinkField('get_file_link')
    fname = serializers.FileField(use_url=False)
    upload_path = serializers.CharField()

    class Meta:
        model = UploadedFile
        fields = ('url', 'id', 'creation_date', 'upload_path', 'fname', 'file_resource',
                  'owner')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def validate_file_upload_path(self, path):
        """
        Custom method to check that the provided path is unique for this user in the DB.
        """
        # remove leading and trailing slashes
        path = path.strip('/')
        if not path:
            raise serializers.ValidationError({'upload_path': ["Invalid file path."]})
        path = os.path.join('/', path)
        try:
            # check if path for this file already exists in the db
            user = self.context['request'].user
            UploadedFile.objects.get(owner=user.id, upload_path=path)
        except ObjectDoesNotExist:
            return path
        else:
            raise serializers.ValidationError({'upload_path': ["File already exists."]})
