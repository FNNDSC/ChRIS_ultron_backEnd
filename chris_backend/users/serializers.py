
import logging
import io

from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.models import ChrisFolder
from core.storage import connect_storage
from userfiles.models import UserFile


logger = logging.getLogger(__name__)


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
        fields = ('url', 'id', 'username', 'email', 'password', 'is_staff', 'feed')

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
        (home_folder, _) = ChrisFolder.objects.get_or_create(path=home_path, owner=user)
        (feeds_folder, _) = ChrisFolder.objects.get_or_create(path=f'{home_path}/feeds',
                                                              owner=user)
        storage_manager = connect_storage(settings)
        welcome_file_path = f'{home_path}/welcome.txt'
        try:
            with io.StringIO('Welcome to ChRIS!') as f:
                storage_manager.upload_obj(welcome_file_path, f.read(),
                                           content_type='text/plain')
            welcome_file = UserFile(parent_folder=home_folder, owner=user)
            welcome_file.fname.name = welcome_file_path
            welcome_file.save()
        except Exception as e:
            logger.error('Could not create welcome file in user space, detail: %s' %
                         str(e))
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
