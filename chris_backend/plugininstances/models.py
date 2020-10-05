
import logging
import time

from django.db import models
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

import django_filters
from django_filters.rest_framework import FilterSet

from core.swiftmanager import SwiftManager
from feeds.models import Feed
from plugins.models import ComputeResource, Plugin, PluginParameter
from plugins.fields import CPUField, MemoryField
from plugins.fields import MemoryInt, CPUInt
from pipelineinstances.models import PipelineInstance

import json

if settings.DEBUG:
    import pdb
    import pudb
    import rpudb
    from celery.contrib import rdb

logger = logging.getLogger(__name__)


STATUS_CHOICES = [("created",               "Default initial"),
                  ("waitingForPrevious",    "Waiting for previous to finish"),
                  ("scheduled",             "Scheduled to the worker"),
                  ("started",               "Sent to remote compute"),
                  ("finishedSuccessfully",  "Finished successfully"),
                  ("finishedWithError",     "Finished with error"),
                  ("cancelled",             "Cancelled")]


class PluginInstance(models.Model):
    title               = models.CharField(     max_length      = 100,
                                                blank           = True)
    start_date          = models.DateTimeField( auto_now_add    = True)
    end_date            = models.DateTimeField( auto_now_add    = True)
    status              = models.CharField(     max_length      = 30,
                                                choices         = STATUS_CHOICES,
                                                default         = 'created')
    summary             = models.CharField(     max_length      = 4000,
                                                blank           = True,
                                                default         = '')
    raw                 = models.TextField(     blank           = True,
                                                default='')
    previous            = models.ForeignKey(    "self",
                                                on_delete       = models.CASCADE,
                                                null            = True,
                                                related_name    = 'next')
    plugin              = models.ForeignKey(    Plugin,
                                                on_delete       = models.CASCADE,
                                                related_name    = 'instances')
    feed                = models.ForeignKey(    Feed,
                                                on_delete       = models.CASCADE,
                                                related_name    = 'plugin_instances')
    owner               = models.ForeignKey(    'auth.User',
                                                on_delete       = models.CASCADE)
    compute_resource    = models.ForeignKey(    ComputeResource,
                                                null            = True,
                                                on_delete       = models.SET_NULL,
                                                related_name    = 'plugin_instances')
    pipeline_inst       = models.ForeignKey(    PipelineInstance,
                                                null            = True,
                                                on_delete       = models.SET_NULL,
                                                related_name    = 'plugin_instances')
    cpu_limit           = CPUField(             null            = True)
    memory_limit        = MemoryField(          null            = True)
    number_of_workers   = models.IntegerField(  null            = True)
    gpu_limit           = models.IntegerField(  null            = True)

    class Meta:
        ordering = ('-start_date',)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Overriden to save a new feed to the DB the first time 'fs' instances are saved.
        For 'ds' instances the feed of the previous instance is assigned.
        """
        if not hasattr(self, 'feed'):
            if self.plugin.meta.type == 'fs':
                self.feed = self._save_feed()
            if self.plugin.meta.type == 'ds':
                self.feed = self.previous.feed
        self._set_compute_defaults()
        super(PluginInstance, self).save(*args, **kwargs)

    def _save_feed(self):
        """
        Custom internal method to create and save a new feed to the DB.
        """
        feed = Feed()
        feed.name = self.plugin.meta.name
        feed.save()
        feed.owner.set([self.owner])
        feed.save()
        return feed

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

    def get_output_path(self):
        """
        Custom method to get the output directory for files generated by
        the plugin instance object.
        """
        # 'fs' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/plugin_name_plugin_inst_<id>/data
        # 'ds' plugins will output files to:
        # SWIFT_CONTAINER_NAME/<username>/feed_<id>/...
        #/previous_plugin_name_plugin_inst_<id>/plugin_name_plugin_inst_<id>/data
        current = self
        path = '/{0}_{1}/data'.format(current.plugin.meta.name, current.id)
        while not current.plugin.meta.type == 'fs':
            current = current.previous
            path = '/{0}_{1}'.format(current.plugin.meta.name, current.id) + path
        username = self.owner.username
        output_path = '{0}/feed_{1}'.format(username, current.feed.id) + path
        return output_path

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

    def register_output_files(self, **kwargs):
        """
        Custom method to register files generated by the plugin instance object
        with the REST API.
        """

        # If using `rpudb` need to have the creation point in an
        # exception condition to prevent mulitple attempts to create
        # the same telnet server...
        # try:
        #     rpudb.set_trace(addr='0.0.0.0', port=7901)
        # except:
        #     pass
        # pudb.set_trace()

        d_swiftstate    = kwargs['swiftState'] if 'swiftState' in kwargs else {}
        swift_manager   = SwiftManager(settings.SWIFT_CONTAINER_NAME,
                                     settings.SWIFT_CONNECTION_PARAMS)
        output_path     = self.get_output_path()

        # the following gets the full list of objects in the swift storage
        # with prefix of <output_path>. Since there is a lag in consistency
        # of swift state from different clients, we poll here using the
        # information returned from pfcon that indicates how many files

        waitPoll        = 0
        maxWaitPoll     = 20
        l_objCurrentlyReportedBySwift   = swift_manager.ls(output_path)
        if 'd_swift_ls' in d_swiftstate.keys():
            # This conditional processes the case where a remote process
            # has returned data that has been pushed into swift by ancillary
            # services
            l_objPutIntoSwift           = d_swiftstate['d_swift_ls']['lsList']
        else:
            # This conditional addressed the case where an internal CUBE
            # process and *not* a remote execution pushed data into swift
            l_objPutIntoSwift           = l_objCurrentlyReportedBySwift
        while not all(obj in l_objCurrentlyReportedBySwift \
                      for obj in l_objPutIntoSwift) \
              and waitPoll < maxWaitPoll:
            time.sleep(0.2)
            waitPoll += 1
            l_objCurrentlyReportedBySwift   = swift_manager.ls(output_path)

        file_count = 0
        for obj_name in l_objCurrentlyReportedBySwift:
            # avoid re-register a file already registered which
            # makes this idempotent
            logger.info('Getting  -->%s<--', obj_name)
            try:
                self.files.get(fname=obj_name)
            except ObjectDoesNotExist:
                plg_inst_file = PluginInstanceFile(plugin_inst=self)
                plg_inst_file.fname.name = obj_name
                try:
                    # This try/except should protect against trying to
                    # save/registering the same file/object twice
                    plg_inst_file.save()
                except:
                    pass
            # except:
            #     # This is for debugging
            #     pudb.set_trace()
            file_count += 1

        return {
            'status':       True,
            'l_object':     l_objCurrentlyReportedBySwift,
            'total':        file_count,
            'outputPath':   output_path,
            'pollLoop':     waitPoll
        }


class PluginInstanceFilter(FilterSet):
    min_start_date = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    max_start_date = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    min_end_date = django_filters.DateFilter(field_name='end_date', lookup_expr='gte')
    max_end_date = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')
    feed_id = django_filters.CharFilter(field_name='feed_id', lookup_expr='exact')
    root_id = django_filters.CharFilter(method='filter_by_root_id')
    plugin_id = django_filters.CharFilter(field_name='plugin_id', lookup_expr='exact')
    pipeline_inst_id = django_filters.CharFilter(field_name='pipeline_inst_id',
                                                 lookup_expr='exact')
    plugin_name = django_filters.CharFilter(field_name='plugin__meta__name',
                                            lookup_expr='icontains')
    plugin_name_exact = django_filters.CharFilter(field_name='plugin__meta__name',
                                                  lookup_expr='exact')
    plugin_version = django_filters.CharFilter(field_name='plugin__version',
                                               lookup_expr='exact')

    class Meta:
        model = PluginInstance
        fields = ['id', 'min_start_date', 'max_start_date', 'min_end_date',
                  'max_end_date', 'root_id', 'title', 'status', 'owner_username',
                  'feed_id', 'plugin_id', 'plugin_name', 'plugin_name_exact',
                  'plugin_version', 'pipeline_inst_id']

    def filter_by_root_id(self, queryset, name, value):
        """
        Custom method to return the plugin instances in a queryset with a common root
        plugin instance.
        """
        filtered_queryset = []
        root_queryset = queryset.filter(pk=value)
        # check whether the root id value is in the DB
        if not root_queryset.exists():
            return root_queryset
        queue = [root_queryset[0]]
        while len(queue) > 0:
            visited = queue.pop()
            queue.extend(list(visited.next.all()))
            filtered_queryset.append(visited)
        return filtered_queryset


class PluginInstanceFile(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    fname = models.FileField(max_length=4000)
    plugin_inst = models.ForeignKey(PluginInstance, db_index=True,
                                    on_delete=models.CASCADE, related_name='files')

    class Meta:
        ordering = ('-fname',)

    def __str__(self):
        return self.fname.name


class PluginInstanceFileFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='lte')
    plugin_inst_id = django_filters.CharFilter(field_name='plugin_inst_id',
                                               lookup_expr='exact')
    feed_id = django_filters.CharFilter(field_name='plugin_inst__feed_id',
                                               lookup_expr='exact')
    fname = django_filters.CharFilter(field_name='fname', lookup_expr='startswith')
    fname_exact = django_filters.CharFilter(field_name='fname', lookup_expr='exact')

    class Meta:
        model = PluginInstanceFile
        fields = ['id', 'min_creation_date', 'max_creation_date', 'plugin_inst_id',
                  'feed_id', 'fname', 'fname_exact']


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
    value = models.CharField(max_length=20000)  # this string can be a list of long paths
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='path_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='path_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return self.value


class UnextpathParameter(models.Model):
    value = models.CharField(max_length=20000)  # this string can be a list of long paths
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='unextpath_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='unextpath_inst')

    class Meta:
        unique_together = ('plugin_inst', 'plugin_param',)

    def __str__(self):
        return self.value
