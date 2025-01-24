
from django.contrib.auth.models import User, Group
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import UserProxy


class UserSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(min_length=4, max_length=32,
                                     validators=[UniqueValidator(
                                         queryset=User.objects.all())])
    email = serializers.EmailField(required=True,
                                   validators=[UniqueValidator(
                                       queryset=User.objects.all())])
    password = serializers.CharField(min_length=8, max_length=100, write_only=True)
    groups = serializers.HyperlinkedIdentityField(view_name='user-group-list')

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'password', 'is_staff', 'groups')

    def create(self, validated_data):
        """
        Overriden to take care of the password hashing.
        """
        # create user taking care of the password hashing and setup groups and home folder
        return UserProxy.objects.create_user(**validated_data)

    def validate_username(self, username):
        """
        Overriden to check that the username does not contain forward slashes.
        """
        if '/' in username:
            raise serializers.ValidationError(
                ["This field may not contain forward slashes."])
        return username


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    users = serializers.HyperlinkedIdentityField(view_name='group-user-list')

    class Meta:
        model = Group
        fields = ('url', 'id', 'name', 'users')

    def validate_name(self, name):
        """
        Overriden to check that the name does not contain forward slashes.
        """
        if '/' in name:
            raise serializers.ValidationError(
                ["This field may not contain forward slashes."])
        return name



class GroupUserSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.CharField(write_only=True, min_length=4, max_length=32)
    group_id = serializers.ReadOnlyField(source='group.id')
    group_name = serializers.ReadOnlyField(source='group.name')
    user_id = serializers.ReadOnlyField(source='user.id')
    user_username = serializers.ReadOnlyField(source='user.username')
    user_email = serializers.ReadOnlyField(source='user.email')
    group = serializers.HyperlinkedRelatedField(view_name='group-detail', read_only=True)
    user = serializers.HyperlinkedRelatedField(view_name='user-detail', read_only=True)

    class Meta:
        model = User.groups.through
        fields = ('url', 'id', 'group_id', 'group_name', 'user_id', 'user_username',
                  'user_email', 'group', 'user', 'username')

    def validate_username(self, username):
        """
        Custom method to check whether the provided username exists in the DB.
        """
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'username': [f"Couldn't find any user with username '{username}'."]})
        return user
