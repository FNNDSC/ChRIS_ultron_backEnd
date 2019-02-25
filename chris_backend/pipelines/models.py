
from django.db import models

import django_filters
from django_filters.rest_framework import FilterSet

from plugins.models import Plugin, PluginParameter


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

    def get_pipings_parameters_names(self):
        """
        Custom method to get the list of all associated plugin pipings. The name of the
        parameters is transformed to have the plugin id, piping id and previous piping
        id as a prefix.
        """
        pipings = self.plugin_pipings.all()
        param_names = []
        for pip in pipings:
            plg = pip.plugin
            prev_pip_id = pip.previous.id if pip.previous else 'null'
            # param name becomes <plugin.id>_<piping.id>_<previous_piping.id>_<param.name>
            param_names.extend(['%s_%s_%s_%s' % (plg.id, pip.id, prev_pip_id, param.name)
                                for param in plg.parameters.all()])
        return param_names

    def get_pipings_tree(self):
        """
        Custom method to return a dictionary containing a dictionary representing a tree
        of pipings and the id of the piping that is the root of the tree. The keys of the
        dictionary tree are the pipings' ids and the values are dictionaries containing
        the piping and the list of child pipings' ids.
        """
        pipings = list(self.plugin_pipings.all())
        root_pip = [pip for pip in pipings if not pip.previous][0]
        root_id = root_pip.id
        tree = {}
        tree[root_id] = {'piping': root_pip, 'child_ids':[]}
        for pip in pipings:
            if pip.id not in tree:
                tree[pip.id] = {'piping': pip, 'child_ids': []}
                prev_id = pip.previous.id
                if prev_id in tree:
                    tree[prev_id]['child_ids'].append(pip.id)
                else:
                    tree[prev_id] = {'piping': pip.previous, 'child_ids': [pip.id]}
        return {'root_id': root_id, 'tree': tree}

    def checkParameterDefaultValues(self):
        """
        Custom method to raise an exception if any of the plugin parameters associated to
        any of the pipings in the pipeline doesn't have a default value.
        """
        for piping in self.plugin_pipings.all():
            piping.checkParameterDefaultValues()

    @staticmethod
    def get_accesible_pipelines(user):
        """
        Custom method to get a filtered queryset with all the pipelines that are
        accessible to a given user (not locked or otherwise own by the user).
        """
        queryset = Pipeline.objects.all()
        # if the user is chris then return all the pipelines in the queryset
        if user.username == 'chris':
            return queryset
        # construct the full lookup expression.
        lookup = models.Q(locked=False) | models.Q(owner=user)
        return queryset.filter(lookup)


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
            # use plugin's parameter default for piping's default
            default_piping_param.value = default
            default_piping_param.save()

    def checkParameterDefaultValues(self):
        """
        Custom method to raise an exception if any of the plugin parameters associated to
        the piping doesn't have a default value.
        """
        for type in DEFAULT_PIPING_PARAMETER_MODELS:
            typed_parameters = getattr(self, type + '_param')
            for parameter in typed_parameters.all():
                if parameter.value is None:
                    raise ValueError('A default is required for parameter %s'
                                     % parameter.plugin_param.name)


class DefaultPipingStrParameter(models.Model):
    value = models.CharField(max_length=200, null=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='string_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='string_piping_default')

    def __str__(self):
        return self.value


class DefaultPipingIntParameter(models.Model):
    value = models.IntegerField(null=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='integer_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='integer_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingFloatParameter(models.Model):
    value = models.FloatField(null=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='float_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='float_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingBoolParameter(models.Model):
    value = models.BooleanField(null=True)
    plugin_piping = models.ForeignKey(PluginPiping, on_delete=models.CASCADE,
                                    related_name='boolean_param')
    plugin_param = models.ForeignKey(PluginParameter, on_delete=models.CASCADE,
                                     related_name='boolean_piping_default')

    def __str__(self):
        return str(self.value)


class DefaultPipingPathParameter(models.Model):
    value = models.CharField(max_length=200, null=True)
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
