
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet

from pipelines.models import Pipeline
from plugins.fields import CPUField, MemoryField


class PipelineInstance(models.Model):
    title = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=800, blank=True)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE,
                                 related_name='instances')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    cpu_limit = CPUField(null=True)
    memory_limit = MemoryField(null=True)
    number_of_workers = models.IntegerField(null=True)
    gpu_limit = models.IntegerField(null=True)

    class Meta:
        ordering = ('pipeline',)

    def __str__(self):
        return self.title


class PipelineInstanceFilter(FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    pipeline_name = django_filters.CharFilter(field_name='pipeline__name',
                                               lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = PipelineInstance
        fields = ['id', 'title', 'description', 'pipeline_name', 'owner_username']
