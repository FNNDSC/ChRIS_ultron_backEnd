
import os

from django.conf import settings
from rest_framework import serializers

from core.models import ChrisFolder
from core.storage import connect_storage
from core.serializers import file_serializer

from .models import UserFile


@file_serializer(required=False)
class UserFileSerializer(serializers.HyperlinkedModelSerializer):
    upload_path = serializers.CharField(max_length=1024, write_only=True, required=False)
    group_permissions = serializers.HyperlinkedIdentityField(
        view_name='filegrouppermission-list')
    user_permissions = serializers.HyperlinkedIdentityField(
        view_name='fileuserpermission-list')

    class Meta:
        model = UserFile
        fields = ('url', 'id', 'creation_date', 'upload_path', 'fname', 'fsize', 'public',
                  'owner_username', 'file_resource', 'parent_folder', 'group_permissions',
                  'user_permissions','owner')

    def create(self, validated_data):
        """
        Overriden to set the file's saving path and parent folder.
        """
        # user file will be stored at: SWIFT_CONTAINER_NAME/<upload_path>
        # where <upload_path> must start with home/<username>/
        upload_path = validated_data.pop('upload_path')
        folder_path = os.path.dirname(upload_path)
        owner = validated_data['owner']

        try:
            parent_folder = ChrisFolder.objects.get(path=folder_path)
        except ChrisFolder.DoesNotExist:
            parent_folder = ChrisFolder.objects.create(path=folder_path, owner=owner)

        validated_data['parent_folder'] = parent_folder
        user_file = UserFile(**validated_data)
        user_file.fname.name = upload_path
        user_file.save()
        return user_file

    def update(self, instance, validated_data):
        """
        Overriden to set the file's saving path and parent folder and delete the old
        path from storage.
        """
        if 'public' in validated_data:
            instance.public = validated_data['public']

        upload_path = validated_data.pop('upload_path', None)

        if upload_path:
            # user file will be stored at: SWIFT_CONTAINER_NAME/<upload_path>
            # where <upload_path> must start with home/
            old_storage_path = instance.fname.name

            storage_manager = connect_storage(settings)
            if storage_manager.obj_exists(upload_path):
                storage_manager.delete_obj(upload_path)

            storage_manager.copy_obj(old_storage_path, upload_path)
            storage_manager.delete_obj(old_storage_path)

            folder_path = os.path.dirname(upload_path)
            owner = instance.owner

            try:
                parent_folder = ChrisFolder.objects.get(path=folder_path)
            except ChrisFolder.DoesNotExist:
                parent_folder = ChrisFolder.objects.create(path=folder_path, owner=owner)

            instance.parent_folder = parent_folder
            instance.fname.name = upload_path

        instance.save()
        return instance

    def validate_upload_path(self, upload_path):
        """
        Overriden to check whether the provided path is under a home/'s subdirectory
        for which the user has write permission.
        """
        upload_path = upload_path.strip().strip('/')

        if upload_path.endswith('.chrislink'):
            raise serializers.ValidationError(["Invalid path. Uploading ChRIS link "
                                               "files is not allowed."])
        if not upload_path.startswith('home/'):
            raise serializers.ValidationError(["Invalid path. Path must start with "
                                               "'home/'."])
        user = self.context['request'].user
        folder_path = os.path.dirname(upload_path)

        while True:
            try:
                folder = ChrisFolder.objects.get(path=folder_path)
            except ChrisFolder.DoesNotExist:
                folder_path = os.path.dirname(folder_path)
            else:
                break

        if not (folder.owner == user or folder.public or
                folder.has_user_permission(user, 'w')):
            raise serializers.ValidationError([f"Invalid path. User does not have write "
                                               f"permission under the folder "
                                               f"'{folder_path}'."])
        return upload_path

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data when
        updating a file. Also to validate that required fields are in data on create
        and remove the 'public' field if passed.
        """
        if self.instance:  # on update
            if 'public' not in data and 'upload_path' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'public' "
                                          "or 'upload_path' must be provided."]})
        else:  # on create
            if 'upload_path' not in data:
                raise serializers.ValidationError(
                    {'upload_path': ["This field is required."]})
            if 'fname' not in data:
                raise serializers.ValidationError(
                    {'fname': ["This field is required."]})

            data.pop('public', None)  # can only be set to public on update
        return data
