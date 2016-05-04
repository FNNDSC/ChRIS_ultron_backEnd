from django.contrib.auth.models import User

from rest_framework import serializers

from .models import Feed


class FeedSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Feed
        fields = ('url', 'owner', 'name')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feeds = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail', read_only=True)

    class Meta:
        model = User
        fields = ('url', 'username', 'feeds')
