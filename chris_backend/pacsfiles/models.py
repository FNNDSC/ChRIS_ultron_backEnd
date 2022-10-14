
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet

from core.utils import filter_files_by_n_slashes


class PACS(models.Model):
    identifier = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.identifier


class PACSFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=512, unique=True)
    PatientID = models.CharField(max_length=100, db_index=True)
    PatientName = models.CharField(max_length=150, blank=True)
    PatientBirthDate = models.DateField(blank=True, null=True)
    PatientAge = models.IntegerField(blank=True, null=True)
    PatientSex = models.CharField(max_length=2, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
                                  blank=True)
    StudyDate = models.DateField(db_index=True)
    AccessionNumber = models.CharField(max_length=100, blank=True, db_index=True)
    Modality = models.CharField(max_length=15, blank=True)
    ProtocolName = models.CharField(max_length=64, blank=True)
    StudyInstanceUID = models.CharField(max_length=100)
    StudyDescription = models.CharField(max_length=400, blank=True)
    SeriesInstanceUID = models.CharField(max_length=100)
    SeriesDescription = models.CharField(max_length=400, blank=True)
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
    fname_icontains_topdir_unique = django_filters.CharFilter(
        method='filter_by_icontains_topdir_unique')
    fname_nslashes = django_filters.CharFilter(method='filter_by_n_slashes')
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
                  'fname_icontains', 'fname_icontains_topdir_unique', 'fname_nslashes',
                  'PatientID', 'PatientName', 'PatientSex', 'PatientAge',
                  'min_PatientAge', 'max_PatientAge', 'PatientBirthDate', 'StudyDate',
                  'AccessionNumber', 'ProtocolName', 'StudyInstanceUID',
                  'StudyDescription', 'SeriesInstanceUID', 'SeriesDescription',
                  'pacs_identifier']

    def filter_by_n_slashes(self, queryset, name, value):
        """
        Custom method to return the files that have the queried number of slashes in
        their fname property. If the queried number ends in 'u' or 'U' then only one
        file per each last "folder" in the path is returned (useful to efficiently get
        the list of immediate folders under the path).
        """
        return filter_files_by_n_slashes(queryset, value)

    def filter_by_icontains_topdir_unique(self, queryset, name, value):
        """
        Custom method to return the files containing all the substrings from the queried
        string (which in turn represents a white-space-separated list of query strings)
        case insensitive anywhere in their fname. But only one file is returned per top
        level directory under SERVICES/PACS/pacs_name. This is useful to efficiently
        determine the top level directories containing a file that matches the query.
        """
        # assume value is a string representing a white-space-separated list
        # of query strings
        value_l = value.split()
        qs = queryset
        for val in value_l:
            qs = qs.filter(fname__icontains=val)
        ids = []
        hash_set = set()
        for f in qs.all():
            path = f.fname.name
            l = path.split('/', 4)  # only split 4 times
            top_dir = '/'.join(l[:4])
            if top_dir not in hash_set:
                ids.append(f.id)
                hash_set.add(top_dir)
        return qs.filter(pk__in=ids)
