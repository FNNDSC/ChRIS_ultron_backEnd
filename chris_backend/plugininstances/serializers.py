
import pathlib

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from plugins.models import TYPES
from feeds.models import Feed

from .models import PluginInstance, PluginInstanceFile
from .models import FloatParameter, IntParameter, BoolParameter
from .models import PathParameter, UnextpathParameter, StrParameter


class PluginInstanceSerializer(serializers.HyperlinkedModelSerializer):
    previous_id = serializers.ReadOnlyField(source='previous.id')
    plugin_id = serializers.ReadOnlyField(source='plugin.id')
    plugin_name = serializers.ReadOnlyField(source='plugin.name')
    plugin_version = serializers.ReadOnlyField(source='plugin.version')
    pipeline_id = serializers.ReadOnlyField(source='pipeline_inst.pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='pipeline_inst.pipeline.name')
    pipeline_inst_id = serializers.ReadOnlyField(source='pipeline_inst.id')
    feed_id = serializers.ReadOnlyField(source='feed.id')
    owner_username = serializers.ReadOnlyField(source='owner.username')
    compute_resource_identifier = serializers.ReadOnlyField(
        source='compute_resource.compute_resource_identifier')
    previous = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                   read_only=True)
    descendants = serializers.HyperlinkedIdentityField(
        view_name='plugininstance-descendant-list')
    parameters = serializers.HyperlinkedIdentityField(
        view_name='plugininstance-parameter-list')
    files = serializers.HyperlinkedIdentityField(
        view_name='plugininstancefile-list')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    pipeline_inst = serializers.HyperlinkedRelatedField(
        view_name='pipelineinstance-detail', read_only=True)
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail',
                                               read_only=True)

    class Meta:
        model = PluginInstance
        fields = ('url', 'id', 'title', 'previous_id', 'plugin_id', 'plugin_name',
                  'plugin_version', 'pipeline_id', 'pipeline_name', 'pipeline_inst_id',
                  'pipeline_inst', 'feed_id', 'start_date', 'end_date', 'status',
                  'owner_username', 'previous', 'feed', 'plugin', 'descendants', 'files',
                  'parameters', 'compute_resource_identifier', 'cpu_limit',
                  'memory_limit', 'number_of_workers', 'gpu_limit')

    def validate_previous(self, previous_id):
        """
        Custom method to check that an id is provided for previous instance when
        corresponding plugin is of type 'ds'. Then check that the provided id exists in
        the DB and that the user can run plugins within this feed.
        """
        # using self.context['view'] in validators prevents calling is_valid when creating
        # a new serializer instance outside the Django view framework. But here is fine
        # as plugin instances are always created through the API
        plugin = self.context['view'].get_object()
        previous = None
        if plugin.type=='ds':
            if not previous_id:
                raise serializers.ValidationError(
                    {'previous_id': ["This field is required."]})
            try:
                pk = int(previous_id)
                previous = PluginInstance.objects.get(pk=pk)
            except (ValueError, ObjectDoesNotExist):
                err_str = "Couldn't find any 'previous' plugin instance with id %s."
                raise serializers.ValidationError(
                    {'previous_id': [err_str % previous_id]})
            # check that the user can run plugins within this feed
            user = self.context['request'].user
            if user not in previous.feed.owner.all():
                err_str = "User is not an owner of feed for previous instance with id %s."
                raise serializers.ValidationError(
                    {'previous_id': [err_str % previous_id]})
        return previous

    def validate_status(self, status):
        if self.instance and (status != 'cancelled' or
                              self.instance.status not in ['started', 'cancelled']):
            raise serializers.ValidationError(["Can not change status from %s to %s." %
                                               (self.instance.status, status)])
        return status

    def validate_gpu_limit(self, gpu_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(gpu_limit,
                                            plugin.min_gpu_limit,
                                            plugin.max_gpu_limit,
                                            'gpu_limit')
        return gpu_limit

    def validate_number_of_workers(self, number_of_workers):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(number_of_workers,
                                            plugin.min_number_of_workers,
                                            plugin.max_number_of_workers,
                                            'number_of_workers')
        return number_of_workers

    def validate_cpu_limit(self, cpu_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(cpu_limit,
                                            plugin.min_cpu_limit,
                                            plugin.max_cpu_limit,
                                            'cpu_limit')
        return cpu_limit

    def validate_memory_limit(self, memory_limit):
        plugin = self.context['view'].get_object()
        self.validate_value_within_interval(memory_limit,
                                            plugin.min_memory_limit,
                                            plugin.max_memory_limit,
                                            'memory_limit')
        return memory_limit

    @staticmethod
    def validate_value_within_interval(val, min_val, max_val, val_str):
        if val < min_val or val > max_val:
            raise serializers.ValidationError({val_str:
                                                   ["This field value is out of range."]})


class PluginInstanceFileSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    file_resource = ItemLinkField('_get_file_link')
    fname = serializers.FileField(use_url=False)
    feed_id = serializers.ReadOnlyField(source='plugin_inst.feed.id')
    plugin_inst_id = serializers.ReadOnlyField(source='plugin_inst.id')

    class Meta:
        model = PluginInstanceFile
        fields = ('url', 'id', 'fname', 'feed_id', 'plugin_inst_id', 'file_resource',
                  'plugin_inst')

    def _get_file_link(self, obj):
        """
        Custom method to get the hyperlink to the actual file resource.
        """
        fields = self.fields.items()
        # get the current url
        url_field = [v for (k, v) in fields if k == 'url'][0]
        view = url_field.view_name
        request = self.context['request']
        format = self.context['format']
        url = url_field.get_url(obj, view, request, format)
        # return url = current url + file name
        return url + pathlib.Path(obj.fname.name).name


class StrParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = StrParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')


class IntParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = IntParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')


class FloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = FloatParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')


class BoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = BoolParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')


def validate_paths(user, string):
    """
    Custom function to check that a user is allowed to access the provided object storage
    paths.
    """
    path_list = [s.strip() for s in string.split(',')]
    for path in path_list:
        path_parts = pathlib.Path(path).parts
        if path_parts[0] != user.username:
            if len(path_parts) == 1 or path_parts[1] == 'uploads':
                raise serializers.ValidationError(
                    ["You do not have permission to access this path."])
            try:
                # file paths should be of the form <username>/feed_<id>/..
                feed_id = path_parts[1].split('_')[-1]
                feed = Feed.objects.get(pk=feed_id)
            except (ValueError, Feed.DoesNotExist):
                raise serializers.ValidationError(
                    ["This field may not be an invalid path."])
            if user not in feed.owner.all():
                raise serializers.ValidationError(
                    ["You do not have permission to access this path."])
    return ','.join(path_list)


class PathParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = PathParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    def __init__(self, *args, **kwargs):
        """
        Overriden to get the request user as a keyword argument at object creation.
        """
        self.user = kwargs.pop('user')
        super(PathParameterSerializer, self).__init__(*args, **kwargs)

    def validate_value(self, value):
        """
        Overriden to check that the user making the request is allowed to access
        the provided object storage paths (value should be a string of paths separated
        by commas).
        """
        return validate_paths(self.user, value)


class UnextpathParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)

    class Meta:
        model = UnextpathParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    def __init__(self, *args, **kwargs):
        """
        Overriden to get the request user as a keyword argument at object creation.
        """
        self.user = kwargs.pop('user')
        super(UnextpathParameterSerializer, self).__init__(*args, **kwargs)

    def validate_value(self, value):
        """
        Overriden to check that the user making the request is allowed to access
        the provided object storage paths (value should be a string of paths separated
        by commas).
        """
        return validate_paths(self.user, value)


class GenericParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    value = serializers.SerializerMethodField()
    url = ItemLinkField('_get_url')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                      read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = StrParameter
        fields = ('url', 'id', 'param_name', 'value', 'type', 'plugin_inst',
                  'plugin_param')

    def _get_url(self, obj):
        """
        Custom method to get the correct url for the serialized object regardless of
        its type.
        """
        request = self.context['request']
        # here parameter detail view names are assumed to follow a convention
        view_name = TYPES[obj.plugin_param.type] + 'parameter-detail'
        return reverse(view_name, request=request, kwargs={"pk": obj.id})

    def get_value(self, obj):
        """
        Overriden to get the default parameter value regardless of its type.
        """
        return obj.value
        

PARAMETER_SERIALIZERS = {'string': StrParameterSerializer,
                         'integer': IntParameterSerializer,
                         'float': FloatParameterSerializer,
                         'boolean': BoolParameterSerializer,
                         'path': PathParameterSerializer,
                         'unextpath': UnextpathParameterSerializer}
