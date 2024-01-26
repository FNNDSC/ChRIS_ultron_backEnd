
import os

from django.conf import settings
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.models import ChrisFolder
from core.storage import connect_storage

from .models import UserFile


class UserFileSerializer(serializers.HyperlinkedModelSerializer):
    fname = serializers.FileField(use_url=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    upload_path = serializers.CharField(write_only=True)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = UserFile
        fields = ('url', 'id', 'creation_date', 'upload_path', 'fname', 'fsize',
                  'owner_username', 'file_resource', 'parent_folder', 'owner')

    def create(self, validated_data):
        """
        Overriden to set the file's saving path and parent folder.
        """
        # user file will be stored at: SWIFT_CONTAINER_NAME/<upload_path>
        # where <upload_path> must start with home/<username>/
        upload_path = validated_data.pop('upload_path')
        folder_path = os.path.dirname(upload_path)
        owner = validated_data['owner']

        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                               owner=owner)
        validated_data['parent_folder'] = parent_folder
        user_file = UserFile(**validated_data)
        user_file.fname.name = upload_path
        user_file.save()
        return user_file

    def update(self, instance, validated_data):
        """
        Overriden to set the file's saving path and parent folder and  delete the old
        path from storage.
        """
        # user file will be stored at: SWIFT_CONTAINER_NAME/<upload_path>
        # where <upload_path> must start with home/<username>/
        upload_path = validated_data.pop('upload_path')
        old_storage_path = instance.fname.name

        storage_manager = connect_storage(settings)
        if storage_manager.obj_exists(upload_path):
            storage_manager.delete_obj(upload_path)
        storage_manager.copy_obj(old_storage_path, upload_path)
        storage_manager.delete_obj(old_storage_path)

        folder_path = os.path.dirname(upload_path)
        owner = instance.owner
        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                               owner=owner)
        instance.parent_folder = parent_folder
        instance.fname.name = upload_path
        instance.save()
        return instance

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def validate_upload_path(self, upload_path):
        """
        Overriden to check whether the provided path is under home/<username>/ but not
        under home/<username>/feeds/.
        """
        # remove leading and trailing slashes
        upload_path = upload_path.strip(' ').strip('/')
        user = self.context['request'].user
        prefix = f'home/{user.username}/'
        if upload_path.startswith(prefix + 'feeds/'):
            error_msg = f"Invalid file path. Uploading files to a path under the " \
                        f"feed's directory '{prefix + 'feeds/'}' is not allowed."
            raise serializers.ValidationError([error_msg])
        if not upload_path.startswith(prefix):
            error_msg = f"Invalid file path. Path must start with '{prefix}'."
            raise serializers.ValidationError([error_msg])
        return upload_path
