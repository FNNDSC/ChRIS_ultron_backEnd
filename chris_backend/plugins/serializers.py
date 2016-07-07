
from rest_framework import serializers

from .models import Plugin, PluginParameter, PluginInstance, StringParameter
from .models import FloatParameter, IntParameter, BoolParameter

class PluginSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Plugin
        fields = ('url', 'id', 'name', 'type')


class PluginParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)    
    class Meta:
        model = PluginParameter
        fields = ('url', 'name', 'type', 'optional', 'plugin')


class PluginInstanceSerializer(serializers.HyperlinkedModelSerializer):
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)   
    class Meta:
        model = PluginInstance
        fields = ('url', 'plugin')


class StringParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininst-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparam-detail',
                                                 read_only=True)
    
    class Meta:
        model = StringParameter
        fields = ('url', 'value', 'plugin_inst', 'plugin_param')


class IntParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininst-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparam-detail',
                                                 read_only=True)
    
    class Meta:
        model = IntParameter
        fields = ('url', 'value', 'plugin_inst', 'plugin_param')


class FloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininst-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparam-detail',
                                                 read_only=True)
    
    class Meta:
        model = FloatParameter
        fields = ('url', 'value', 'plugin_inst', 'plugin_param')


class BoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    plugin_inst = serializers.HyperlinkedRelatedField(view_name='plugininst-detail',
                                                 read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparam-detail',
                                                 read_only=True)
    
    class Meta:
        model = BoolParameter
        fields = ('url', 'value', 'plugin_inst', 'plugin_param')
