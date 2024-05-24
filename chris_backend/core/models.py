
import logging
import uuid
import io
import os

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import User, Group

import django_filters
from django_filters.rest_framework import FilterSet

from .storage import connect_storage
#from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)


PERMISSION_CHOICES = [("r", "Read"), ("w", "Write")]


def validate_permission(permission):
    """
    Custom function to determine whether a permission value is valid.
    """
    perm_list = [p[0] for p in PERMISSION_CHOICES]
    if permission not in perm_list:
        raise ValueError(f"Invalid permission '{permission}'. Allowed values "
                         f"are: {perm_list}.")
    return permission


class ChrisInstance(models.Model):
    """
    Model class that defines a singleton representing a ChRIS instance.
    """
    creation_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, default="ChRIS instance")
    uuid = models.UUIDField(default=uuid.uuid4)
    job_id_prefix = models.CharField(max_length=100, blank=True, default='chris-jid-')
    description = models.CharField(max_length=600, blank=True)

    class Meta:
        verbose_name = 'ChRIS instance'
        verbose_name_plural = 'ChRIS instance'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        count = ChrisInstance.objects.all().count()
        if count > 0:
            self.id = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        try:
            obj = cls.objects.get(id=1)
        except cls.DoesNotExist:
            obj = cls()
            obj.save()
        return obj


class ChrisFolder(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=1024, unique=True)  # folder's path
    public = models.BooleanField(blank=True, default=False, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                               related_name='children')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    shared_groups = models.ManyToManyField(Group, related_name='shared_folders',
                                           through='FolderGroupPermission')
    shared_users = models.ManyToManyField(User, related_name='shared_folders',
                                          through='FolderUserPermission')

    class Meta:
        ordering = ('-path',)

    def __str__(self):
        return self.path

    def save(self, *args, **kwargs):
        """
        Overriden to recursively create parent folders when first saving the folder
        to the DB.
        """
        if self.path:
            parent_path = os.path.dirname(self.path)
            try:
                parent = ChrisFolder.objects.get(path=parent_path)
            except ChrisFolder.DoesNotExist:
                parent = ChrisFolder(path=parent_path, owner=self.owner)
                parent.save()  # recursive call
            self.parent = parent

        if self.path in ('', 'home') or self.path.startswith(('PIPELINES', 'SERVICES')):
            self.owner = User.objects.get(username='chris')
        super(ChrisFolder, self).save(*args, **kwargs)

    def get_descendants(self):
        """
        Custom method to return all the folders that are a descendant of this
        folder.
        """
        path = self.path.rstrip('/') + '/'
        return list(ChrisFolder.objects.filter(path__startswith=path))

    def has_group_permission(self, group, permission):
        """
        Custom method to determine whether a group has been granted a permission
        to access the folder.
        """
        p = validate_permission(permission)
        qs = FolderGroupPermission.objects.filter(group=group, folder=self, permission=p)
        return qs.exists()

    def has_user_permission(self, user, permission):
        """
        Custom method to determine whether a user has been granted a permission
        to access the folder.
        """
        p = validate_permission(permission)
        lookup = models.Q(user=user) | models.Q(user__groups__shared_folders=self)
        qs = FolderUserPermission.objects.filter(folder=self, permission=p).filter(lookup)
        return qs.exists()

    def grant_group_permission(self, group, permission):
        """
        Custom method to grant a group a permission to access the folder and all its
        descendant folders, link files and files.
        """
        FolderGroupPermission.objects.create(folder=self, group=group,
                                             permission=permission)

    def remove_group_permission(self, group, permission):
        """
        Custom method to remove a group's permission to access the folder and all its
        descendant folders, link files and files.
        """
        FolderGroupPermission.objects.get(folder=self, group=group,
                                          permission=permission).delete()


    def grant_user_permission(self, user, permission):
        """
        Custom method to grant a user a permission to access the folder and all its
        descendant folders, link files and files.
        """
        FolderUserPermission.objects.create(folder=self, user=user, permission=permission)

    def remove_user_permission(self, user, permission):
        """
        Custom method to remove a user's permission to access the folder and all its
        descendant folders, link files and files.
        """
        FolderUserPermission.objects.get(folder=self, user=user,
                                         permission=permission).delete()

    def grant_public_access(self):
        """
        Custom method to grant public access to the folder and all its descendant folders,
        link files and files.
        """
        self._update_public_access(True)

    def remove_public_access(self):
        """
        Custom method to remove public access to the folder and all its descendant
        folders, link files and files.
        """
        self._update_public_access(False)

    def _update_public_access(self, public_tf):
        """
        Internal method to update public access to the folder and all its descendant
        folders, link files and files.
        """
        path = self.path.rstrip('/') + '/'

        folders = list(ChrisFolder.objects.filter(path__startswith=path))
        for folder in folders:
            folder.public = public_tf
        ChrisFolder.objects.bulk_update(folders, ['public'])

        files = list(ChrisFile.objects.filter(path__startswith=path))
        for f in files:
            f.public = public_tf
        ChrisFile.objects.bulk_update(files, ['public'])

        link_files = list(ChrisLinkFile.objects.filter(path__startswith=path))
        for lf in link_files:
            lf.public = public_tf
        ChrisLinkFile.objects.bulk_update(link_files, ['public'])


class ChrisFolderFilter(FilterSet):
    path = django_filters.CharFilter(field_name='path')

    class Meta:
        model = ChrisFolder
        fields = ['id', 'path']


class FolderGroupPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('folder', 'group',)

    def __str__(self):
        return self.permission

    def save(self, *args, **kwargs):
        """
        Overriden to grant the group permission to all the folders, files and link
        files within the folder.
        """
        super(FolderGroupPermission, self).save(*args, **kwargs)

        group = self.group
        permission = self.permission
        path = self.folder.path.rstrip('/') + '/'

        folders = ChrisFolder.objects.filter(path__startswith=path)
        objs = []
        for folder in folders:
            perm = FolderGroupPermission(folder=folder, group=group,
                                         permission=permission)
            objs.append(perm)
        FolderGroupPermission.objects.bulk_create(objs, update_conflicts=True,
                                                  update_fields=['permission'],
                                                  unique_fields=['folder_id', 'group_id'])

        files = ChrisFile.objects.filter(fname__startswith=path)
        objs = []
        for f in files:
            perm = FileGroupPermission(file=f, group=group, permission=permission)
            objs.append(perm)
        FileGroupPermission.objects.bulk_create(objs, update_conflicts=True,
                                                update_fields=['permission'],
                                                unique_fields=['file_id', 'group_id'])

        link_files = ChrisLinkFile.objects.filter(fname__startswith=path)
        objs = []
        for lf in link_files:
            perm = LinkFileGroupPermission(link_file=lf, group=group,
                                           permission=permission)
            objs.append(perm)
        LinkFileGroupPermission.objects.bulk_create(objs, update_conflicts=True,
                                                    update_fields=['permission'],
                                                    unique_fields=['link_file_id',
                                                                   'group_id'])

    def delete(self, *args, **kwargs):
        """
        Overriden to remove the group permission to all the folders, files and
        link files within the folder.
        """
        super(FolderGroupPermission, self).delete(*args, **kwargs)

        group = self.group
        permission = self.permission
        path = self.folder.path.rstrip('/') + '/'

        FolderGroupPermission.objects.filter(folder__path__startswith=path, group=group,
                                             permission=permission).delete()

        FileGroupPermission.objects.filter(file__fname__startswith=path, group=group,
                                           permission=permission).delete()

        LinkFileGroupPermission.objects.filter(link_file__fname__startswith=path,
                                               group=group,
                                               permission=permission).delete()


class FolderGroupPermissionFilter(FilterSet):
    group_name = django_filters.CharFilter(field_name='group__name', lookup_expr='exact')

    class Meta:
        model = FolderGroupPermission
        fields = ['id', 'group_name']


class FolderUserPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('folder', 'user',)

    def __str__(self):
        return self.permission

    def save(self, *args, **kwargs):
        """
        Overriden to grant the user permission to all the folders, files and link
        files within the folder.
        """
        super(FolderUserPermission, self).save(*args, **kwargs)

        user = self.user
        permission = self.permission
        path = self.folder.path.rstrip('/') + '/'

        folders = ChrisFolder.objects.filter(path__startswith=path)
        objs = []
        for folder in folders:
            perm = FolderUserPermission(folder=folder, user=user, permission=permission)
            objs.append(perm)
        FolderUserPermission.objects.bulk_create(objs, update_conflicts=True,
                                                 update_fields=['permission'],
                                                 unique_fields=['folder_id', 'group_id'])

        files = ChrisFile.objects.filter(path__startswith=path)
        objs = []
        for f in files:
            perm = FileUserPermission(file=f, user=user, permission=permission)
            objs.append(perm)
        FileUserPermission.objects.bulk_create(objs, update_conflicts=True,
                                               update_fields=['permission'],
                                               unique_fields=['file_id', 'group_id'])

        link_files = ChrisLinkFile.objects.filter(path__startswith=path)
        objs = []
        for lf in link_files:
            perm = LinkFileUserPermission(link_file=lf, user=user, permission=permission)
            objs.append(perm)
        LinkFileUserPermission.objects.bulk_create(objs, update_conflicts=True,
                                                   update_fields=['permission'],
                                                   unique_fields=['link_file_id',
                                                                  'group_id'])

    def delete(self, *args, **kwargs):
        """
        Overriden to remove the user permission to all the folders, files and
        link files within the folder.
        """
        super(FolderUserPermission, self).delete(*args, **kwargs)

        user = self.user
        permission = self.permission
        path = self.folder.path.rstrip('/') + '/'

        FolderUserPermission.objects.filter(folder__path__startswith=path, user=user,
                                             permission=permission).delete()

        FileUserPermission.objects.filter(file__fname__startswith=path, user=user,
                                          permission=permission).delete()

        LinkFileUserPermission.objects.filter(link_file__fname__startswith=path,
                                              user=user, permission=permission).delete()


class FolderUserPermissionFilter(FilterSet):
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='exact')

    class Meta:
        model = FolderUserPermission
        fields = ['id', 'username']


class ChrisFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=1024, unique=True)
    public = models.BooleanField(blank=True, default=False, db_index=True)
    parent_folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE,
                                      related_name='chris_files')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    shared_groups = models.ManyToManyField(Group, related_name='shared_files',
                                           through='FileGroupPermission')
    shared_users = models.ManyToManyField(User, related_name='shared_files',
                                          through='FileUserPermission')

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name

    def has_group_permission(self, group, permission):
        """
        Custom method to determine whether a group has been granted permission to access
        the file.
        """
        p = validate_permission(permission)
        qs = FileGroupPermission.objects.filter(group=group, file=self, permission=p)
        return qs.exists()

    def has_user_permission(self, user, permission):
        """
        Custom method to determine whether a user has been granted permission to access
        the file.
        """
        p = validate_permission(permission)
        lookup = models.Q(user=user) | models.Q(user__groups__shared_files=self)
        qs = FileUserPermission.objects.filter(file=self, permission=p).filter(lookup)
        return qs.exists()

    def grant_group_permission(self, group, permission):
        """
        Custom method to grant a group a permission to access the file.
        """
        FileGroupPermission.objects.create(folder=self, group=group,
                                           permission=permission)

    def remove_group_permission(self, group, permission):
        """
        Custom method to remove a group's permission to access the file.
        """
        FileGroupPermission.objects.get(folder=self, group=group,
                                        permission=permission).delete()

    def grant_user_permission(self, user, permission):
        """
        Custom method to grant a user a permission to access the file.
        """
        FileUserPermission.objects.create(folder=self, user=user, permission=permission)

    def remove_user_permission(self, user, permission):
        """
        Custom method to remove a user's permission to access the file.
        """
        FileUserPermission.objects.get(folder=self, user=user,
                                       permission=permission).delete()

    def grant_public_access(self):
        """
        Custom method to grant public access to the file.
        """
        self.public = True
        self.save()

    def remove_public_access(self):
        """
        Custom method to remove public access to the file.
        """
        self.public = False
        self.save()

    @classmethod
    def get_base_queryset(cls):
        """
        Custom method to return a queryset that is only comprised by all files
        registered in storage.
        """
        return cls.objects.all()


@receiver(post_delete, sender=ChrisFile)
def auto_delete_file_from_storage(sender, instance, **kwargs):
    storage_path = instance.fname.name
    storage_manager = connect_storage(settings)
    try:
        if storage_manager.obj_exists(storage_path):
            storage_manager.delete_obj(storage_path)
    except Exception as e:
        logger.error('Storage error, detail: %s' % str(e))


class FileGroupPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    file = models.ForeignKey(ChrisFile, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('file', 'group',)

    def __str__(self):
        return self.permission


class FileGroupPermissionFilter(FilterSet):
    group_name = django_filters.CharFilter(field_name='group__name', lookup_expr='exact')

    class Meta:
        model = FileGroupPermission
        fields = ['id', 'group_name']


class FileUserPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    file = models.ForeignKey(ChrisFile, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('file', 'user',)

    def __str__(self):
        return self.permission


class FileUserPermissionFilter(FilterSet):
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='exact')

    class Meta:
        model = FileUserPermission
        fields = ['id', 'username']


class ChrisLinkFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=1024, db_index=True)  # pointed path
    fname = models.FileField(max_length=1024, unique=True)
    public = models.BooleanField(blank=True, default=False, db_index=True)
    parent_folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE,
                                      related_name='chris_link_files')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    shared_groups = models.ManyToManyField(Group, related_name='shared_link_files',
                                           through='LinkFileGroupPermission')
    shared_users = models.ManyToManyField(User, related_name='shared_link_files',
                                          through='LinkFileUserPermission')

    def __str__(self):
        return self.fname.name

    def save(self, *args, **kwargs):
        """
        Overriden to create and save the associated link file when the link is
        saved.
        """
        path = self.path  # pointed path
        name = kwargs.pop('name')  # must provide a name for the link
        link_file_path = os.path.join(self.parent_folder.path, f'{name}.chrislink')
        link_file_contents = f'{path}'

        storage_manager = connect_storage(settings)

        with io.StringIO(link_file_contents) as f:
            if storage_manager.obj_exists(link_file_path):
                storage_manager.delete_obj(link_file_path)
            storage_manager.upload_obj(link_file_path, f.read(),
                                       content_type='text/plain')
        self.fname.name = link_file_path
        super(ChrisLinkFile, self).save(*args, **kwargs)

    def has_group_permission(self, group, permission):
        """
        Custom method to determine whether a group has been granted permission to access
        the link file.
        """
        p = validate_permission(permission)
        return LinkFileGroupPermission.objects.filter(group=group, link_file=self,
                                                      permission=p).exists()

    def has_user_permission(self, user, permission):
        """
        Custom method to determine whether a user has been granted permission to access
        the link file.
        """
        p = validate_permission(permission)
        lookup = models.Q(user=user) | models.Q(user__groups__shared_link_files=self)
        return LinkFileUserPermission.objects.filter(link_file=self,
                                                     permission=p).filter(lookup).exists()

    def grant_group_permission(self, group, permission):
        """
        Custom method to grant a group a permission to access the link file.
        """
        LinkFileGroupPermission.objects.create(folder=self, group=group,
                                               permission=permission)

    def remove_group_permission(self, group, permission):
        """
        Custom method to remove a group's permission to access the link file.
        """
        LinkFileGroupPermission.objects.get(folder=self, group=group,
                                            permission=permission).delete()

    def grant_user_permission(self, user, permission):
        """
        Custom method to grant a user a permission to access the link file.
        """
        LinkFileUserPermission.objects.create(folder=self, user=user,
                                              permission=permission)

    def remove_user_permission(self, user, permission):
        """
        Custom method to remove a user's permission to access the link file.
        """
        LinkFileUserPermission.objects.get(folder=self, user=user,
                                           permission=permission).delete()

    def grant_public_access(self):
        """
        Custom method to grant public access to the file.
        """
        self.public = True
        self.save()

    def remove_public_access(self):
        """
        Custom method to remove public access to the file.
        """
        self.public = False
        self.save()


@receiver(post_delete, sender=ChrisLinkFile)
def auto_delete_file_from_storage(sender, instance, **kwargs):
    storage_path = instance.fname.name
    storage_manager = connect_storage(settings)
    try:
        if storage_manager.obj_exists(storage_path):
            storage_manager.delete_obj(storage_path)
    except Exception as e:
        logger.error('Storage error, detail: %s' % str(e))


class LinkFileGroupPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    link_file = models.ForeignKey(ChrisLinkFile, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('link_file', 'group',)

    def __str__(self):
        return self.permission


class LinkFileGroupPermissionFilter(FilterSet):
    group_name = django_filters.CharFilter(field_name='group__name', lookup_expr='exact')

    class Meta:
        model = LinkFileGroupPermission
        fields = ['id', 'group_name']


class LinkFileUserPermission(models.Model):
    permission = models.CharField(choices=PERMISSION_CHOICES, default='r', max_length=1)
    link_file = models.ForeignKey(ChrisLinkFile, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('link_file', 'user',)

    def __str__(self):
        return self.permission


class LinkFileUserPermissionFilter(FilterSet):
    username = django_filters.CharFilter(field_name='user__username', lookup_expr='exact')

    class Meta:
        model = LinkFileUserPermission
        fields = ['id', 'username']


class FileDownloadToken(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    token = models.CharField(max_length=300, db_index=True)

    class Meta:
        ordering = ('owner', 'creation_date')

    def __str__(self):
        return str(self.token)


class FileDownloadTokenFilter(FilterSet):

    class Meta:
        model = FileDownloadToken
        fields = ['id']
