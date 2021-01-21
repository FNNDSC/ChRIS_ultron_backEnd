
from rest_framework import serializers

from .models import ChrisInstance


class ChrisInstanceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = ChrisInstance
        fields = ('url', 'id', 'creation_date', 'name', 'uuid', 'job_id_prefix',
                  'description')
