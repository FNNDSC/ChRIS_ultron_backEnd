"""
Signal receivers that maintain the denormalized counters on
:class:`dicomweb.models.PACSStudy`.

A study row carries ``NumberOfStudyRelatedSeries`` and
``NumberOfStudyRelatedInstances`` so the QIDO-RS read surface can answer
study-level queries without aggregating over the series/instance tables. These
counters are kept in step with the hierarchy here, using ``F()`` expressions so
concurrent ingests increment atomically at the database level. The invariant is
that, at every committed state, each counter equals the actual number of related
rows.

The hooks key off single-row saves/deletes:

* ``PACSSeries`` rows are created one at a time through
  ``PACSSeriesSerializer.create`` (``super().create()`` -> ``save()``), so
  ``post_save`` fires with ``created=True`` exactly once per series. The series
  is linked to its study (``study`` FK) before that save, so ``study_id`` is set
  when the signal runs -- and because the save happens inside the serializer's
  ``transaction.atomic()`` block, the counter bump commits together with it.
* ``PACSInstance`` rows are created one at a time by
  ``dicomweb.tasks.index_pacs_instance`` (``update_or_create``), so ``post_save``
  fires with ``created=True`` exactly once per instance and never on the
  idempotent re-run/update path.

``PACSFile``, by contrast, is written with ``bulk_create`` (which emits no
``post_save`` -- see ``dicomweb.tests.test_integration``). That is why instance
indexing is driven by an explicit ``on_commit`` fan-out rather than a signal.
The counters key off ``PACSInstance`` (the indexed row), not ``PACSFile``, so
they are unaffected by that limitation.

Deletes are symmetric. Django deletes referencing rows before the rows they
reference, so when a ``PACSSeries`` is removed its ``PACSInstance`` children are
deleted first -- each firing ``post_delete`` while the series (and thus its
``study_id``) is still resolvable -- and the series ``post_delete`` fires last.
The net effect drops both counters correctly. Updates that target a
since-deleted study match zero rows and are harmless no-ops.
"""
import logging

from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from pacsfiles.models import PACSSeries

from .models import PACSInstance, PACSStudy

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PACSSeries)
def increment_study_series_count(sender, instance, created, **kwargs):
    """Bump ``NumberOfStudyRelatedSeries`` when a new series joins a study."""
    if created and instance.study_id:
        PACSStudy.objects.filter(pk=instance.study_id).update(
            NumberOfStudyRelatedSeries=F('NumberOfStudyRelatedSeries') + 1)


@receiver(post_delete, sender=PACSSeries)
def decrement_study_series_count(sender, instance, **kwargs):
    """Drop ``NumberOfStudyRelatedSeries`` when a series leaves a study."""
    if instance.study_id:
        PACSStudy.objects.filter(pk=instance.study_id).update(
            NumberOfStudyRelatedSeries=F('NumberOfStudyRelatedSeries') - 1)


@receiver(post_save, sender=PACSInstance)
def increment_study_instance_count(sender, instance, created, **kwargs):
    """Bump ``NumberOfStudyRelatedInstances`` when a new instance is indexed."""
    if created and instance.series.study_id:
        PACSStudy.objects.filter(pk=instance.series.study_id).update(
            NumberOfStudyRelatedInstances=F('NumberOfStudyRelatedInstances') + 1)


@receiver(post_delete, sender=PACSInstance)
def decrement_study_instance_count(sender, instance, **kwargs):
    """Drop ``NumberOfStudyRelatedInstances`` when an indexed instance is removed.

    The instance's study is resolved with a narrow query (rather than
    ``instance.series``) so that a concurrently-gone series yields ``None``
    instead of raising ``DoesNotExist`` from inside the receiver.
    """
    study_id = (PACSSeries.objects
                .filter(pk=instance.series_id)
                .values_list('study_id', flat=True)
                .first())
    if study_id:
        PACSStudy.objects.filter(pk=study_id).update(
            NumberOfStudyRelatedInstances=F('NumberOfStudyRelatedInstances') - 1)
