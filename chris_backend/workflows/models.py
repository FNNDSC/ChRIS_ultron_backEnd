
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet

from pipelines.models import Pipeline


class Workflow(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    created_plugin_inst_ids = models.CharField(max_length=600)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE,
                                 related_name='workflows')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.created_plugin_inst_ids


class WorkflowFilter(FilterSet):
    pipeline_name = django_filters.CharFilter(field_name='pipeline__name',
                                               lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = Workflow
        fields = ['id', 'pipeline_name', 'owner_username']
