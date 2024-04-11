
import os

from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.models import ChrisFolder, ChrisFile, ChrisLinkFile


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
        fields = ('url', 'id', 'creation_date', 'path', 'parent', 'children',
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


class FileBrowserChrisFileSerializer(serializers.HyperlinkedModelSerializer):
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


class FileBrowserChrisLinkFileSerializer(serializers.HyperlinkedModelSerializer):
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
