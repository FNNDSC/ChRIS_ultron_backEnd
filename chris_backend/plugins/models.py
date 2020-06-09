
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet
from django.core.exceptions import ValidationError

from .fields import CPUField, MemoryField


# front-end API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values"), ("unextpath", "Unextracted path values")]

# table of equivalence between front-end API types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path', 'unextpath': 'unextpath'}

PLUGIN_TYPE_CHOICES = [("ds", "Data synthesis"), ("fs", "Feed synthesis")]


class ComputeResource(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=600)

    def __str__(self):
        return self.name

    def delete(self):
        """
        Overriden to only allow the delete if no plugin would be left without a compute
        resource after the operation.
        """
        plg_ids = self.get_plugins_with_self_as_single_compute_resource()
        if plg_ids:
            plg_ids.sort()
            msg = "Can not delete compute resource '%s'. Please first register the " \
                  "following plugins with another compute resource. Plugin IDs: %s"
            raise ValidationError(msg % (self.name, plg_ids))
        super().delete()

    def get_plugins_with_self_as_single_compute_resource(self):
        """
        Custom method to get the list of plugin ids for the plugins that are only
        registered with this single compute resource.
        """
        return [pl.id for pl in self.plugins.all() if pl.compute_resources.count() == 1]


class ComputeResourceFilter(FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='name', lookup_expr='exact')
    description = django_filters.CharFilter(lookup_expr='icontains')
    plugin_id = django_filters.CharFilter(field_name='plugins__id',
                                          lookup_expr='exact')

    class Meta:
        model = ComputeResource
        fields = ['id', 'name', 'name_exact', 'description', 'plugin_id']


class Plugin(models.Model):
    # default resource limits inserted at registration time
    defaults = {
                'min_cpu_limit': 1000,    # in millicores
                'min_memory_limit': 200,  # in Mi
                'max_limit': 2147483647   # maxint
               }
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=10)
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    dock_image = models.CharField(max_length=500)
    type = models.CharField(choices=PLUGIN_TYPE_CHOICES, default='ds', max_length=4)
    icon = models.URLField(max_length=300, blank=True)
    execshell = models.CharField(max_length=50)
    selfpath = models.CharField(max_length=512)
    selfexec = models.CharField(max_length=50)
    authors = models.CharField(max_length=200)
    title = models.CharField(max_length=400)
    category = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=800)
    documentation = models.CharField(max_length=800, blank=True)
    license = models.CharField(max_length=50)
    min_gpu_limit = models.IntegerField(null=True, blank=True, default=0)
    max_gpu_limit = models.IntegerField(null=True, blank=True, default=0)
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
    compute_resources = models.ManyToManyField(ComputeResource, related_name='plugins')

    class Meta:
        unique_together = ('name', 'version',)
        ordering = ('type',)

    def __str__(self):
        return self.name

    def get_plugin_parameter_names(self):
        """
        Custom method to get the list of plugin parameter names.
        """
        return [param.name for param in self.parameters.all()]

    def get_registered_compute_resources(self):
        return [cr.name for cr in self.compute_resources.all()]
    get_registered_compute_resources.admin_order_field = 'id'
    get_registered_compute_resources.short_description = 'Associated compute resources'


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
    compute_resource_id = django_filters.CharFilter(field_name='compute_resources__id',
                                                    lookup_expr='exact')

    class Meta:
        model = Plugin
        fields = ['id', 'name', 'name_exact', 'version', 'title', 'dock_image', 'type',
                  'category', 'authors', 'description', 'min_creation_date',
                  'max_creation_date', 'compute_resource_id']


class PluginParameter(models.Model):
    name = models.CharField(max_length=50)
    flag = models.CharField(max_length=52)
    short_flag = models.CharField(max_length=52, blank=True)
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
