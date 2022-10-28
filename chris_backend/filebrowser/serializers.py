
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.serializers import NoModelSerializer
from collectionjson.fields import ItemLinkField
from core.utils import get_file_resource_link


class FileBrowserPathListSerializer(NoModelSerializer):
    path = serializers.CharField(read_only=True)
    subfolders = serializers.CharField(read_only=True)
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        """
        Overriden to get the url of the path.
        """
        request = self.context['request']
        return reverse('filebrowserpath-list', request=request)


class FileBrowserPathSerializer(NoModelSerializer):
    path = serializers.CharField(read_only=True)
    subfolders = serializers.CharField(read_only=True)
    url = serializers.SerializerMethodField()
    files = ItemLinkField('get_files')

    def get_url(self, obj):
        """
        Overriden to get the url of the path.
        """
        request = self.context['request']
        path = self.context['view'].kwargs.get('path')
        return reverse(
            'filebrowserpath',
            request=request,
            kwargs={
                "path": path})

    def get_files(self, obj):
        """
        Custom method to get the hyperlink to the list of files directly under the path.
        """
        request = self.context['request']
        path = self.context['view'].kwargs.get('path')
        return reverse(
            'filebrowserpathfile-list',
            request=request,
            kwargs={
                "path": path})


class FileBrowserPathFileSerializer(serializers.HyperlinkedModelSerializer):
    fname = serializers.FileField(use_url=False)
    fsize = serializers.ReadOnlyField(source='fname.size')
    file_resource = ItemLinkField('get_file_link')

    class Meta:
        model = None
        fields = ('url', 'creation_date', 'fname', 'fsize', 'file_resource')

    def get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        return get_file_resource_link(self, obj)
