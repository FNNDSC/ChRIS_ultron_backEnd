
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services

from .models import ComputeResource, ComputeResourceFilter
from .models import Plugin, PluginFilter, PluginParameter
from .serializers import ComputeResourceSerializer
from .serializers import PluginSerializer, PluginParameterSerializer


class ComputeResourceList(generics.ListAPIView):
    """
    A view for the collection of compute resources.
    """
    serializer_class = ComputeResourceSerializer
    queryset = ComputeResource.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(ComputeResourceList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('computeresource-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'feeds': reverse('feed-list', request=request)}
        return services.append_collection_links(response, links)


class ComputeResourceListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of compute resources resulting from a query search.
    """
    serializer_class = ComputeResourceSerializer
    queryset = ComputeResource.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = ComputeResourceFilter


class ComputeResourceDetail(generics.RetrieveAPIView):
    """
    A compute resource view.
    """
    serializer_class = ComputeResourceSerializer
    queryset = ComputeResource.objects.all()
    permission_classes = (permissions.IsAuthenticated,)


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


class PluginComputeResourceList(generics.ListAPIView):
    """
    A view for a plugin-specific collection of compute resources.
    """
    queryset = Plugin.objects.all()
    serializer_class = ComputeResourceSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the compute resources for the queried plugin.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_computeresources_queryset()
        response = services.get_list_response(self, queryset)
        plugin = self.get_object()
        links = {'plugin': reverse('plugin-detail', request=request,
                                   kwargs={"pk": plugin.id})}
        return services.append_collection_links(response, links)

    def get_computeresources_queryset(self):
        """
        Custom method to get the actual compute resources queryset for the plugin.
        """
        plugin = self.get_object()
        return plugin.compute_resources.all()


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
