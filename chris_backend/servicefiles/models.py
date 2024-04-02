
import logging

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings

import django_filters
from django_filters.rest_framework import FilterSet

from core.models import ChrisFolder
from core.utils import filter_files_by_n_slashes
from core.storage import connect_storage


logger = logging.getLogger(__name__)


REGISTERED_SERVICES = ['PACS']


class Service(models.Model):
    identifier = models.CharField(max_length=20, unique=True)
    # top folder
    folder = models.OneToOneField(ChrisFolder, on_delete=models.CASCADE,
                                      related_name='service')

    def __str__(self):
        return self.identifier


@receiver(post_delete, sender=Service)
def auto_delete_service_folder_with_service(sender, instance, **kwargs):
    instance.folder.delete()


class ServiceFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, unique=True)
    parent_folder = models.ForeignKey(ChrisFolder, on_delete=models.CASCADE,
                                      related_name='service_files')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name


@receiver(post_delete, sender=ServiceFile)
def auto_delete_file_from_storage(sender, instance, **kwargs):
    storage_path = instance.fname.name
    storage_manager = connect_storage(settings)
    try:
        if storage_manager.obj_exists(storage_path):
            storage_manager.delete_obj(storage_path)
    except Exception as e:
        logger.error('Storage error, detail: %s' % str(e))


class ServiceFileFilter(FilterSet):
    min_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='gte')
    max_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='lte')
    fname = django_filters.CharFilter(field_name='fname', lookup_expr='startswith')
    fname_exact = django_filters.CharFilter(field_name='fname', lookup_expr='exact')
    fname_icontains = django_filters.CharFilter(field_name='fname',
                                                lookup_expr='icontains')
    fname_nslashes = django_filters.CharFilter(method='filter_by_n_slashes')
    service_identifier = django_filters.CharFilter(method='filter_by_service_identifier')

    class Meta:
        model = ServiceFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'fname', 'fname_exact',
                  'fname_icontains', 'fname_nslashes', 'service_identifier']

    def filter_by_service_identifier(self, queryset, name, value):
        """
        Custom method to return the files associated to a specific service identifier.
        """
        try:
            service = Service.objects.get(identifier=value)
        except Service.DoesNotExist:
            return ServiceFile.objects.none()
        return queryset.filter(fname__startswith=service.folder.path)

    def filter_by_n_slashes(self, queryset, name, value):
        """
        Custom method to return the files that have the queried number of slashes in
        their fname property. If the queried number ends in 'u' or 'U' then only one
        file per each last "folder" in the path is returned (useful to efficiently get
        the list of immediate folders under the path).
        """
        return filter_files_by_n_slashes(queryset, value)
