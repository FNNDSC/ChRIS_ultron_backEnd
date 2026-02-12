
import logging

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone

import django_filters
from django_filters.rest_framework import FilterSet

from core.models import AsyncDeletableModel, ChrisFolder
from feeds.models import Feed
from plugins.models import ComputeResource, Plugin, PluginParameter
from plugins.fields import CPUField, MemoryField
from plugins.fields import MemoryInt, CPUInt
from workflows.models import Workflow


logger = logging.getLogger(__name__)


STATUS_CHOICES = [("created", "Default initial"),
                  ("waiting", "Waiting to be scheduled"),
                  ("scheduled", "Scheduled on worker"),
                  ("started", "Started on compute env"),
                  ("registeringFiles", "Registering output files"),
                  ("finishedSuccessfully", "Finished successfully"),
                  ("finishedWithError", "Finished with error"),
                  ("cancelled", "Cancelled")]

ACTIVE_STATUSES = ['created', 'waiting', 'scheduled', 'started', 'registeringFiles']

INACTIVE_STATUSES = ['finishedSuccessfully', 'finishedWithError', 'cancelled']


class PluginInstance(AsyncDeletableModel):
    title = models.CharField(max_length=100, blank=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='created',
                              db_index=True)
    summary = models.CharField(max_length=4000, blank=True)
    raw = models.TextField(blank=True)
    size = models.BigIntegerField(default=0)
    error_code = models.CharField(max_length=7, blank=True)
    previous = models.ForeignKey("self", on_delete=models.CASCADE, null=True,
                                 related_name='next')
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, related_name='instances')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE,
                             related_name='plugin_instances')
    output_folder = models.OneToOneField(ChrisFolder, on_delete=models.CASCADE, null=True,
                                         related_name='plugin_inst')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    compute_resource = models.ForeignKey(ComputeResource, null=True,
                                         on_delete=models.SET_NULL,
                                         related_name='plugin_instances')
    workflow = models.ForeignKey(Workflow, null=True,
                                 on_delete=models.SET_NULL,
                                 related_name='plugin_instances')
    cpu_limit = CPUField(null=True)
    memory_limit = MemoryField(null=True)
    number_of_workers = models.IntegerField(null=True)
    gpu_limit = models.IntegerField(null=True)

    class Meta:
        ordering = ('-start_date',)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Overriden to save a new output folder to the DB the first time the instance
        is saved. In addition, a new feed is saved for 'fs' instances. For 'ds' and
        'ts' instances the feed of the previous instance is assigned.
        """
        if not hasattr(self, 'feed'):
            plugin_type = self.plugin.meta.type
            if plugin_type == 'fs':
                self.feed = self._save_feed()
            elif plugin_type in ('ds', 'ts'):
                self.feed = self.previous.feed

        self._set_compute_defaults()

        super(PluginInstance, self).save(*args, **kwargs)

        if self.output_folder is None:
            self.output_folder = self._save_output_folder()
            self.save()

    def _save_feed(self):
        """
        Custom internal method to create and save a new feed to the DB.
        """
        feed = Feed()
        feed.name = self.title or self.plugin.meta.name
        feed.owner = self.owner
        feed.save()

        # feed's folder path: SWIFT_CONTAINER_NAME/home/<username>/feeds/feed_<id>
        feed_folder_path = f'home/{self.owner.username}/feeds/feed_{feed.id}'
        folder = ChrisFolder(path=feed_folder_path, owner=self.owner)
        folder.save()

        feed.folder = folder
        feed.save()
        return feed

    def _save_output_folder(self):
        """
        Custom internal method to create and save a new output folder to the DB.
        """
        # 'fs' plugins will output files to:
        # SWIFT_CONTAINER_NAME/home/<username>/feeds/feed_<id>/<plugin_name>_
        # <plugin_inst_id>/data
        # 'ds' and 'ts' plugins will output files to:
        # SWIFT_CONTAINER_NAME/home/<username>/feeds/feed_<id>/...
        # /<previous_plugin_name>_<plugin_inst_id>/<plugin_name>_<plugin_inst_id>/data
        current = self
        path = '/{0}_{1}/data'.format(current.plugin.meta.name, current.id)
        while not current.plugin.meta.type == 'fs':
            current = current.previous
            path = '/{0}_{1}'.format(current.plugin.meta.name, current.id) + path

        feed = current.feed
        # username = self.owner.username
        username = feed.owner.username  # use creator of the feed for shared
        # feeds
        output_path = 'home/{0}/feeds/feed_{1}'.format(username, feed.id) + path

        folder = ChrisFolder(path=output_path, owner=self.owner)
        folder.save()
        return folder

    def _set_compute_defaults(self):
        """
        Custom internal method to set compute-related defaults.
        """
        if not self.cpu_limit:
            self.cpu_limit = CPUInt(self.plugin.min_cpu_limit)
        if not self.memory_limit:
            self.memory_limit = MemoryInt(self.plugin.min_memory_limit)
        if not self.number_of_workers:
            self.number_of_workers = self.plugin.min_number_of_workers
        if not self.gpu_limit:
            self.gpu_limit = self.plugin.min_gpu_limit

    def get_root_instance(self):
        """
        Custom method to return the root plugin instance for this plugin instance.
        """
        current = self
        while not current.plugin.meta.type == 'fs':
            current = current.previous
        return current

    def get_descendant_instances(self):
        """
        Custom method to return all the plugin instances that are a descendant of this
        plugin instance.
        """
        descendant_instances = []
        queue = [self]
        while len(queue) > 0:
            visited = queue.pop()
            queue.extend(list(visited.next.all()))
            descendant_instances.append(visited)
        return descendant_instances

    def get_parameter_instances(self):
        """
        Custom method to get all the parameter instances associated with this plugin
        instance regardless of their type.
        """
        parameter_instances = []
        parameter_instances.extend(list(self.unextpath_param.all()))
        parameter_instances.extend(list(self.path_param.all()))
        parameter_instances.extend(list(self.string_param.all()))
        parameter_instances.extend(list(self.integer_param.all()))
        parameter_instances.extend(list(self.float_param.all()))
        parameter_instances.extend(list(self.boolean_param.all()))
        return parameter_instances

    def get_output_path(self):
        """
        Custom method to get the output directory for files generated by
        the plugin instance object.
        """
        return str(self.output_folder.path)

    def set_status(self, status):
        self.status = status

        if status == 'scheduled':
            now = timezone.now()
            self.start_date = now  # save scheduling date
            self.end_date = now
            self.save(update_fields=['start_date', 'end_date', 'status'])
        else:
            self.save(update_fields=['status'])


@receiver(post_delete, sender=PluginInstance)
def auto_delete_output_folder_with_plugin_instance(sender, instance, **kwargs):
    try:
        instance.output_folder.parent.delete()  # delete parent of the output data folder
    except Exception:
        pass


class PluginInstanceFilter(FilterSet):
    min_start_date = django_filters.IsoDateTimeFilter(field_name='start_date',
                                                      lookup_expr='gte')
    max_start_date = django_filters.IsoDateTimeFilter(field_name='start_date',
                                                      lookup_expr='lte')
    min_end_date = django_filters.IsoDateTimeFilter(field_name='end_date',
                                                    lookup_expr='gte')
    max_end_date = django_filters.IsoDateTimeFilter(field_name='end_date',
                                                    lookup_expr='lte')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')
    feed_id = django_filters.CharFilter(field_name='feed_id', lookup_expr='exact')
    root_id = django_filters.CharFilter(method='filter_by_root_id')
    previous_id = django_filters.CharFilter(method='filter_by_previous_id')
    plugin_id = django_filters.CharFilter(field_name='plugin_id', lookup_expr='exact')
    workflow_id = django_filters.CharFilter(field_name='workflow_id', lookup_expr='exact')
    plugin_name = django_filters.CharFilter(field_name='plugin__meta__name',
                                            lookup_expr='icontains')
    plugin_name_exact = django_filters.CharFilter(field_name='plugin__meta__name',
                                                  lookup_expr='exact')
    plugin_version = django_filters.CharFilter(field_name='plugin__version',
                                               lookup_expr='exact')
    plugin_type = django_filters.CharFilter(field_name='plugin__meta__type',
                                            lookup_expr='exact')
    active = django_filters.BooleanFilter(method='filter_by_active_status')

    class Meta:
        model = PluginInstance
        fields = ['id', 'min_start_date', 'max_start_date', 'min_end_date',
                  'max_end_date', 'root_id', 'previous_id', 'title', 'status', 'active',
                  'owner_username', 'feed_id', 'plugin_id', 'plugin_name',
                  'plugin_name_exact', 'plugin_version', 'plugin_type', 'workflow_id',
                  'deletion_status']

    def filter_by_root_id(self, queryset, name, value):
        """
        Custom method to return the plugin instances in a queryset with a common root
        plugin instance.
        """
        filtered_list = []
        root_queryset = queryset.filter(pk=value)
        # check whether the root id value is in the DB
        if not root_queryset.exists():
            return root_queryset
        queue = [root_queryset[0]]
        while len(queue) > 0:
            visited = queue.pop()
            queue.extend(list(visited.next.all()))
            filtered_list.append(visited.id)
        return PluginInstance.objects.filter(pk__in=filtered_list)

    def filter_by_previous_id(self, queryset, name, value):
        """
        Custom method to return the plugin instances in a queryset with a common previous
        plugin instance.
        """
        previous_queryset = queryset.filter(pk=value)
        # check whether the previous id value is in the DB
        if not previous_queryset.exists():
            return previous_queryset
        previous = previous_queryset.first()
        return previous.next.all()

    def filter_by_active_status(self, queryset, name, value):
        """
        Custom method to return the plugin instances in a queryset with an
        "active" status.
        """
        statuses = ACTIVE_STATUSES if value else INACTIVE_STATUSES
        return queryset.filter(status__in=statuses)


class PluginInstanceLock(models.Model):
    plugin_inst = models.OneToOneField(PluginInstance, on_delete=models.CASCADE,
                                       related_name='lock')
    start_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.plugin_inst.id)


class PluginInstanceSplit(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    filter = models.CharField(max_length=600, blank=True)
    created_plugin_inst_ids = models.CharField(max_length=600)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='splits')

    class Meta:
        ordering = ('plugin_inst', '-creation_date',)

    def __str__(self):
        return self.created_plugin_inst_ids


class StrParameter(models.Model):
    value = models.CharField(max_length=600, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='string_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='string_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return self.value


class IntParameter(models.Model):
    value = models.IntegerField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='integer_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='integer_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return str(self.value)


class FloatParameter(models.Model):
    value = models.FloatField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='float_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='float_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return str(self.value)


class BoolParameter(models.Model):
    value = models.BooleanField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='boolean_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='boolean_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return str(self.value)


class PathParameter(models.Model):
    value = models.CharField(max_length=16000)  # this string can be a list of long paths
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='path_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='path_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return self.value


class UnextpathParameter(models.Model):
    value = models.CharField(max_length=16000)  # this string can be a list of long paths
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='unextpath_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='unextpath_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return self.value


PARAMETER_MODELS = {'string': StrParameter,
                    'integer': IntParameter,
                    'float': FloatParameter,
                    'boolean': BoolParameter,
                    'path': PathParameter,
                    'unextpath': UnextpathParameter}
