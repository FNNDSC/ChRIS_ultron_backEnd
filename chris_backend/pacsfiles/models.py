
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet


class PACSFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=500, blank=True)
    mrn = models.CharField(max_length=10, blank=True)
    patient_name = models.CharField(max_length=15, blank=True)
    study = models.CharField(max_length=150, blank=True)
    series = models.CharField(max_length=150, blank=True)
    name = models.CharField(max_length=175, blank=True)

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name


class PACSFileFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                 lookup_expr='lte')

    mrn = django_filters.CharFilter(field_name='mrn', lookup_expr='icontains')
    mrn_exact = django_filters.CharFilter(field_name='mrn', lookup_expr='exact')
    patient_name = django_filters.CharFilter(field_name='patient_name',
                                             lookup_expr='icontains')
    study = django_filters.CharFilter(field_name='study', lookup_expr='icontains')
    series = django_filters.CharFilter(field_name='series', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = PACSFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'mrn', 'mrn_exact',
                  'patient_name', 'study', 'series', 'name']
