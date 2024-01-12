
from rest_framework import serializers

from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link

from .models import ChrisInstance, ChrisFolder, ChrisLinkFile
from .utils import get_file_resource_link


class ChrisInstanceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ChrisInstance
        fields = ('url', 'id', 'creation_date', 'name', 'uuid', 'job_id_prefix',
                  'description')


class ChrisFolderSerializer(serializers.HyperlinkedModelSerializer):
    size = serializers.ReadOnlyField()
    parent = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                 read_only=True)
    children = serializers.HyperlinkedIdentityField(view_name='chrisfolder-child-list')
    user_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-userfile-list')
    pacs_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-pacsfile-list')
    service_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-servicefile-list')
    pipeline_source_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-pipelinesourcefile-list')
    chris_link_files = serializers.HyperlinkedIdentityField(
        view_name='chrislinkfile-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFolder
        fields = ('url', 'id', 'creation_date', 'path', 'size', 'parent', 'children',
                  'user_files', 'pacs_files', 'service_files', 'chris_link_files',
                  'pipeline_source_files', 'owner')

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
            error_msg = f"Invalid file path. Creating folders with a path under the " \
                        f"feed's directory '{prefix + 'feeds/'}' is not allowed."
            raise serializers.ValidationError([error_msg])
        if not path.startswith(prefix):
            error_msg = f"Invalid file path. Path must start with '{prefix}'."
            raise serializers.ValidationError([error_msg])
        return path


class ChrisLinkFileSerializer(serializers.HyperlinkedModelSerializer):
    fname = serializers.FileField(use_url=False, required=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    file_resource = ItemLinkField('get_file_link')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisLinkFile
        fields = ('url', 'id', 'creation_date', 'path', 'is_folder', 'fname', 'fsize',
                  'owner_username', 'file_resource', 'parent_folder', 'owner')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)
