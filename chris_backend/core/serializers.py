
from rest_framework import serializers

from drf_spectacular.utils import OpenApiTypes, extend_schema_field

from collectionjson.fields import ItemLinkField
from .models import ChrisInstance, FileDownloadToken, ChrisFile, ChrisLinkFile
from .utils import get_file_resource_link


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


class _ChrisFileSerializerMetaclass(serializers.SerializerMetaclass):
    """
    A metaclass to require that the Meta inner class' model attribute is ChrisFile.
    """
    def __new__(cls, name, bases, dct):
        if set(bases) == {serializers.HyperlinkedModelSerializer}:
            # skip validation of ChrisFileSerializer, which is a
            # direct subclass of HyperlinkedModelSerializer
            return super().__new__(cls, name, bases, dct)
        if (Meta := dct.get('Meta', None)) is None:
            raise TypeError(f'{name} must have an inner class called Meta')
        if not issubclass(getattr(Meta, 'model', None), (ChrisFile, ChrisLinkFile)):
            raise TypeError(f'{name}.Meta.model must be ChrisFile or ChrisLinkFile')
        return super().__new__(cls, name, bases, dct)


class ChrisFileSerializer(serializers.HyperlinkedModelSerializer,
                          metaclass=_ChrisFileSerializerMetaclass):
    """
    A superclass for serializers of ``ChrisFile`` or similar.
    """
    fname = serializers.FileField(use_url=False, allow_empty_file=True, required=False)
    fsize = serializers.SerializerMethodField()
    file_resource = ItemLinkField('get_file_link')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    parent_folder = serializers.HyperlinkedRelatedField(view_name='chrisfolder-detail',
                                                        read_only=True)
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
