
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
    """
    Model class that defines a remote compute resource for plugins.
    """
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
    """
    Filter class for the ComputeResource model.
    """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='name', lookup_expr='exact')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    plugin_id = django_filters.CharFilter(field_name='plugins__id',
                                          lookup_expr='exact')

    class Meta:
        model = ComputeResource
        fields = ['id', 'name', 'name_exact', 'description', 'plugin_id']


class PluginMeta(models.Model):
    """
    Model class that defines the meta info for a plugin that is the same across
    plugin's versions.
    """
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=400, blank=True)
    stars = models.IntegerField(default=0)
    public_repo = models.URLField(max_length=300, blank=True)
    license = models.CharField(max_length=50, blank=True)
    type = models.CharField(choices=PLUGIN_TYPE_CHOICES, default='ds', max_length=4)
    icon = models.URLField(max_length=300, blank=True)
    category = models.CharField(max_length=100, blank=True)
    authors = models.CharField(max_length=200, blank=True)
    documentation = models.CharField(max_length=800, blank=True)

    class Meta:
        ordering = ('type', '-creation_date',)

    def __str__(self):
        return str(self.name)


class PluginMetaFilter(FilterSet):
    """
    Filter class for the PluginMeta model.
    """
    min_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name='creation_date',
                                                  lookup_expr='lte')
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='name', lookup_expr='exact')
    title = django_filters.CharFilter(field_name='title', lookup_expr='icontains')
    category = django_filters.CharFilter(field_name='category', lookup_expr='icontains')
    type = django_filters.CharFilter(field_name='type', lookup_expr='exact')
    authors = django_filters.CharFilter(field_name='authors', lookup_expr='icontains')
    name_title_category = django_filters.CharFilter(method='search_name_title_category')
    name_authors_category = django_filters.CharFilter(
        method='search_name_authors_category')

    def search_name_title_category(self, queryset, name, value):
        """
        Custom method to get a filtered queryset with all plugins for which name or title
        or category matches the search value.
        """
        # construct the full lookup expression.
        lookup = models.Q(name__icontains=value)
        lookup = lookup | models.Q(title__icontains=value)
        lookup = lookup | models.Q(category__icontains=value)
        return queryset.filter(lookup)

    def search_name_authors_category(self, queryset, name, value):
        """
        Custom method to get a filtered queryset with all plugins for which name or author
        or category matches the search value.
        """
        # construct the full lookup expression.
        lookup = models.Q(name__icontains=value)
        lookup = lookup | models.Q(authors__icontains=value)
        lookup = lookup | models.Q(category__icontains=value)
        return queryset.filter(lookup)

    class Meta:
        model = PluginMeta
        fields = ['id', 'name', 'name_exact', 'title', 'category', 'type', 'authors',
                  'min_creation_date', 'max_creation_date', 'name_title_category',
                  'name_authors_category']


class Plugin(models.Model):
    """
    Model class that defines the versioned plugin.
    """
    # default resource limits inserted at registration time
    defaults = {
                'min_cpu_limit': 1000,    # in millicores
                'min_memory_limit': 200,  # in Mi
                'max_limit': 2147483647   # maxint
               }
    creation_date = models.DateTimeField(auto_now_add=True)
    meta = models.ForeignKey(PluginMeta, on_delete=models.CASCADE, related_name='plugins')
    version = models.CharField(max_length=10)
    dock_image = models.CharField(max_length=500)
    execshell = models.CharField(max_length=50)
    selfpath = models.CharField(max_length=512)
    selfexec = models.CharField(max_length=50)
    description = models.CharField(max_length=800, blank=True)
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
        unique_together = ('meta', 'version',)
        ordering = ('meta', '-creation_date',)

    def __str__(self):
        return self.meta.name

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
    """
    Filter class for the Plugin model.
    """
    min_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='gte')
    max_creation_date = django_filters.DateFilter(field_name="creation_date",
                                                  lookup_expr='lte')
    name = django_filters.CharFilter(field_name='meta__name', lookup_expr='icontains')
    name_exact = django_filters.CharFilter(field_name='meta__name', lookup_expr='exact')
    title = django_filters.CharFilter(field_name='meta__title', lookup_expr='icontains')
    category = django_filters.CharFilter(field_name='meta__category',
                                         lookup_expr='icontains')
    type = django_filters.CharFilter(field_name='meta__type', lookup_expr='exact')
    description = django_filters.CharFilter(field_name='description',
                                            lookup_expr='icontains')
    name_title_category = django_filters.CharFilter(method='search_name_title_category')
    compute_resource_id = django_filters.CharFilter(field_name='compute_resources__id',
                                                    lookup_expr='exact')

    def search_name_title_category(self, queryset, name, value):
        """
        Custom method to get a filtered queryset with all plugins for which name or title
        or category matches the search value.
        """
        # construct the full lookup expression.
        lookup = models.Q(meta__name__icontains=value)
        lookup = lookup | models.Q(meta__title__icontains=value)
        lookup = lookup | models.Q(meta__category__icontains=value)
        return queryset.filter(lookup)

    class Meta:
        model = Plugin
        fields = ['id', 'name', 'name_exact', 'version', 'dock_image', 'type', 'category',
                  'min_creation_date', 'max_creation_date', 'title',  'description',
                  'name_title_category', 'compute_resource_id']


class PluginParameter(models.Model):
    """
    Model class that defines a plugin parameter.
    """
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
    """
    Model class that defines a default value for a plugin parameter of type string.
    """
    value = models.CharField(max_length=600, blank=True)
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='string_default')

    def __str__(self):
        return self.value


class DefaultIntParameter(models.Model):
    """
    Model class that defines a default value for a plugin parameter of type integer.
    """
    value = models.IntegerField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='integer_default')

    def __str__(self):
        return str(self.value)


class DefaultFloatParameter(models.Model):
    """
    Model class that defines a default value for a plugin parameter of type float.
    """
    value = models.FloatField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='float_default')

    def __str__(self):
        return str(self.value)


class DefaultBoolParameter(models.Model):
    """
    Model class that defines a default value for a plugin parameter of type boolean.
    """
    value = models.BooleanField()
    plugin_param = models.OneToOneField(PluginParameter, on_delete=models.CASCADE,
                                        related_name='boolean_default')

    def __str__(self):
        return str(self.value)
