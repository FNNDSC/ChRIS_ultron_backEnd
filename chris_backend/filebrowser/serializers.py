
from rest_framework import serializers
from core.models import ChrisFolder


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
