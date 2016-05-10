from django.contrib.auth.models import User

from rest_framework import serializers

from .models import Feed

from core.renderers import LinkField


class FeedSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Feed
        fields = ('url', 'owner', 'name')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail', read_only=True)

    class Meta:
        model = User
        fields = ('url', 'username', 'feed')
        

