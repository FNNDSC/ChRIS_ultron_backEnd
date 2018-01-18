
from django.contrib.auth.models import User

from rest_framework import serializers
from rest_framework.validators import UniqueValidator


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)
    username = serializers.CharField(max_length=32,
                                     validators=[UniqueValidator(queryset=User.objects.all())])
    password = serializers.CharField(min_length=6, max_length=100, write_only=True)

    def create(self, validated_data):
        user = User(username=validated_data['username'])
        user.set_password(validated_data['password'])
        user.save()
        return user

    def is_valid(self, raise_exception=False):
        """
        Overriden to generate a properly formatted message for validation errors
        """
        valid = super(UserSerializer, self).is_valid()
        if raise_exception and not valid:
            raise serializers.ValidationError({'detail': str(self._errors)})
        return valid

    class Meta:
        model = User
        fields = ('url', 'username', 'feed', 'password')