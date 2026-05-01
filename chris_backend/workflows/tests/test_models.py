
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Case, When, IntegerField
from django.test import TestCase

from plugininstances.enums import STATUS_CHOICES
from plugininstances.models import PluginInstance
from plugins.models import ComputeResource, Plugin, PluginMeta
from pipelines.models import Pipeline
from workflows.models import (JOBS_STATUS_FIELDS, Workflow,
                              _status_count_kwargs)


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class JobsStatusFieldsTests(TestCase):
    """Sanity checks for the JOBS_STATUS_FIELDS / _status_count_kwargs constants."""

    def test_every_status_is_in_status_choices(self):
        valid = {c[0] for c in STATUS_CHOICES}
        for _, status in JOBS_STATUS_FIELDS:
            self.assertIn(status, valid)

    def test_status_count_kwargs_has_one_entry_per_field(self):
        kwargs = _status_count_kwargs('plugin_instances__status')
        self.assertEqual(set(kwargs.keys()), {f for f, _ in JOBS_STATUS_FIELDS})

    def test_status_count_kwargs_uses_supplied_path(self):
        local = _status_count_kwargs('status')
        related = _status_count_kwargs('plugin_instances__status')
        # The two should produce a different SQL string because the inner
        # When() lookup paths differ.
        for field in (f for f, _ in JOBS_STATUS_FIELDS):
            self.assertNotEqual(str(local[field]), str(related[field]))


class WorkflowJobsStatusCountTests(TestCase):
    """
    Behavioral + SQL-equivalence tests for the refactored
    ``Workflow.add_jobs_status_count`` and ``Workflow.get_jobs_status_count``.
    """

    def setUp(self):
        logging.disable(logging.WARNING)

        (self.compute_resource, _) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        (pl_meta, _) = PluginMeta.objects.get_or_create(
            name='simplefsapp', type='fs')
        (self.plugin, _) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        self.plugin.compute_resources.set([self.compute_resource])
        self.plugin.save()

        self.user = User.objects.create_user(username='wf_owner',
                                             password='wf_pass')
        (self.pipeline, _) = Pipeline.objects.get_or_create(
            name='ModelPipeline', owner=self.user, category='test')
        (self.workflow, _) = Workflow.objects.get_or_create(
            title='ModelsWf', pipeline=self.pipeline, owner=self.user)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _make_instance(self, status):
        return PluginInstance.objects.create(
            plugin=self.plugin, owner=self.user,
            compute_resource=self.compute_resource,
            workflow=self.workflow, status=status)

    @staticmethod
    def _legacy_annotate(qs):
        """
        The pre-refactor literal-kwargs form of ``add_jobs_status_count``.
        Used as the reference for SQL/result equivalence tests.
        """
        return qs.annotate(
            created_jobs=Count(Case(When(plugin_instances__status='created', then=1),
                                    output_field=IntegerField())),
            waiting_jobs=Count(Case(When(plugin_instances__status='waiting', then=1),
                                    output_field=IntegerField())),
            copying_jobs=Count(Case(When(plugin_instances__status='copying', then=1),
                                    output_field=IntegerField())),
            scheduled_jobs=Count(Case(When(plugin_instances__status='scheduled', then=1),
                                      output_field=IntegerField())),
            started_jobs=Count(Case(When(plugin_instances__status='started', then=1),
                                    output_field=IntegerField())),
            uploading_jobs=Count(Case(When(plugin_instances__status='uploading', then=1),
                                      output_field=IntegerField())),
            registering_jobs=Count(Case(When(plugin_instances__status='registeringFiles',
                                             then=1), output_field=IntegerField())),
            finished_jobs=Count(Case(When(plugin_instances__status='finishedSuccessfully',
                                          then=1), output_field=IntegerField())),
            errored_jobs=Count(Case(When(plugin_instances__status='finishedWithError',
                                         then=1), output_field=IntegerField())),
            cancelled_jobs=Count(Case(When(plugin_instances__status='cancelled', then=1),
                                      output_field=IntegerField())),
        ).order_by('-creation_date')

    @staticmethod
    def _legacy_aggregate(workflow):
        """The pre-refactor literal-kwargs form of ``get_jobs_status_count``."""
        return workflow.plugin_instances.aggregate(
            created_jobs=Count(Case(When(status='created', then=1),
                                    output_field=IntegerField())),
            waiting_jobs=Count(Case(When(status='waiting', then=1),
                                    output_field=IntegerField())),
            copying_jobs=Count(Case(When(status='copying', then=1),
                                    output_field=IntegerField())),
            scheduled_jobs=Count(Case(When(status='scheduled', then=1),
                                      output_field=IntegerField())),
            started_jobs=Count(Case(When(status='started', then=1),
                                    output_field=IntegerField())),
            uploading_jobs=Count(Case(When(status='uploading', then=1),
                                      output_field=IntegerField())),
            registering_jobs=Count(Case(When(status='registeringFiles', then=1),
                                        output_field=IntegerField())),
            finished_jobs=Count(Case(When(status='finishedSuccessfully', then=1),
                                     output_field=IntegerField())),
            errored_jobs=Count(Case(When(status='finishedWithError', then=1),
                                    output_field=IntegerField())),
            cancelled_jobs=Count(Case(When(status='cancelled', then=1),
                                      output_field=IntegerField())),
        )

    def test_add_jobs_status_count_sql_matches_legacy(self):
        """
        Refactored add_jobs_status_count must produce byte-for-byte the same SQL
        as the pre-refactor ten-literal-kwarg form, guaranteeing the same query
        plan (one LEFT JOIN + GROUP BY + 10 conditional counts).
        """
        legacy_qs = self._legacy_annotate(Workflow.objects.all())
        refactored_qs = Workflow.add_jobs_status_count(Workflow.objects.all())
        self.assertEqual(str(legacy_qs.query), str(refactored_qs.query))

    def test_add_jobs_status_count_results_match_legacy(self):
        """
        Even if Django's SQL compiler ever drifts, the actual annotated counts
        must still match the legacy form on a representative dataset.
        """
        # 2 created, 1 waiting, 3 finishedSuccessfully, 1 cancelled, 0 elsewhere
        for _ in range(2):
            self._make_instance('created')
        self._make_instance('waiting')
        for _ in range(3):
            self._make_instance('finishedSuccessfully')
        self._make_instance('cancelled')

        legacy = self._legacy_annotate(Workflow.objects.all()).get(pk=self.workflow.pk)
        refactored = Workflow.add_jobs_status_count(
            Workflow.objects.all()).get(pk=self.workflow.pk)
        for field, _ in JOBS_STATUS_FIELDS:
            self.assertEqual(getattr(refactored, field),
                             getattr(legacy, field),
                             f"mismatch on '{field}'")

    def test_add_jobs_status_count_zero_when_no_instances(self):
        """A workflow with no plugin instances has 0 in every annotated count."""
        annotated = Workflow.add_jobs_status_count(
            Workflow.objects.all()).get(pk=self.workflow.pk)
        for field, _ in JOBS_STATUS_FIELDS:
            self.assertEqual(getattr(annotated, field), 0,
                             f"expected 0 for '{field}'")

    def test_get_jobs_status_count_matches_legacy(self):
        """
        Refactored get_jobs_status_count must return identical dicts to the
        legacy literal-kwargs aggregate.
        """
        for _ in range(2):
            self._make_instance('started')
        self._make_instance('finishedWithError')

        self.assertEqual(self.workflow.get_jobs_status_count(),
                         self._legacy_aggregate(self.workflow))
