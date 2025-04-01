
from rest_framework import generics
from rest_framework import permissions
from rest_framework.reverse import reverse
from rest_framework.serializers import ValidationError
from drf_spectacular.utils import extend_schema_view, extend_schema

from collectionjson import services
from plugins.models import Plugin

from .models import PluginInstance, PluginInstanceFilter, PluginInstanceSplit
from .models import StrParameter, FloatParameter, IntParameter
from .models import BoolParameter, PathParameter, UnextpathParameter
from .serializers import PARAMETER_SERIALIZERS
from .serializers import GenericParameterSerializer, PluginInstanceSplitSerializer
from .serializers import PluginInstanceSerializer
from .permissions import (IsOwnerOrChrisOrAuthenticatedReadOnlyOrPublicReadOnly,
                          IsOwnerOrReadOnly, IsAuthenticatedReadOnlyOrPublicReadOnly,
                          IsNotDeleteFSPluginInstance)
from .tasks import run_plugin_instance, cancel_plugin_instance
from .utils import run_if_ready


@extend_schema_view(
    get=extend_schema(operation_id='plugins_instances_list')
)
class PluginInstanceList(generics.ListCreateAPIView):
    """
    A view for the collection of plugin instances.
    """
    http_method_names = ['get', 'post']
    serializer_class = PluginInstanceSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """
        Overriden to remove descriptors from the request that must take their default
        value on creation.
        """
        self.request.data.pop('status', None)
        return super(PluginInstanceList, self).create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with 
        the newly created plugin instance before first saving to the DB. All the plugin 
        instance's parameters in the request are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        user = self.request.user
        # get previous plugin instance and create the new plugin instance
        request_data = serializer.context['request'].data
        previous_id = request_data.get('previous_id')
        previous = serializer.validate_previous(previous_id)
        plugin = self.get_object()

        # collect and validate parameters from the request
        parameter_serializers = []
        for parameter in plugin.parameters.all():
            if parameter.name in request_data:
                data = {'value': request_data[parameter.name]}
                param_type = parameter.type
                if param_type in ('path', 'unextpath'):
                    # these serializers need the user to be passed
                    parameter_serializer = PARAMETER_SERIALIZERS[param_type](
                        data=data, user=user)
                elif param_type == 'string' and plugin.meta.type == 'ts':
                    # these serializers need the param's name, plugin type and previous
                    parameter_serializer = PARAMETER_SERIALIZERS[param_type](
                        data=data, param_name=parameter.name, plugin_type='ts',
                        previous=previous)
                else:
                    parameter_serializer = PARAMETER_SERIALIZERS[param_type](data=data)
                parameter_serializer.is_valid(raise_exception=True)
                parameter_serializers.append((parameter, parameter_serializer))
            elif not parameter.optional:
                raise ValidationError({parameter.name: ["This field is required."]})

        # if no validation errors at this point then save to the DB
        cr_data = serializer.validated_data.get('compute_resource')
        if cr_data:
            compute_resource = plugin.compute_resources.get(name=cr_data['name'])
        else:
            compute_resource = plugin.compute_resources.first()
        plg_inst = serializer.save(owner=user, plugin=plugin, previous=previous,
                                   compute_resource=compute_resource)
        for param, param_serializer in parameter_serializers:
            param_serializer.save(plugin_inst=plg_inst, plugin_param=param)

        run_if_ready(plg_inst, previous)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of instances for the queried plugin. A document-level
        link relation and a collection+json template are also added to the response.
        """
        queryset = self.get_plugin_instances_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        # append document-level link relations
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id}),
                 'compute_resources': reverse('plugin-computeresource-list',
                                              request=request, kwargs={"pk": plugin.id})
                 }
        response = services.append_collection_links(response, links)
        # append write template
        param_names = plugin.get_plugin_parameter_names()
        template_data = {'title': '', 'compute_resource_name': '', 'previous_id': '',
                         'cpu_limit': '', 'memory_limit': '', 'number_of_workers': '',
                         'gpu_limit': ''}
        for name in param_names:
            template_data[name] = ''
        return services.append_collection_template(response, template_data)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get the actual plugin instances' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.instances.all())


@extend_schema_view(
    get=extend_schema(operation_id='all_plugins_instances_list')
)
class AllPluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of all plugin instances.
    """
    http_method_names = ['get']
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add a query list and document-level link relation to the response.
        """
        response = super(AllPluginInstanceList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('allplugininstance-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'plugins': reverse('plugin-list', request=request)}
        return services.append_collection_links(response, links)


class AllPluginInstanceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugin instances resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PluginInstanceFilter

        
class PluginInstanceDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A plugin instance view.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (IsOwnerOrChrisOrAuthenticatedReadOnlyOrPublicReadOnly,
                          IsNotDeleteFSPluginInstance,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to add a collection+json template to the response.
        """
        response = super(PluginInstanceDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'title': '', 'status': ''}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove descriptors that are not allowed to be updated before
        serializer validation.
        """
        data = self.request.data
        data.pop('gpu_limit', None)
        data.pop('number_of_workers', None)
        data.pop('cpu_limit', None)
        data.pop('memory_limit', None)
        return super(PluginInstanceDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to cancel this plugin instance and all its descendants' execution.
        """
        if 'status' in self.request.data:
            instance = self.get_object()
            if instance.status != 'cancelled':
                descendants = instance.get_descendant_instances()
                if instance.status == 'started':
                    cancel_plugin_instance.delay(instance.id)  # call async task
                for plg_inst in descendants:
                    plg_inst.status = 'cancelled'
                    plg_inst.save()

        super(PluginInstanceDetail, self).perform_update(serializer)

    def destroy(self, request, *args, **kwargs):
        """
        Overriden to cancel the plugin instance execution before deleting it. All the
        descendant instances are also cancelled before they are deleted by the DB CASCADE.
        """
        instance = self.get_object()
        descendants = instance.get_descendant_instances()
        if instance.status == 'started':
            cancel_plugin_instance(instance.id)
        for plg_inst in descendants:
            if plg_inst.status not in ('finishedSuccessfully', 'finishedWithError',
                                       'cancelled'):
                plg_inst.status = 'cancelled'
                plg_inst.save()
        return super(PluginInstanceDetail, self).destroy(request, *args, **kwargs)


class PluginInstanceDescendantList(generics.ListAPIView):
    """
    A view for the collection of plugin instances that are a descendant of this plugin
    instance.
    """
    http_method_names = ['get']
    serializer_class = PluginInstanceSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the plugin instance descendants.
        """
        queryset = self.get_descendants_queryset()
        return services.get_list_response(self, queryset)

    def get_descendants_queryset(self):
        """
        Custom method to get the actual descendants queryset.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.get_descendant_instances())


class PluginInstanceSplitList(generics.ListCreateAPIView):
    """
    A view for the collection of splits for a plugin instance.
    """
    http_method_names = ['get', 'post']
    serializer_class = PluginInstanceSplitSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrReadOnly,)

    def perform_create(self, serializer):
        """
        Overriden to associate a plugin instance and a list of newly created
        'pl-topologicalcopy' plugin instance ids with the newly created split before
        first saving to the DB.
        """
        user = self.request.user
        instance = self.get_object()
        plg_topologcopy = Plugin.objects.filter(meta__name='pl-topologicalcopy').first()

        cr_name = serializer.validated_data.pop('compute_resource_name', '')
        if cr_name:
            compute_resource = plg_topologcopy.compute_resources.get(name=cr_name)
        else:
            compute_resource = plg_topologcopy.compute_resources.first()

        plg_filter_param = plg_topologcopy.parameters.get(name='filter')
        plg_plugininstances_param = plg_topologcopy.parameters.get(name='plugininstances')

        created_plg_inst_ids = []
        filter_list = serializer.validated_data.get('filter', '').split(',')
        for f in filter_list:
            plg_inst = PluginInstance.objects.create(
                plugin=plg_topologcopy, owner=user, previous=instance,
                compute_resource=compute_resource
            )
            StrParameter.objects.create(plugin_inst=plg_inst,
                                        plugin_param=plg_plugininstances_param,
                                        value=str(instance.id))
            if f:
                StrParameter.objects.create(plugin_inst=plg_inst,
                                            plugin_param=plg_filter_param,
                                            value=f)
            run_if_ready(plg_inst, instance)
            created_plg_inst_ids.append(str(plg_inst.id))

        serializer.save(
            plugin_inst=instance, created_plugin_inst_ids=','.join(created_plg_inst_ids)
        )

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of splits for the queried plugin instance.
        A document-level link relation and a collection+json template are also added
        to the response.
        """
        queryset = self.get_splits_queryset()
        response = services.get_list_response(self, queryset)
        instance = self.get_object()
        # append document-level link relations
        links = {'plugin_inst': reverse('plugininstance-detail', request=request,
                                        kwargs={"pk": instance.id})}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'filter': '', 'compute_resource_name': ''}
        return services.append_collection_template(response, template_data)

    def get_splits_queryset(self):
        """
        Custom method to get the actual splits queryset.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.splits.all())


class PluginInstanceSplitDetail(generics.RetrieveAPIView):
    """
    A view for a plugin instance split.
    """
    http_method_names = ['get']
    queryset = PluginInstanceSplit.objects.all()
    serializer_class = PluginInstanceSplitSerializer
    permission_classes = (permissions.IsAuthenticated,)


class PluginInstanceParameterList(generics.ListAPIView):
    """
    A view for the collection of parameters that the plugin instance was run with.
    """
    http_method_names = ['get']
    serializer_class = GenericParameterSerializer
    queryset = PluginInstance.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the parameter values used by the queried
        plugin instance.
        """
        queryset = self.get_parameters_queryset()
        return services.get_list_response(self, queryset)

    def get_parameters_queryset(self):
        """
        Custom method to get a queryset with all the parameters regardless of their type.
        """
        instance = self.get_object()
        return self.filter_queryset(instance.get_parameter_instances())


class StrParameterDetail(generics.RetrieveAPIView):
    """
    A string parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['string']
    queryset = StrParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)
    

class IntParameterDetail(generics.RetrieveAPIView):
    """
    An integer parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['integer']
    queryset = IntParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)


class FloatParameterDetail(generics.RetrieveAPIView):
    """
    A float parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['float']
    queryset = FloatParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)
    

class BoolParameterDetail(generics.RetrieveAPIView):
    """
    A boolean parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['boolean']
    queryset = BoolParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)


class PathParameterDetail(generics.RetrieveAPIView):
    """
    A path parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['path']
    queryset = PathParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)


class UnextpathParameterDetail(generics.RetrieveAPIView):
    """
    A unextpath parameter view.
    """
    http_method_names = ['get']
    serializer_class = PARAMETER_SERIALIZERS['unextpath']
    queryset = UnextpathParameter.objects.all()
    permission_classes = (IsAuthenticatedReadOnlyOrPublicReadOnly,)
