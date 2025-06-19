
from django.db import models
from django.db.models import Count, Case, When, IntegerField
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

    @staticmethod
    def add_jobs_status_count(workflow_qs):
        """
        Custom static method to add the number of associated plugin instances per
        execution status to each element of a Workflow queryset.
        """
        return workflow_qs.annotate(
            created_jobs=Count(Case(When(plugin_instances__status='created', then=1),
                               output_field=IntegerField())),
            waiting_jobs=Count(Case(When(plugin_instances__status='waiting', then=1),
                               output_field=IntegerField())),
            scheduled_jobs=Count(Case(When(plugin_instances__status='scheduled', then=1),
                                    output_field=IntegerField())),
            started_jobs=Count(Case(When(plugin_instances__status='started', then=1),
                                    output_field=IntegerField())),
            registering_jobs=Count(Case(When(plugin_instances__status='registeringFiles',
                                             then=1), output_field=IntegerField())),
            finished_jobs=Count(Case(When(plugin_instances__status='finishedSuccessfully',
                                          then=1), output_field=IntegerField())),
            errored_jobs=Count(Case(When(plugin_instances__status='finishedWithError',
                                         then=1), output_field=IntegerField())),
            cancelled_jobs=Count(Case(When(plugin_instances__status='cancelled', then=1),
                                    output_field=IntegerField()))
        )

    def get_jobs_status_count(self):
        """
        Custom method to get the number of associated plugin instances per
        execution status.
        """
        return self.plugin_instances.aggregate(
            created_jobs=Count(Case(When(status='created', then=1),
                               output_field=IntegerField())),
            waiting_jobs=Count(Case(When(status='waiting', then=1),
                               output_field=IntegerField())),
            scheduled_jobs=Count(Case(When(status='scheduled', then=1),
                               output_field=IntegerField())),
            started_jobs=Count(Case(When(status='started', then=1),
                               output_field=IntegerField())),
            registering_jobs=Count(Case(When(status='registeringFiles', then=1),
                               output_field=IntegerField())),
            finished_jobs=Count(Case(When(status='finishedSuccessfully', then=1),
                               output_field=IntegerField())),
            errored_jobs=Count(Case(When(status='finishedWithError', then=1),
                               output_field=IntegerField())),
            cancelled_jobs=Count(Case(When(status='cancelled', then=1),
                               output_field=IntegerField()))
        )


class WorkflowFilter(FilterSet):
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    pipeline_name = django_filters.CharFilter(field_name='pipeline__name',
                                               lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')

    class Meta:
        model = Workflow
        fields = ['id', 'title', 'pipeline_name', 'owner_username']
