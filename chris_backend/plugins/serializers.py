
from rest_framework import serializers

from .models import Plugin


class PluginSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Plugin
        fields = ('url', 'name', 'type')
