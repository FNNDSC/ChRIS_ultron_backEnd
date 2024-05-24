
import os

from django.contrib.auth.models import User, Group
from django.db.utils import IntegrityError
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.models import (ChrisFolder, ChrisFile, ChrisLinkFile, FolderGroupPermission,
                         FolderUserPermission, FileGroupPermission, FileUserPermission,
                         LinkFileGroupPermission, LinkFileUserPermission)


class FileBrowserFolderSerializer(serializers.HyperlinkedModelSerializer):
    parent = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    children = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-child-list')
    files = serializers.HyperlinkedIdentityField(view_name='chrisfolder-file-list')
    link_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-linkfile-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFolder
        fields = ('url', 'id', 'creation_date', 'path', 'public', 'parent', 'children',
                  'files', 'link_files', 'owner')

    def create(self, validated_data):
        """
        Overriden to set the parent folder.
        """
        path = validated_data.get('path')
        parent_path = os.path.dirname(path)
        owner = validated_data['owner']

        (parent_folder, _) = ChrisFolder.objects.get_or_create(path=parent_path,
                                                               owner=owner)
        validated_data['parent'] = parent_folder
        return super(FileBrowserFolderSerializer, self).create(validated_data)

    def validate_path(self, path):
        """
        Overriden to check whether the provided path is under home/<username>/ but not
        under home/<username>/feeds/.
        """
        # remove leading and trailing slashes
        path = path.strip(' ').strip('/')
        user = self.context['request'].user
        prefix = f'home/{user.username}/'

        if path.startswith(prefix + 'feeds/'):
            error_msg = f"Invalid field value. Creating folders with a path under the " \
                        f"feed's directory '{prefix + 'feeds/'}' is not allowed."
            raise serializers.ValidationError([error_msg])

        if not path.startswith(prefix):
            error_msg = f"Invalid field value. Path must start with '{prefix}'."
            raise serializers.ValidationError([error_msg])

        try:
            ChrisFolder.objects.get(path=path)
        except ChrisFolder.DoesNotExist:
            pass
        else:
            error_msg = f"Folder with path '{path}' already exists."
            raise serializers.ValidationError([error_msg])
        return path


class FileBrowserFolderGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True)
    folder_id = serializers.ReadOnlyField(source='folder.id')
    folder_name = serializers.ReadOnlyField(source='folder.name')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')

    class Meta:
        model = FolderGroupPermission
        fields = ('url', 'id', 'permission', 'folder_id', 'folder_name', 'group_id',
                  'group_name', 'folder', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted.
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

class FileBrowserFolderUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32)
    folder_id = serializers.ReadOnlyField(source='folder.id')
    folder_name = serializers.ReadOnlyField(source='folder.name')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = FolderUserPermission
        fields = ('url', 'id', 'permission', 'folder_id', 'folder_name', 'user_id',
                  'user_username', 'folder', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted.
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


class FileBrowserFileSerializer(serializers.HyperlinkedModelSerializer):
    fname = serializers.FileField(use_url=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize',
                  'owner_username', 'file_resource', 'parent_folder', 'owner')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)


class FileBrowserFileGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True)
    file_id = serializers.ReadOnlyField(source='file.id')
    file_fname = serializers.ReadOnlyField(source='file.fname')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')

    class Meta:
        model = FileGroupPermission
        fields = ('url', 'id', 'permission', 'file_id', 'file_fname', 'group_id',
                  'group_name', 'file', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted.
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


class FileBrowserFileUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32)
    file_id = serializers.ReadOnlyField(source='file.id')
    file_fname = serializers.ReadOnlyField(source='file.fname')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = FileUserPermission
        fields = ('url', 'id', 'permission', 'file_id', 'file_fname', 'user_id',
                  'user_username', 'file', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted.
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


class FileBrowserLinkFileSerializer(serializers.HyperlinkedModelSerializer):
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    linked_folder = ItemLinkField('get_linked_folder_link')
    linked_file = ItemLinkField('get_linked_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisLinkFile
        fields = ('url', 'id', 'creation_date', 'path', 'fname', 'fsize',
                  'owner_username', 'file_resource', 'linked_folder', 'linked_file',
                  'parent_folder', 'owner')

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


class FileBrowserLinkFileGroupPermissionSerializer(serializers.HyperlinkedModelSerializer):
    grp_name = serializers.CharField(write_only=True)
    link_file_id = serializers.ReadOnlyField(source='link_file.id')
    link_file_fname = serializers.ReadOnlyField(source='link_file.fname')
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')

    class Meta:
        model = FileGroupPermission
        fields = ('url', 'id', 'permission', 'link_file_id', 'link_file_fname',
                  'group_id', 'group_name', 'link_file', 'group', 'grp_name')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a group that
        already has a permission granted.
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


class FileBrowserLinkFileUserPermissionSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32)
    link_file_id = serializers.ReadOnlyField(source='link_file.id')
    link_file_fname = serializers.ReadOnlyField(source='link_file.fname')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = FileUserPermission
        fields = ('url', 'id', 'permission', 'link_file_id', 'link_file_fname', 'user_id',
                  'user_username', 'link_file', 'user', 'username')

    def create(self, validated_data):
        """
        Overriden to handle the error when trying to create a permission for a user that
        already has a permission granted.
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
