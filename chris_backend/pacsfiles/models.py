
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
    PatientID = models.CharField(max_length=150, db_index=True)
    PatientName = models.CharField(max_length=150, blank=True)
    PatientBirthDate = models.DateField(blank=True, null=True)
    PatientAge = models.IntegerField(blank=True, null=True)
    PatientSex = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female')],
                                  blank=True)
    StudyDate = models.DateField(db_index=True)
    Modality = models.CharField(max_length=15, blank=True)
    ProtocolName = models.CharField(max_length=64, blank=True)
    StudyInstanceUID = models.CharField(max_length=150)
    StudyDescription = models.CharField(max_length=500, blank=True)
    SeriesInstanceUID = models.CharField(max_length=150)
    SeriesDescription = models.CharField(max_length=500, blank=True)
    pacs = models.ForeignKey(PACS, on_delete=models.CASCADE)

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name


class PACSFileFilter(FilterSet):
    min_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='gte')
    max_creation_date = django_filters.IsoDateTimeFilter(field_name='creation_date',
                                                         lookup_expr='lte')
    fname = django_filters.CharFilter(field_name='fname', lookup_expr='startswith')
    fname_exact = django_filters.CharFilter(field_name='fname', lookup_expr='exact')
    fname_icontains = django_filters.CharFilter(field_name='fname',
                                                lookup_expr='icontains')
    PatientName = django_filters.CharFilter(field_name='PatientName',
                                            lookup_expr='icontains')
    ProtocolName = django_filters.CharFilter(field_name='ProtocolName',
                                             lookup_expr='icontains')
    StudyDescription = django_filters.CharFilter(field_name='StudyDescription',
                                                 lookup_expr='icontains')
    SeriesDescription = django_filters.CharFilter(field_name='SeriesDescription',
                                                 lookup_expr='icontains')
    pacs_identifier = django_filters.CharFilter(field_name='pacs__identifier',
                                                lookup_expr='exact')
    min_PatientAge = django_filters.NumberFilter(field_name='PatientAge',
                                                 lookup_expr='gte')
    max_PatientAge = django_filters.NumberFilter(field_name='PatientAge',
                                                 lookup_expr='lte')

    class Meta:
        model = PACSFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'fname', 'fname_exact',
                  'fname_icontains', 'PatientID', 'PatientName', 'PatientSex',
                  'PatientAge', 'min_PatientAge', 'max_PatientAge', 'PatientBirthDate',
                  'StudyDate', 'ProtocolName', 'StudyInstanceUID', 'StudyDescription',
                  'SeriesInstanceUID', 'SeriesDescription', 'pacs_identifier']
