
import logging
import uuid
import io
import os

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import User

import django_filters
from django_filters.rest_framework import FilterSet

from .storage import connect_storage
#from django.core.files.base import ContentFile


logger = logging.getLogger(__name__)


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
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                               related_name='children')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

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
        descendants = []
        queue = [self]
        while len(queue) > 0:
            visited = queue.pop()
            queue.extend(list(visited.children.all()))
            descendants.append(visited)
        return descendants


class ChrisFolderFilter(FilterSet):
    path = django_filters.CharFilter(field_name='path')

    class Meta:
        model = ChrisFolder
        fields = ['id', 'path']


class ChrisLinkFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=1024, db_index=True)  # pointed path
    fname = models.FileField(max_length=1024, unique=True)
    parent_folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE,
                                      related_name='chris_link_files')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

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


@receiver(post_delete, sender=ChrisLinkFile)
def auto_delete_file_from_storage(sender, instance, **kwargs):
    storage_path = instance.fname.name
    storage_manager = connect_storage(settings)
    try:
        if storage_manager.obj_exists(storage_path):
            storage_manager.delete_obj(storage_path)
    except Exception as e:
        logger.error('Storage error, detail: %s' % str(e))


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
