
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services

from .models import Plugin, PluginFilter, PluginParameter
from .models import Pipeline, PipelineFilter, PluginPiping
from .serializers import PluginSerializer,  PluginParameterSerializer
from .serializers import PipelineSerializer, PluginPipingSerializer

class PluginList(generics.ListAPIView):
    """
    A view for the collection of plugins.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(PluginList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('plugin-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'feeds': reverse('feed-list', request=request)}    
        return services.append_collection_links(response, links)


class PluginListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of plugins resulting from a query search.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PluginFilter
        

class PluginDetail(generics.RetrieveAPIView):
    """
    A plugin view.
    """
    serializer_class = PluginSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class PluginParameterList(generics.ListAPIView):
    """
    A view for the collection of plugin parameters.
    """
    serializer_class = PluginParameterSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return the list of parameters for the queried plugin.
        A document-level link relation is also added to the response.
        """
        queryset = self.get_plugin_parameters_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}    
        return services.append_collection_links(response, links)

    def get_plugin_parameters_queryset(self):
        """
        Custom method to get the actual plugin parameters' queryset.
        """
        plugin = self.get_object()
        return self.filter_queryset(plugin.parameters.all())

    
class PluginParameterDetail(generics.RetrieveAPIView):
    """
    A plugin parameter view.
    """
    serializer_class = PluginParameterSerializer
    queryset = PluginParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


class PipelineList(generics.ListCreateAPIView):
    """
    A view for the collection of pipelines.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the pipeline before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to add document-level link relations, query list and a collection+json
        template to the response.
        """
        response = super(PipelineList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('pipeline-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'plugins': reverse('plugin-list', request=request)}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'name': "", 'authors': "", 'category': "", 'description': "",
                         'plugin_id_tree': "", 'plugin_inst_id': ""}
        return services.append_collection_template(response, template_data)


class PipelineListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of pipelines resulting from a query search.
    """
    serializer_class = PipelineSerializer
    queryset = Pipeline.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PipelineFilter


class PipelineDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A pipeline view.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(PipelineDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'name': "", 'authors': "", 'category': "", 'description': ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to include required parameters if not in the request.
        """
        pipeline = self.get_object()
        if not 'name' in request.data:
            request.data['name'] = pipeline.name # name is required in the serializer
        request.data['plugin_id_tree'] = str([plg.id for plg in pipeline.plugins.all()])
        return super(PipelineDetail, self).update(request, *args, **kwargs)


class PipelinePluginList(generics.ListAPIView):
    """
    A view for a pipeline-specific collection of plugins.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PluginSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the plugins for the queried pipeline.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_plugins_queryset()
        response = services.get_list_response(self, queryset)
        pipeline = self.get_object()
        links = {'pipeline': reverse('pipeline-detail', request=request,
                                   kwargs={"pk": pipeline.id})}
        return services.append_collection_links(response, links)

    def get_plugins_queryset(self):
        """
        Custom method to get the actual plugins queryset for the queried pipeline.
        """
        pipeline = self.get_object()
        return pipeline.plugins.all()


class PipelinePluginPipingList(generics.ListAPIView):
    """
    A view for the collection of pipeline-specific plugin pipings.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PluginPipingSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the plugin pipings for the queried pipeline.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_plugin_pipings_queryset()
        response = services.get_list_response(self, queryset)
        pipeline = self.get_object()
        links = {'pipeline': reverse('pipeline-detail', request=request,
                                   kwargs={"pk": pipeline.id})}
        return services.append_collection_links(response, links)

    def get_plugin_pipings_queryset(self,):
        """
        Custom method to get the actual plugin pipings queryset for the pipeline.
        """
        pipeline = self.get_object()
        return PluginPiping.objects.filter(pipeline=pipeline)


class PluginPipingDetail(generics.RetrieveAPIView):
    """
    A plugin piping view.
    """
    queryset = PluginPiping.objects.all()
    serializer_class = PluginPipingSerializer
    permission_classes = (permissions.IsAuthenticated,)
