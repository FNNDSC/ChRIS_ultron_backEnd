
from rest_framework import serializers

from .models import ChrisInstance, ChrisFolder


class ChrisInstanceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ChrisInstance
        fields = ('url', 'id', 'creation_date', 'name', 'uuid', 'job_id_prefix',
                  'description')


class ChrisFolderSerializer(serializers.HyperlinkedModelSerializer):
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
    link_files = serializers.HyperlinkedIdentityField(
        view_name='chrisfolder-linkfile-list')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = ChrisFolder
        fields = ('url', 'id', 'creation_date', 'path', 'parent', 'children',
                  'user_files', 'pacs_files', 'service_files', 'link_files',
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
