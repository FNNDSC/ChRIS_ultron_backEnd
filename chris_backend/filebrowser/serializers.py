
import os

from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link
from core.models import ChrisFolder, ChrisLinkFile
from .services import get_folder_file_type, get_folder_file_view_name


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
            file_type = get_folder_file_type(parent_folder)
            if file_type is not None:  # there are files within the parent folder
                try:
                    linked_file = getattr(parent_folder, file_type).get(fname=obj.path)
                except Exception: # file not found
                    return None
                request = self.context['request']
                return reverse(get_folder_file_view_name(parent_folder), request=request,
                           kwargs={'pk': linked_file.pk})
