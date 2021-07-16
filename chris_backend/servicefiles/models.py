
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet


REGISTERED_SERVICES = ['PACS']


class Service(models.Model):
    identifier = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.identifier


class ServiceFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, unique=True)
    service = models.ForeignKey(Service, db_index=True, on_delete=models.CASCADE)

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name


class ServiceFileFilter(FilterSet):
    min_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='gte')
    max_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='lte')
    fname = django_filters.CharFilter(field_name='fname', lookup_expr='startswith')
    fname_exact = django_filters.CharFilter(field_name='fname', lookup_expr='exact')
    fname_icontains = django_filters.CharFilter(field_name='fname',
                                                lookup_expr='icontains')
    service_identifier = django_filters.CharFilter(field_name='service__identifier',
                                                   lookup_expr='exact')
    service_id = django_filters.CharFilter(field_name='service_id', lookup_expr='exact')

    class Meta:
        model = ServiceFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'fname', 'fname_exact',
                  'fname_icontains', 'service_identifier', 'service_id']
