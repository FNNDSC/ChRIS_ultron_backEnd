
from rest_framework import serializers

from .models import ChrisInstance, FileDownloadToken


class ChrisInstanceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ChrisInstance
        fields = ('url', 'id', 'creation_date', 'name', 'uuid', 'job_id_prefix',
                  'description')


class FileDownloadTokenSerializer(serializers.HyperlinkedModelSerializer):
    token = serializers.CharField(required=False)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = FileDownloadToken
        fields = ('url', 'id', 'creation_date', 'token', 'owner_username', 'owner')
