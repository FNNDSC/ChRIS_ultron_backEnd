from typing import Optional

from rest_framework import serializers
from drf_spectacular.utils import OpenApiTypes, extend_schema_field

from collectionjson.fields import ItemLinkField
from .utils import get_file_resource_link
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


def file_serializer(cls: Optional[serializers.SerializerMetaclass] = None, required: bool = True):
    """
    A class decorator for adding fields to serializers of ``ChrisFile`` views.

    :param cls: the serializer to wrap
    :param required: whether the ``fname`` field is required
    """
    if cls is None:
        return lambda cls: _wrap_file_serializer_class(cls, required)
    return _wrap_file_serializer_class(cls, required)


def _wrap_file_serializer_class(cls: serializers.SerializerMetaclass, required: bool):
    # Implementation notes:
    # - Do not use ``fsize = serializers.ReadOnlyField(source="fname.size")``
    #   See bug: https://github.com/tfranzel/drf-spectacular/issues/1303
    # - Mixin pattern does not work, you get " Field name `fsize` is not valid for model `ChrisFile`."
    #   Decorator pattern is a workaround.
    assert type(cls) == serializers.SerializerMetaclass, f'{cls} is not a serializer'

    class _FileSerializer(cls):
        fname = serializers.FileField(use_url=False, required=required)
        fsize = serializers.SerializerMethodField()
        file_resource = ItemLinkField('get_file_link')
        owner_username = serializers.ReadOnlyField(source='owner.username')
        parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail', read_only=True)
        owner = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

        def get_fsize(self, obj) -> int:
            """
            Get the size of the file in bytes.
            """
            return obj.fname.size

        @extend_schema_field(OpenApiTypes.URI)
        def get_file_link(self, obj):
            """
            Custom method to get the hyperlink to the actual file resource.
            """
            return get_file_resource_link(self, obj)

    _FileSerializer.__name__ = cls.__name__
    return _FileSerializer
