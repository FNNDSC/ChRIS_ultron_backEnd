
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet


class PACS(models.Model):
    identifier = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.identifier


class PACSFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, unique=True)
    PatientID = models.CharField(max_length=15, db_index=True)
    PatientName = models.CharField(max_length=30)
    StudyInstanceUID = models.CharField(max_length=50, db_index=True)
    StudyDescription = models.CharField(max_length=200, blank=True)
    SeriesInstanceUID = models.CharField(max_length=50, db_index=True)
    SeriesDescription = models.CharField(max_length=200, blank=True)
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
    fname = django_filters.CharFilter(field_name='fname', lookup_expr='startswith')
    fname_exact = django_filters.CharFilter(field_name='fname', lookup_expr='exact')
    PatientID = django_filters.CharFilter(field_name='PatientID', lookup_expr='exact')
    PatientName = django_filters.CharFilter(field_name='PatientName',
                                            lookup_expr='icontains')
    StudyInstanceUID = django_filters.CharFilter(field_name='StudyInstanceUID',
                                                 lookup_expr='exact')
    StudyDescription = django_filters.CharFilter(field_name='StudyDescription',
                                                 lookup_expr='icontains')

    SeriesInstanceUID = django_filters.CharFilter(field_name='SeriesInstanceUID',
                                                 lookup_expr='exact')
    SeriesDescription = django_filters.CharFilter(field_name='SeriesDescription',
                                                 lookup_expr='icontains')
    pacs_identifier = django_filters.CharFilter(field_name='pacs__identifier',
                                                lookup_expr='exact')

    class Meta:
        model = PACSFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'fname', 'fname_exact',
                  'PatientID', 'PatientName', 'StudyInstanceUID', 'StudyDescription',
                  'SeriesInstanceUID', 'SeriesDescription', 'pacs_identifier']
