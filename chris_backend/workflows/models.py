
from django.db import models
import django_filters
from django_filters.rest_framework import FilterSet

from pipelines.models import Pipeline


class Workflow(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE,
                                 related_name='workflows')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.title

    def get_plugin_instances_status_count(self, status):
        """
        Custom method to get the number of associated plugin instances with a given
        execution status.
        """
        return self.plugin_instances.filter(status=status).count()


class WorkflowFilter(FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    pipeline_name = django_filters.CharFilter(field_name='pipeline__name',
                                               lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = Workflow
        fields = ['id', 'title', 'pipeline_name', 'owner_username']
