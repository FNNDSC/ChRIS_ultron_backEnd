
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.validators import UniqueValidator


class UserSerializer(serializers.HyperlinkedModelSerializer):
    feed = serializers.HyperlinkedRelatedField(many=True, view_name='feed-detail',
                                               read_only=True)
    username = serializers.CharField(min_length=4, max_length=32,
                                     validators=[UniqueValidator(
                                         queryset=User.objects.all())])
    email = serializers.EmailField(required=True,
                                   validators=[UniqueValidator(
                                       queryset=User.objects.all())])
    password = serializers.CharField(min_length=8, max_length=100, write_only=True)

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'password', 'feed')

    def create(self, validated_data):
        """
        Overriden to take care of the password hashing.
        """
        username = validated_data.get('username')
        email = validated_data.get('email')
        password = validated_data.get('password')
        return User.objects.create_user(username, email, password)

    def validate_username(self, username):
        """
        Overriden to check that the username does not contain forward slashes.
        """
        if '/' in username:
            raise serializers.ValidationError(
                ["This field may not contain forward slashes."])
        return username
