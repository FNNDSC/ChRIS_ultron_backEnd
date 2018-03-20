
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers
from collectionjson.services import collection_serializer_is_valid

from .models import Plugin, PluginParameter, PluginInstance, StringParameter
from .models import FloatParameter, IntParameter, BoolParameter, PathParameter


class PluginSerializer(serializers.HyperlinkedModelSerializer):
    parameters = serializers.HyperlinkedIdentityField(view_name='pluginparameter-list')
    instances = serializers.HyperlinkedIdentityField(view_name='plugininstance-list')
    
    class Meta:
        model = Plugin
        fields = ('url', 'name', 'dock_image', 'type', 'authors', 'title', 'category',
                  'description', 'documentation', 'license', 'version',
                  'parameters', 'instances')


class PluginParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)    
    class Meta:
        model = PluginParameter
        fields = ('url', 'name', 'type', 'optional', 'default', 'help', 'plugin')


class PluginInstanceSerializer(serializers.HyperlinkedModelSerializer):
    plugin_name = serializers.ReadOnlyField(source='plugin.name')
    owner = serializers.ReadOnlyField(source='owner.username')
    previous = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                   read_only=True)
    previous_id = serializers.ReadOnlyField(source='previous.id')
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    feed = serializers.HyperlinkedRelatedField(view_name='feed-detail',
                                               read_only=True)
    string_param = serializers.HyperlinkedRelatedField(many=True,
                                                       view_name='stringparameter-detail',
                                                       read_only=True)
    int_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='intparameter-detail',
                                                    read_only=True)
    float_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='floatparameter-detail',
                                                    read_only=True)
    bool_param = serializers.HyperlinkedRelatedField(many=True,
                                                    view_name='boolparameter-detail',
                                                    read_only=True)
    path_param = serializers.HyperlinkedRelatedField(many=True,
                                                       view_name='pathparameter-detail',
                                                       read_only=True)

    class Meta:
        model = PluginInstance
        fields = ('url', 'id', 'previous_id', 'plugin_name', 'start_date', 'end_date', 'status',
                  'previous', 'owner', 'feed', 'plugin', 'string_param', 'int_param',
                  'float_param', 'bool_param', 'path_param', 'gpu_limit')

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        return super(PluginInstanceSerializer, self).is_valid(raise_exception=raise_exception)

    def validate_previous(self, previous_id, plugin):
        """
        Custom method to check that an id is provided for previous instance when
        corresponding plugin is of type 'ds'. Then check that the provided id exists in
        the DB.
        """
        previous = None
        if plugin.type=='ds':
            if not previous_id:
                raise serializers.ValidationError(
                    {'detail': "A previous plugin instance id is required"})
            try:
                pk = int(previous_id)
                previous = PluginInstance.objects.get(pk=pk)
            except (ValueError, ObjectDoesNotExist):
                raise serializers.ValidationError(
                    {'detail':
                     "Couldn't find any 'previous' plugin instance with id %s" % previous_id})
        return previous

    def validate_gpu_limit(self, gpu_limit, plugin):
        """
        Validates GPU limits for the requested plugin.
        :param Int gpu_limit: value that was requested.
        :param Plugin plugin: The plugin which needs gpu requests.
        :return: Int 
        """
        if gpu_limit > plugin.max_gpu_limit:
            gpu_limit = plugin.max_gpu_limit
        elif gpu_limit < plugin.min_gpu_limit:
            gpu_limit = plugin.min_gpu_limit
        return gpu_limit


class StringParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)   
    class Meta:
        model = StringParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class IntParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = IntParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class FloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = FloatParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class BoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    
    class Meta:
        model = BoolParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')


class PathParameterSerializer(serializers.HyperlinkedModelSerializer):
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininstance-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                 read_only=True)
    class Meta:
        model = PathParameter
        fields = ('url', 'param_name', 'value', 'plugin_inst', 'plugin_param')
        

PARAMETER_SERIALIZERS={'string': StringParameterSerializer,
                       'integer': IntParameterSerializer,
                       'float': FloatParameterSerializer,
                       'boolean': BoolParameterSerializer,
                       'path': PathParameterSerializer }

