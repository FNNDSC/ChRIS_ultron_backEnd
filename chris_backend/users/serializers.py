
from django.contrib.auth.models import User

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from collectionjson.services import collection_serializer_is_valid


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)
    username = serializers.CharField(max_length=32,
                                     validators=[UniqueValidator(queryset=User.objects.all())])
    email = serializers.EmailField(required=True,
                                   validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(min_length=6, max_length=100, write_only=True)

    def create(self, validated_data):
        """
        Overriden to save hashed password to the DB.
        """
        user = User(username=validated_data['username'], email=validated_data['email'])
        user.set_password(validated_data['password'])
        user.save()
        return user

    @collection_serializer_is_valid
    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors.
        """
        return super(UserSerializer, self).is_valid(raise_exception=raise_exception)

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'password', 'feed')