
import time

from django.db import models
from django.conf import settings

import django_filters
from django_filters.rest_framework import FilterSet

import swiftclient

from feeds.models import Feed
from .fields import CPUField, MemoryField




# API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values")]

# table of equivalence between front-end types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path'}

PLUGIN_TYPE_CHOICES = [("ds", "Data plugin"), ("fs", "Filesystem plugin")]

STATUS_TYPES = ['started', 'finishedSuccessfully', 'finishedWithError']


class ComputeResource(models.Model):
    compute_resource_identifier = models.CharField(max_length=100)

    def __str__(self):
        return self.compute_resource_identifier


class Plugin(models.Model):
    # default resource limits inserted at registration time
    defaults = {
                'min_cpu_limit': 1000,   # in millicores
                'min_memory_limit': 200, # in Mi
                'max_limit': 2147483647  # maxint
               }
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    dock_image = models.CharField(max_length=500)
    type = models.CharField(choices=PLUGIN_TYPE_CHOICES, default='ds', max_length=4)
    execshell = models.CharField(max_length=50)
    selfpath = models.CharField(max_length=512)
    selfexec = models.CharField(max_length=50)
    authors = models.CharField(max_length=200)
    title = models.CharField(max_length=400)
    category = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=800)
    documentation = models.CharField(max_length=800, blank=True)
    license = models.CharField(max_length=50)
    version = models.CharField(max_length=10)
    compute_resource = models.ForeignKey(ComputeResource, on_delete=models.CASCADE,
                        related_name='plugins')
    min_gpu_limit = models.IntegerField(null=True, blank=True, default=0)
    max_gpu_limit = models.IntegerField(null=True, blank=True,
                                        default=defaults['max_limit'])
    min_number_of_workers = models.IntegerField(null=True, blank=True, default=1)
    max_number_of_workers = models.IntegerField(null=True, blank=True,
                                                default=defaults['max_limit'])
    min_cpu_limit = CPUField(null=True, blank=True,
                             default=defaults['min_cpu_limit']) # In millicores
    max_cpu_limit = CPUField(null=True, blank=True,
                             default=defaults['max_limit']) # In millicores
    min_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['min_memory_limit']) # In Mi
    max_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['max_limit']) # In Mi

    class Meta:
        ordering = ('type',)

    def __str__(self):
        return self.name

    def get_plugin_parameter_names(self):
        """
        Custom method to get the list of plugin parameter names.
        """
        params = self.parameters.all()
        return [param.name for param in params]


class PluginFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='lte')

    class Meta:
        model = Plugin
        fields = ['id', 'name', 'dock_image', 'type', 'category', 'authors',
                  'min_creation_date', 'max_creation_date']


class PluginParameter(models.Model):
    name = models.CharField(max_length=50)
    flag = models.CharField(max_length=52)
    action = models.CharField(max_length=20, default='store')
    optional = models.BooleanField(default=True)
    default = models.CharField(max_length=200, blank=True)
    type = models.CharField(choices=TYPE_CHOICES, default='string', max_length=10)
    help = models.TextField(blank=True)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE,
                               related_name='parameters')
    
    class Meta:
        ordering = ('plugin',)

    def __str__(self):
        return self.name
    

class PluginInstance(models.Model):
    title = models.CharField(max_length=100, blank=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default=STATUS_TYPES[0])
    previous = models.ForeignKey("self", on_delete=models.CASCADE, null=True,
                                 related_name='next')
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, related_name='instances')
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE,
                             related_name='plugin_instances')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    compute_resource = models.ForeignKey(ComputeResource, on_delete=models.CASCADE, 
                                    related_name='plugin_instances')
    cpu_limit = CPUField(null=True)
    memory_limit = MemoryField(null=True)
    number_of_workers = models.IntegerField(null=True)
    gpu_limit = models.IntegerField(null=True)

    class Meta:
        ordering = ('-start_date',)

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        """
        Overriden to save a new feed to the DB the first time the instance is saved.
        """
        if not hasattr(self, 'feed') and self.plugin.type == 'fs':
            self._save_feed()
        super(PluginInstance, self).save(*args, **kwargs)
            
    def _save_feed(self):
        """
        Custom method to create and save a new feed to the DB.
        """
        feed = Feed()
        feed.name = self.plugin.name
        feed.owner.set([self.owner])
        feed.save()
        self.feed = feed

    def get_root_instance(self):
        """
        Custom method to return the root plugin instance for this plugin instance.
        """
        current = self
        while not current.plugin.type == 'fs':
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
        path = '/{0}_{1}/data'.format(current.plugin.name, current.id)
        while not current.plugin.type == 'fs':
            current = current.previous
            path = '/{0}_{1}'.format(current.plugin.name, current.id) + path
        username = self.owner.username
        output_path = '{0}/feed_{1}'.format(username, current.feed.id) + path
        return output_path

    def register_output_files(self, *args, **kwargs):
        """
        Custom method to register files generated by the plugin instance object
        with the REST API.
        """
        d_swiftState    = {}
        for k, v in kwargs.items():
            if k == 'swiftState':   d_swiftState    = v

        # initiate a Swift service connection
        conn = swiftclient.Connection(
            user    = settings.SWIFT_USERNAME,
            key     = settings.SWIFT_KEY,
            authurl = settings.SWIFT_AUTH_URL,
        )
        output_path = self.get_output_path()

        # the following gets the full list of objects in the swift storage
        # with prefix of <output_path>. Since there is a lag in consistency
        # of swift state from different clients, we poll here using the 
        # information returned from pfcon that indicates how many files

        object_list             = []
        pollLoop                = 0
        maxPolls                = 20
        if 'd_swiftstore' in d_swiftState.keys():
            objectsReportedInSwift  = d_swiftState['d_swiftstore']['filesPushed']
        else:
            objectsReportedInSwift  = 0 

        while len(object_list) <= objectsReportedInSwift and pollLoop < maxPolls:
            object_list = conn.get_container(
                        settings.SWIFT_CONTAINER_NAME, 
                        prefix          = output_path,
                        full_listing    = True)[1]
            time.sleep(0.2)
            pollLoop += 1
        fileCount       = 0
        for object in object_list:
            plg_inst_file = PluginInstanceFile(plugin_inst=self)
            plg_inst_file.fname.name = object['name']
            plg_inst_file.save()
            fileCount += 1
        return {
            'status':       True,
            'l_object':     object_list,
            'total':        fileCount,
            'outputPath':   output_path,
            'pollLoop':     pollLoop
        }


class PluginInstanceFilter(FilterSet):
    min_start_date = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    max_start_date = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    min_end_date = django_filters.DateFilter(field_name='end_date', lookup_expr='gte')
    max_end_date = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')
    root_id = django_filters.CharFilter(method='filter_by_root_id')

    class Meta:
        model = PluginInstance
        fields = ['id', 'min_start_date', 'max_start_date', 'min_end_date', 'max_end_date',
                  'root_id']

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
    fname = models.FileField(max_length=2048)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='files')

    class Meta:
        ordering = ('fname',)

    def __str__(self):
        return self.fname.name


class StringParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='string_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='string_inst')

    def __str__(self):
        return self.value
    
    
class IntParameter(models.Model):
    value = models.IntegerField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='integer_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='integer_inst')

    def __str__(self):
        return str(self.value)
    

class FloatParameter(models.Model):
    value = models.FloatField()
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='float_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='float_inst')

    def __str__(self):
        return str(self.value)


class BoolParameter(models.Model):
    value = models.BooleanField(default=False, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='boolean_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='boolean_inst')

    def __str__(self):
        return str(self.value)


class PathParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_inst = models.ForeignKey(PluginInstance, on_delete=models.CASCADE,
                                    related_name='path_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='path_inst')

    def __str__(self):
        return self.value
