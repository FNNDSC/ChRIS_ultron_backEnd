
from django.db import models
from django.db.models import Count, Case, When, IntegerField
import django_filters
from django_filters.rest_framework import FilterSet

from pipelines.models import Pipeline
from plugininstances.enums import STATUS_CHOICES


# Mapping of (annotation field name) -> (plugin-instance status string).
# Source of truth for valid status strings is plugininstances.enums.STATUS_CHOICES;
# the field-name side of the pair is workflow-specific (e.g. 'registeringFiles' is
# surfaced as 'registering_jobs', 'finishedSuccessfully' as 'finished_jobs').
JOBS_STATUS_FIELDS = (
    ('created_jobs',     'created'),
    ('waiting_jobs',     'waiting'),
    ('copying_jobs',     'copying'),
    ('scheduled_jobs',   'scheduled'),
    ('started_jobs',     'started'),
    ('uploading_jobs',   'uploading'),
    ('registering_jobs', 'registeringFiles'),
    ('finished_jobs',    'finishedSuccessfully'),
    ('errored_jobs',     'finishedWithError'),
    ('cancelled_jobs',   'cancelled'),
)
assert {s for _, s in JOBS_STATUS_FIELDS} <= {c[0] for c in STATUS_CHOICES}, (
    'workflows.JOBS_STATUS_FIELDS references a status missing from '
    'plugininstances.enums.STATUS_CHOICES'
)


def _status_count_kwargs(status_path: str) -> dict:
    """
    Build the dict of count expressions keyed by annotation/aggregate field name.
    The same dict shape works for both QuerySet.annotate (status_path traverses
    the related manager, e.g. 'plugin_instances__status') and Manager.aggregate
    (status_path is the local field, e.g. 'status').
    """
    return {
        field: Count(
            Case(When(**{status_path: status}, then=1),
                 output_field=IntegerField())
        )
        for field, status in JOBS_STATUS_FIELDS
    }


class Workflow(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=100, blank=True, db_index=True)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE,
                                 related_name='workflows')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-creation_date',)

    def __str__(self):
        return self.title

    @staticmethod
    def add_jobs_status_count(workflow_qs):
        """
        Custom static method to add the number of associated plugin instances per
        execution status to each element of a Workflow queryset.
        """
        return workflow_qs.annotate(
            **_status_count_kwargs('plugin_instances__status')
        ).order_by('-creation_date')

    def get_jobs_status_count(self):
        """
        Custom method to get the number of associated plugin instances per
        execution status.
        """
        return self.plugin_instances.aggregate(**_status_count_kwargs('status'))


class WorkflowFilter(FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    pipeline_name = django_filters.CharFilter(field_name='pipeline__name',
                                               lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = Workflow
        fields = ['id', 'title', 'pipeline_name', 'owner_username']
