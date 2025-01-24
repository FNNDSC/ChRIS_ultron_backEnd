
import logging
import io

from django.contrib.auth.models import User, Group
from django_auth_ldap.backend import LDAPBackend
from django.conf import settings

import django_filters
from django_filters.rest_framework import FilterSet

from core.models import ChrisFolder, ChrisLinkFile
from core.storage import connect_storage
from userfiles.models import UserFile


logger = logging.getLogger(__name__)


class GroupFilter(FilterSet):
    name_icontains = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Group
        fields = ['id', 'name', 'name_icontains']


class GroupUserFilter(FilterSet):
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='exact')

    class Meta:
        model = User.groups.through
        fields = ['id', 'username']


class UserProxy(User):

    class Meta:
        ordering = ('-username',)
        proxy = True
        app_label = 'auth'

    def save(self, *args, **kwargs):
        """
        Overriden to assign the user's default groups and setup its home folder the
        first time it's saved to the DB.
        """
        first_save = False if self.pk else True
        super(UserProxy, self).save(*args, **kwargs)

        if first_save:  # first time the model is being saved
            # retrieve predefined groups
            try:
                all_grp = Group.objects.get(name='all_users')
                pacs_grp = Group.objects.get(name='pacs_users')
            except Group.DoesNotExist:
                logger.error(
                    f"Error while retrieving groups: ['all_users', 'pacs_users']")
                raise

            # assign predefined groups
            user = self
            user.groups.set([all_grp, pacs_grp])

            home_path = f'home/{user.username}'
            uploads_path = f'{home_path}/uploads'
            feeds_path = f'{home_path}/feeds'

            # create predefined folders under the home directory
            (uploads_folder, _) = ChrisFolder.objects.get_or_create(path=uploads_path,
                                                                    owner=user)
            (feeds_folder, _) = ChrisFolder.objects.get_or_create(path=feeds_path,
                                                                  owner=user)

            # create predefined link files under the home directory
            link_file = ChrisLinkFile(path='PUBLIC', owner=user,
                                      parent_folder=uploads_folder.parent)
            link_file.save(name='public')
            link_file = ChrisLinkFile(path='SHARED', owner=user,
                                      parent_folder=uploads_folder.parent)
            link_file.save(name='shared')

            # create a welcome.txt file inside the uploads folder
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
                logger.error(
                    f'Could not create welcome file in user space, detail: {str(e)}')


class CustomLDAPBackend(LDAPBackend):
    def get_user_model(self):
        return UserProxy
