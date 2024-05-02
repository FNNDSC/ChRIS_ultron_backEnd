
import logging
import io

from django.contrib.auth.models import User, Group
from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.models import ChrisFolder
from core.storage import connect_storage
from userfiles.models import UserFile


logger = logging.getLogger(__name__)


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
        Overriden to take care of the password hashing and create a welcome file
        and a feeds folder for the user in its personal storage space.
        """
        username = validated_data.get('username')
        email = validated_data.get('email')
        password = validated_data.get('password')
        user = User.objects.create_user(username, email, password)

        home_path = f'home/{username}'
        uploads_path = f'{home_path}/uploads'
        feeds_path = f'{home_path}/feeds'

        (uploads_folder, _) = ChrisFolder.objects.get_or_create(path=uploads_path,
                                                                owner=user)
        (feeds_folder, _) = ChrisFolder.objects.get_or_create(path=feeds_path, owner=user)

        storage_manager = connect_storage(settings)
        welcome_file_path = f'{uploads_path}/welcome.txt'
        try:
            with io.StringIO('Welcome to ChRIS!') as f:
                storage_manager.upload_obj(welcome_file_path, f.read(),
                                           content_type='text/plain')
            welcome_file = UserFile(parent_folder=uploads_folder, owner=user)
            welcome_file.fname.name = welcome_file_path
            welcome_file.save()
        except Exception as e:
            logger.error(f'Could not create welcome file in user space, detail: {str(e)}')
        return user

    def validate_username(self, username):
        """
        Overriden to check that the username does not contain forward slashes and is
        not the 'chris' special username.
        """
        if '/' in username:
            raise serializers.ValidationError(
                ["This field may not contain forward slashes."])
        if username == 'chris':
            raise serializers.ValidationError(
                ["Username %s is not available." % username])
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
