
import os

from django.contrib.auth.models import User, Group
from django.db.utils import IntegrityError
from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from core.storage import connect_storage
from core.utils import get_file_resource_link
from core.models import (ChrisFolder, ChrisFile, ChrisLinkFile, FolderGroupPermission,
                         FolderUserPermission, FileGroupPermission, FileUserPermission,
                         LinkFileGroupPermission, LinkFileUserPermission)


class FileBrowserFolderSerializer(serializers.HyperlinkedModelSerializer):
    path = serializers.CharField(max_length=1024, required=False)
    parent = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    children = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-child-list')
    files = serializers.HyperlinkedIdentityField(view_name='chrisfolder-file-list')
    link_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-linkfile-list')
    group_permissions = serializers.HyperlinkedIdentityField(
        view_name='foldergrouppermission-list')
    user_permissions = serializers.HyperlinkedIdentityField(
        view_name='folderuserpermission-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFolder
        fields = ('url', 'id', 'creation_date', 'path', 'public', 'parent', 'children',
                  'files', 'link_files', 'group_permissions', 'user_permissions', 'owner')

    def create(self, validated_data):
        """
        Overriden to set the parent folder.
        """
        path = validated_data['path']
        parent_path = os.path.dirname(path)
        owner = validated_data['owner']

        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=parent_path,
                                                               owner=owner)
        validated_data['parent'] = parent_folder
        return super(FileBrowserFolderSerializer, self).create(validated_data)

    def update(self, instance, validated_data):
        """
        Overriden to grant or remove public access to the folder and all its
        descendant folders, link files and files depending on the new public status of
        the folder.
        """
        if 'public' in validated_data:
            if instance.public and not validated_data['public']:
                instance.remove_public_link()
                instance.remove_public_access()

            elif not instance.public and validated_data['public']:
                instance.grant_public_access()
                instance.create_public_link()
        return super(FileBrowserFolderSerializer, self).update(instance, validated_data)

    def validate_path(self, path):
        """
        Overriden to check whether the provided path is under a home/'s subdirectory
        for which the user has write permission. Also to check whether the folder
        already exists.
        """
        # remove leading and trailing slashes
        path = path.strip(' ').strip('/')

        if not path.startswith('home/'):
            raise serializers.ValidationError(["Invalid path. Path must start with "
                                               "'home/'."])
        try:
            ChrisFolder.objects.get(path=path)
        except ChrisFolder.DoesNotExist:
            pass
        else:
            raise serializers.ValidationError([f"Folder with path '{path}' already "
                                               f"exists."])
        user = self.context['request'].user
        parent_folder_path = os.path.dirname(path)

        while True:
            try:
                parent_folder = ChrisFolder.objects.get(path=parent_folder_path)
            except ChrisFolder.DoesNotExist:
                parent_folder_path = os.path.dirname(parent_folder_path)
            else:
                break

        if not (parent_folder.owner == user or parent_folder.public or
                parent_folder.has_user_permission(user, 'w')):
            raise serializers.ValidationError([f"Invalid path. User do not have write "
                                               f"permission under the folder "
                                               f"'{parent_folder_path}'."])
        return path

    def validate_public(self, public):
        """
        Overriden to check that only the owner or superuser chris can change a folder's
        public status.
        """
        if self.instance:  # on update
            user = self.context['request'].user

            if not (self.instance.owner == user or user.username == 'chris'):
                raise serializers.ValidationError(
                    ["Public status of a feed can only be changed by its owner or"
                     "superuser 'chris'."])
        return public

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a folder.
        """
        if self.instance:  # on update
            if 'public' not in data:
                raise serializers.ValidationError({'public': ['This field is required.']})
        else:
            if 'path' not in data: # on create
                raise serializers.ValidationError({'path': ['This field is required.']})
        return data


class FileBrowserFolderGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True, required=False)
    folder_id = serializers.ReadOnlyField(source='folder.id')
    folder_name = serializers.ReadOnlyField(source='folder.name')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    group = serializers.HyperlinkedRelatedField(view_name='group-detail', read_only=True)

    class Meta:
        model = FolderGroupPermission
        fields = ('url', 'id', 'permission', 'folder_id', 'folder_name', 'group_id',
                  'group_name', 'folder', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to the folder is created if it doesn't exist.
        """
        folder = validated_data['folder']
        group = validated_data['group']

        try:
            perm = super(FileBrowserFolderGroupPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"Group '{group.name}' already has a permission to access folder "
                      f"with id {folder.id}"]})

        lf = folder.create_shared_link()
        lf.grant_group_permission(group, 'r')
        return perm

    def validate_grp_name(self, grp_name):
        """
        Custom method to check whether the provided group name exists in the DB.
        """
        try:
            group = Group.objects.get(name=grp_name)
        except Group.DoesNotExist:
            raise serializers.ValidationError(
                {'grp_name': [f"Couldn't find any group with name '{grp_name}'."]})
        return group

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'grp_name' not in data: # on create
                raise serializers.ValidationError({'grp_name':
                                                       ['This field is required.']})
        return data


class FileBrowserFolderUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32,
                                     required=False)
    folder_id = serializers.ReadOnlyField(source='folder.id')
    folder_name = serializers.ReadOnlyField(source='folder.name')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')
    folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = FolderUserPermission
        fields = ('url', 'id', 'permission', 'folder_id', 'folder_name', 'user_id',
                  'user_username', 'folder', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to the folder is created if it doesn't exist.
        """
        folder = validated_data['folder']
        user = validated_data['user']

        try:
            perm = super(FileBrowserFolderUserPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"User '{user.username}' already has a permission to access "
                      f"folder with id {folder.id}"]})

        lf = folder.create_shared_link()
        lf.grant_user_permission(user, 'r')
        return perm

    def validate_username(self, username):
        """
        Custom method to check whether the provided username exists in the DB.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'username': [f"Couldn't find any user with username '{username}'."]})
        return user

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'username' not in data: # on create
                raise serializers.ValidationError({'username':
                                                       ['This field is required.']})
        return data


class FileBrowserFileSerializer(serializers.HyperlinkedModelSerializer):
    new_file_path = serializers.CharField(max_length=1024, write_only=True,
                                          required=False)
    fname = serializers.FileField(use_url=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    group_permissions = serializers.HyperlinkedIdentityField(
        view_name='filegrouppermission-list')
    user_permissions = serializers.HyperlinkedIdentityField(
        view_name='fileuserpermission-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'public',
                  'new_file_path', 'owner_username', 'file_resource', 'parent_folder',
                  'group_permissions', 'user_permissions', 'owner')

    def update(self, instance, validated_data):
        """
        Overriden to set the file's saving path and parent folder and delete the old
        path from storage.
        """
        if 'public' in validated_data:
            instance.public = validated_data['public']

        new_file_path = validated_data.pop('new_file_path', None)

        if new_file_path:
            # user file will be stored at: SWIFT_CONTAINER_NAME/<new_file_path>
            # where <new_file_path> must start with home/

            old_storage_path = instance.fname.name

            storage_manager = connect_storage(settings)
            if storage_manager.obj_exists(new_file_path):
                storage_manager.delete_obj(new_file_path)

            storage_manager.copy_obj(old_storage_path, new_file_path)
            storage_manager.delete_obj(old_storage_path)

            folder_path = os.path.dirname(new_file_path)
            owner = instance.owner
            (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                   owner=owner)
            instance.parent_folder = parent_folder
            instance.fname.name = new_file_path

        instance.save()
        return instance

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def validate_new_file_path(self, new_file_path):
        """
        Overriden to check whether the provided path is under a home/'s subdirectory
        for which the user has write permission.
        """
        # remove leading and trailing slashes
        new_file_path = new_file_path.strip(' ').strip('/')

        if new_file_path.endswith('.chrislink'):
            raise serializers.ValidationError(["Invalid path. This is not a ChRIS link "
                                               "file."])
        if not new_file_path.startswith('home/'):
            raise serializers.ValidationError(["Invalid path. Path must start with "
                                               "'home/'."])
        user = self.context['request'].user
        folder_path = os.path.dirname(new_file_path)

        while True:
            try:
                folder = ChrisFolder.objects.get(path=folder_path)
            except ChrisFolder.DoesNotExist:
                folder_path = os.path.dirname(folder_path)
            else:
                break

        if not (folder.owner == user or folder.public or
                folder.has_user_permission(user, 'w')):
            raise serializers.ValidationError([f"Invalid path. User do not have write "
                                               f"permission under the folder "
                                               f"'{folder_path}'."])
        return new_file_path

    def validate_public(self, public):
        """
        Overriden to check that only the owner or superuser chris can change a file's
        public status.
        """
        if self.instance:  # on update
            user = self.context['request'].user

            if not (self.instance.owner == user or user.username == 'chris'):
                raise serializers.ValidationError(
                    ["Public status of a feed can only be changed by its owner or"
                     "superuser 'chris'."])
        return public

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data when
        updating a file.
        """
        if self.instance:  # on update
            if 'public' not in data and 'new_file_path' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'public' "
                                          "or 'new_file_path' must be provided."]})
        return data


class FileBrowserFileGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True, required=False)
    file_id = serializers.ReadOnlyField(source='file.id')
    file_fname = serializers.ReadOnlyField(source='file.fname')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')
    file = serializers.HyperlinkedRelatedField(view_name='chrisfile-detail',
                                               read_only=True)
    group = serializers.HyperlinkedRelatedField(view_name='group-detail', read_only=True)

    class Meta:
        model = FileGroupPermission
        fields = ('url', 'id', 'permission', 'file_id', 'file_fname', 'group_id',
                  'group_name', 'file', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to the file is created if it doesn't exist.
        """
        f = validated_data['file']
        group = validated_data['group']

        try:
            perm = super(FileBrowserFileGroupPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"Group '{group.name}' already has a permission to access file "
                      f"with id {f.id}"]})

        lf = f.create_shared_link()
        lf.grant_group_permission(group, 'r')
        return perm

    def validate_grp_name(self, grp_name):
        """
        Custom method to check whether the provided group name exists in the DB.
        """
        try:
            group = Group.objects.get(name=grp_name)
        except Group.DoesNotExist:
            raise serializers.ValidationError(
                {'grp_name': [f"Couldn't find any group with name '{grp_name}'."]})
        return group

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'grp_name' not in data: # on create
                raise serializers.ValidationError({'grp_name':
                                                       ['This field is required.']})
        return data


class FileBrowserFileUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32,
                                     required=False)
    file_id = serializers.ReadOnlyField(source='file.id')
    file_fname = serializers.ReadOnlyField(source='file.fname')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')
    file = serializers.HyperlinkedRelatedField(view_name='chrisfile-detail',
                                               read_only=True)
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = FileUserPermission
        fields = ('url', 'id', 'permission', 'file_id', 'file_fname', 'user_id',
                  'user_username', 'file', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to the file is created if it doesn't exist.
        """
        f = validated_data['file']
        user = validated_data['user']

        try:
            perm = super(FileBrowserFileUserPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"User '{user.username}' already has a permission to access "
                      f"file with id {f.id}"]})

        lf = f.create_shared_link()
        lf.grant_user_permission(user, 'r')
        return perm

    def validate_username(self, username):
        """
        Custom method to check whether the provided username exists in the DB.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'username': [f"Couldn't find any user with username '{username}'."]})
        return user

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'username' not in data: # on create
                raise serializers.ValidationError({'username':
                                                       ['This field is required.']})
        return data


class FileBrowserLinkFileSerializer(serializers.HyperlinkedModelSerializer):
    new_link_file_path = serializers.CharField(max_length=1024, write_only=True,
                                               required=False)
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    linked_folder = ItemLinkField('get_linked_folder_link')
    linked_file = ItemLinkField('get_linked_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    group_permissions = serializers.HyperlinkedIdentityField(
        view_name='linkfilegrouppermission-list')
    user_permissions = serializers.HyperlinkedIdentityField(
        view_name='linkfileuserpermission-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisLinkFile
        fields = ('url', 'id', 'creation_date', 'path', 'fname', 'fsize', 'public',
                  'new_link_file_path', 'owner_username', 'file_resource',
                  'linked_folder', 'linked_file', 'parent_folder', 'group_permissions',
                  'user_permissions', 'owner')

    def update(self, instance, validated_data):
        """
        Overriden to set the link file's saving path and parent folder and delete
        the old path from storage.
        """
        if 'public' in validated_data:
            instance.public = validated_data['public']

        new_link_file_path = validated_data.pop('new_link_file_path', None)

        if new_link_file_path:
            # user file will be stored at: SWIFT_CONTAINER_NAME/<new_link_file_path>
            # where <new_link_file_path> must start with home/

            old_storage_path = instance.fname.name

            storage_manager = connect_storage(settings)
            if storage_manager.obj_exists(new_link_file_path):
                storage_manager.delete_obj(new_link_file_path)

            storage_manager.copy_obj(old_storage_path, new_link_file_path)
            storage_manager.delete_obj(old_storage_path)

            folder_path = os.path.dirname(new_link_file_path)
            owner = instance.owner
            (parent_folder, _) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                   owner=owner)
            instance.parent_folder = parent_folder
            instance.fname.name = new_link_file_path

        instance.save()
        return instance

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)

    def get_linked_folder_link(self, obj):
        """
        Custom method to get the hyperlink to the linked folder if the ChRIS link
        points to a folder.
        """
        try:
            linked_folder = ChrisFolder.objects.get(path=obj.path)
        except ChrisFolder.DoesNotExist:
            return None
        request = self.context['request']
        return reverse('chrisfolder-detail', request=request,
                       kwargs={'pk': linked_folder.pk})

    def get_linked_file_link(self, obj):
        """
        Custom method to get the hyperlink to the linked file if the ChRIS link
        points to a file.
        """
        try:
            ChrisFolder.objects.get(path=obj.path)
        except ChrisFolder.DoesNotExist:
            parent_folder_path = os.path.dirname(obj.path)

            try:
                parent_folder = ChrisFolder.objects.get(path=parent_folder_path)
            except ChrisFolder.DoesNotExist: # no parent folder then no file
                return None

            try:
                linked_file = parent_folder.chris_files.get(fname=obj.path)
            except ChrisFile.DoesNotExist:  # file not found
                return None

            request = self.context['request']
            return reverse('chrisfile-detail', request=request,
                           kwargs={'pk': linked_file.pk})

    def validate_new_link_file_path(self, new_link_file_path):
        """
        Overriden to check whether the provided path is under a home/'s subdirectory
        for which the user has write permission.
        """
        # remove leading and trailing slashes
        new_link_file_path = new_link_file_path.strip(' ').strip('/')

        if new_link_file_path.endswith('.chrislink'):
            raise serializers.ValidationError(["Invalid path. This is not a ChRIS link "
                                               "file."])
        if not new_link_file_path.startswith('home/'):
            raise serializers.ValidationError(["Invalid path. Path must start with "
                                               "'home/'."])
        user = self.context['request'].user
        folder_path = os.path.dirname(new_link_file_path)

        while True:
            try:
                folder = ChrisFolder.objects.get(path=folder_path)
            except ChrisFolder.DoesNotExist:
                folder_path = os.path.dirname(folder_path)
            else:
                break

        if not (folder.owner == user or folder.public or
                folder.has_user_permission(user, 'w')):
            raise serializers.ValidationError([f"Invalid path. User do not have write "
                                               f"permission under the folder "
                                               f"'{folder_path}'."])
        return new_link_file_path

    def validate_public(self, public):
        """
        Overriden to check that only the owner or superuser chris can change a link
        file's public status.
        """
        if self.instance:  # on update
            user = self.context['request'].user

            if not (self.instance.owner == user or user.username == 'chris'):
                raise serializers.ValidationError(
                    ["Public status of a feed can only be changed by its owner or"
                     "superuser 'chris'."])
        return public

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data when
        updating a file.
        """
        if self.instance:  # on update
            if 'public' not in data and 'new_link_file_path' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'public' "
                                          "or 'new_link_file_path' must be provided."]})
        return data


class FileBrowserLinkFileGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True, required=False)
    link_file_id = serializers.ReadOnlyField(source='link_file.id')
    link_file_fname = serializers.ReadOnlyField(source='link_file.fname')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')
    link_file = serializers.HyperlinkedRelatedField(view_name='chrislinkfile-detail',
                                                    read_only=True)
    group = serializers.HyperlinkedRelatedField(view_name='group-detail', read_only=True)

    class Meta:
        model = FileGroupPermission
        fields = ('url', 'id', 'permission', 'link_file_id', 'link_file_fname',
                  'group_id', 'group_name', 'link_file', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to this link file is created if it doesn't exist.
        """
        lf = validated_data['link_file']
        group = validated_data['group']

        try:
            perm = super(FileBrowserLinkFileGroupPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"Group '{group.name}' already has a permission to access link "
                      f"file with id {lf.id}"]})

        shared_lf = lf.create_shared_link()
        shared_lf.grant_group_permission(group, 'r')
        return perm

    def validate_grp_name(self, grp_name):
        """
        Custom method to check whether the provided group name exists in the DB.
        """
        try:
            group = Group.objects.get(name=grp_name)
        except Group.DoesNotExist:
            raise serializers.ValidationError(
                {'grp_name': [f"Couldn't find any group with name '{grp_name}'."]})
        return group

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'grp_name' not in data: # on create
                raise serializers.ValidationError({'grp_name':
                                                       ['This field is required.']})
        return data


class FileBrowserLinkFileUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32,
                                     required=False)
    link_file_id = serializers.ReadOnlyField(source='link_file.id')
    link_file_fname = serializers.ReadOnlyField(source='link_file.fname')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')
    link_file = serializers.HyperlinkedRelatedField(view_name='chrislinkfile-detail',
                                                    read_only=True)
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = FileUserPermission
        fields = ('url', 'id', 'permission', 'link_file_id', 'link_file_fname', 'user_id',
                  'user_username', 'link_file', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted. Also a link file in the SHARED folder
        pointing to this link file is created if it doesn't exist.
        """
        lf = validated_data['link_file']
        user = validated_data['user']

        try:
            perm = super(FileBrowserLinkFileUserPermissionSerializer,
                         self).create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {'non_field_errors':
                     [f"User '{user.username}' already has a permission to access "
                      f"file with id {lf.id}"]})

        shared_lf = lf.create_shared_link()
        shared_lf.grant_user_permission(user, 'r')
        return perm

    def validate_username(self, username):
        """
        Custom method to check whether the provided username exists in the DB.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'username': [f"Couldn't find any user with username '{username}'."]})
        return user

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating or
        updating a permission.
        """
        if self.instance:  # on update
            if 'permission' not in data:
                raise serializers.ValidationError({'permission':
                                                       ['This field is required.']})
        else:
            if 'username' not in data: # on create
                raise serializers.ValidationError({'username':
                                                       ['This field is required.']})
        return data
