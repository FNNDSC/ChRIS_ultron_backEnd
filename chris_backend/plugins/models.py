
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet

from .fields import CPUField, MemoryField


# front-end API types
TYPE_CHOICES = [("string", "String values"), ("float", "Float values"),
                ("boolean", "Boolean values"), ("integer", "Integer values"),
                ("path", "Path values")]

# table of equivalence between front-end API types and back-end types
TYPES = {'string': 'str', 'integer': 'int', 'float': 'float', 'boolean': 'bool',
         'path': 'path'}

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
                             default=defaults['min_cpu_limit'])  # In millicores
    max_cpu_limit = CPUField(null=True, blank=True,
                             default=defaults['max_limit'])  # In millicores
    min_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['min_memory_limit'])  # In Mi
    max_memory_limit = MemoryField(null=True, blank=True,
                                   default=defaults['max_limit'])  # In Mi

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

    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    category = django_filters.CharFilter(field_name='category', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    authors = django_filters.CharFilter(field_name='authors', lookup_expr='icontains')

    class Meta:
        model = Plugin
        fields = ['id', 'name', 'title', 'dock_image', 'type', 'category', 'authors',
                  'description', 'min_creation_date', 'max_creation_date']


class PluginParameter(models.Model):
    name = models.CharField(max_length=50)
    flag = models.CharField(max_length=52)
    action = models.CharField(max_length=20, default='store')
    optional = models.BooleanField(default=True)
    type = models.CharField(choices=TYPE_CHOICES, default='string', max_length=10)
    help = models.TextField(blank=True)
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE,
                               related_name='parameters')
    
    class Meta:
        ordering = ('plugin',)

    def __str__(self):
        return self.name

    def get_default(self):
        """
        Overriden to get the default parameter value regardless of type.
        """
        default_attr_name = '%s_default' % self.type
        default = getattr(self, default_attr_name, None)
        return default.value if default else None


class DefaultStrParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
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


class DefaultPathParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='path_default')

    def __str__(self):
        return self.value


class Pipeline(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    locked = models.BooleanField(default=True)
    authors = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=800, blank=True)
    owner = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    plugins = models.ManyToManyField(Plugin, related_name='pipelines',
                                     through='PluginPiping')

    class Meta:
        ordering = ('category',)

    def __str__(self):
        return self.name


class PipelineFilter(FilterSet):
    min_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='lte')
    owner_username = django_filters.CharFilter(field_name='owner__username',
                                               lookup_expr='exact')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    category = django_filters.CharFilter(field_name='category', lookup_expr='icontains')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    authors = django_filters.CharFilter(field_name='authors', lookup_expr='icontains')

    class Meta:
        model = Pipeline
        fields = ['id', 'owner_username', 'name', 'category', 'description',
                  'authors', 'min_creation_date', 'max_creation_date']


<<<<<<< HEAD
class PluginPiping(models.Model):
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE,
                                 related_name='plugin_pipings')
    previous = models.ForeignKey("self", on_delete=models.CASCADE, null=True,
                                 related_name='next')

    class Meta:
        ordering = ('pipeline',)

    def __str__(self):
        return str(self.id)

    def save(self, *args, **kwargs):
        """
        Overriden to save the default plugin parameters' values associated with this
        piping.
        """
        super(PluginPiping, self).save(*args, **kwargs)
        plugin = self.plugin
        parameters = plugin.parameters.all()
        for parameter in parameters:
            default_piping_param = DEFAULT_PIPING_PARAMETER_MODELS[parameter.type]()
            default_piping_param.plugin_piping = self
            default_piping_param.plugin_param = parameter
            default = parameter.get_default()
            if default is not None:  # use plugin's parameter default for piping's default
                default_piping_param.value = default
            default_piping_param.save()


class DefaultPipingStrParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='string_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='string_piping_default')

    def __str__(self):
        return self.value


class DefaultPipingIntParameter(models.Model):
    value = models.IntegerField(default=1, blank=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='integer_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='integer_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingFloatParameter(models.Model):
    value = models.FloatField(default=1.0, blank=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='float_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='float_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingBoolParameter(models.Model):
    value = models.BooleanField(default=False, blank=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='boolean_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='boolean_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingPathParameter(models.Model):
    value = models.CharField(max_length=200, blank=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='path_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='path_piping_default')

    def __str__(self):
        return self.value


DEFAULT_PIPING_PARAMETER_MODELS = {'string': DefaultPipingStrParameter,
                         'integer': DefaultPipingIntParameter,
                         'float': DefaultPipingFloatParameter,
                         'boolean': DefaultPipingBoolParameter,
                         'path': DefaultPipingPathParameter}
