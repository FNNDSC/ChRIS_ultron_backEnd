
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet


class PACS(models.Model):
    identifier = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.identifier


class PACSFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=500)
    mrn = models.CharField(max_length=10)
    patient_name = models.CharField(max_length=15)
    study = models.CharField(max_length=150)
    series = models.CharField(max_length=150)
    name = models.CharField(max_length=175)
    pacs = models.ForeignKey(PACS, on_delete=models.CASCADE)

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
    pacs_identifier = django_filters.CharFilter(field_name='pacs__identifier',
                                                lookup_expr='exact')
    pacs_id = django_filters.CharFilter(field_name='pacs_id', lookup_expr='exact')

    class Meta:
        model = PACSFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'mrn', 'mrn_exact',
                  'patient_name', 'study', 'series', 'name', 'pacs_identifier', 'pacs_id']
