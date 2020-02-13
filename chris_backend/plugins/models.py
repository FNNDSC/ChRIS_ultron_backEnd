
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet

from .fields import CPUField, MemoryField


# front-end API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values"), ("unextpath", "Unextracted path values")]

# table of equivalence between front-end API types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path', 'unextpath': 'unextpath'}

PLUGIN_TYPE_CHOICES = [("ds", "Data plugin"), ("fs", "Filesystem plugin")]


class ComputeResource(models.Model):
    compute_resource_identifier = models.CharField(max_length=100)

    def __str__(self):
        return self.compute_resource_identifier


class Plugin(models.Model):
    # default resource limits inserted at registration time
    defaults = {
                'min_cpu_limit': 1000,    # in millicores
                'min_memory_limit': 200,  # in Mi
                'max_limit': 2147483647   # maxint
               }
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
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
                             default=defaults['min_cpu_limit'])  # In millicores
    max_cpu_limit = CPUField(null=True, blank=True,
                             default=defaults['max_limit'])  # In millicores
    min_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['min_memory_limit'])  # In Mi
    max_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['max_limit'])  # In Mi

    class Meta:
        unique_together = ('name', 'version',)
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

    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='name', lookup_expr='exact')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    category = django_filters.CharFilter(field_name='category', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    authors = django_filters.CharFilter(field_name='authors', lookup_expr='icontains')

    class Meta:
        model = Plugin
        fields = ['id', 'name', 'name_exact', 'version', 'title', 'dock_image', 'type',
                  'category', 'authors', 'description', 'min_creation_date',
                  'max_creation_date']


class PluginParameter(models.Model):
    name = models.CharField(max_length=50)
    flag = models.CharField(max_length=52)
    action = models.CharField(max_length=20, default='store')
    optional = models.BooleanField(default=False)
    type = models.CharField(choices=TYPE_CHOICES, default='string', max_length=10)
    help = models.TextField(blank=True)
    ui_exposed = models.BooleanField(default=True)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE,
                               related_name='parameters')
    
    class Meta:
        ordering = ('plugin',)

    def __str__(self):
        return self.name

    def get_default(self):
        """
        Overriden to get the default parameter instance regardless of its type.
        """
        default_attr_name = '%s_default' % self.type
        return getattr(self, default_attr_name, None)


class DefaultStrParameter(models.Model):
    value = models.CharField(max_length=600, blank=True)
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='string_default')

    def __str__(self):
        return self.value


class DefaultIntParameter(models.Model):
    value = models.IntegerField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='integer_default')

    def __str__(self):
        return str(self.value)


class DefaultFloatParameter(models.Model):
    value = models.FloatField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='float_default')

    def __str__(self):
        return str(self.value)


class DefaultBoolParameter(models.Model):
    value = models.BooleanField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='boolean_default')

    def __str__(self):
        return str(self.value)
