
from rest_framework import generics, permissions
from rest_framework.reverse import reverse

from collectionjson import services
from plugins.serializers import PluginSerializer

from .models import Pipeline, PipelineFilter, PluginPiping
from .models import DefaultPipingPathParameter, DefaultPipingStrParameter
from .models import DefaultPipingIntParameter, DefaultPipingFloatParameter
from .models import DefaultPipingBoolParameter
from .serializers import PipelineSerializer, PluginPipingSerializer
from .serializers import DEFAULT_PIPING_PARAMETER_SERIALIZERS
from .serializers import GenericDefaultPipingParameterSerializer
from .permissions import IsOwnerOrChrisOrNotLockedReadOnly, IsChirsOrOwnerOrNotLocked
from .permissions import IsChirsOrOwnerAndLockedOrNotLockedReadOnly


class PipelineList(generics.ListCreateAPIView):
    """
    A view for the collection of pipelines.
    """
    serializer_class = PipelineSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the pipelines
        that are accessible to the currently authenticated user.
        """
        return Pipeline.get_accesible_pipelines(self.request.user)

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
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = PipelineFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the pipelines
        that are accessible to the currently authenticated user.
        """
        return Pipeline.get_accesible_pipelines(self.request.user)


class PipelineDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A pipeline view.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(PipelineDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'name': "", 'authors': "", 'category': "", 'description': ""}
        pipeline = self.get_object()
        if pipeline.locked:
            template_data['locked'] = ""
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to include required parameters if not in the request and delete
        'locked' parameter if the pipeline is not locked.
        """
        pipeline = self.get_object()
        if not pipeline.locked and 'locked' in request.data:
            # this pipeline was made available to the public so it cannot be locked
            del request.data['locked']
        if 'name' not in request.data:
            request.data['name'] = pipeline.name  # name is required in the serializer
        return super(PipelineDetail, self).update(request, *args, **kwargs)


class PipelinePluginList(generics.ListAPIView):
    """
    A view for a pipeline-specific collection of plugins.
    """
    queryset = Pipeline.objects.all()
    serializer_class = PluginSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrNotLockedReadOnly,)

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
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrNotLockedReadOnly,)

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
        return pipeline.plugin_pipings.all()


class PipelineDefaultParameterList(generics.ListAPIView):
    """
    A view for the collection of pipeline-specific plugin parameters' defaults.
    """
    queryset = Pipeline.objects.all()
    serializer_class = GenericDefaultPipingParameterSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrNotLockedReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list with all the default parameter values used by the
        queried pipeline.
        """
        queryset = self.get_default_parameters_queryset()
        response = services.get_list_response(self, queryset)
        return response

    def get_default_parameters_queryset(self):
        """
        Custom method to get a queryset with all the default parameters regardless their
        type.
        """
        pipeline = self.get_object()
        queryset = []
        queryset.extend(list(DefaultPipingPathParameter.objects.filter(
            plugin_piping__pipeline=pipeline)))
        queryset.extend(list(DefaultPipingStrParameter.objects.filter(
            plugin_piping__pipeline=pipeline)))
        queryset.extend(list(DefaultPipingIntParameter.objects.filter(
            plugin_piping__pipeline=pipeline)))
        queryset.extend(list(DefaultPipingFloatParameter.objects.filter(
            plugin_piping__pipeline=pipeline)))
        queryset.extend(list(DefaultPipingBoolParameter.objects.filter(
            plugin_piping__pipeline=pipeline)))
        return self.filter_queryset(queryset)


class PluginPipingDetail(generics.RetrieveAPIView):
    """
    A plugin piping view.
    """
    queryset = PluginPiping.objects.all()
    serializer_class = PluginPipingSerializer
    permission_classes = (permissions.IsAuthenticated, IsChirsOrOwnerOrNotLocked,)


class DefaultPipingStrParameterDetail(generics.RetrieveUpdateAPIView):
    """
    A view for a string default value for a plugin parameter in a pipeline's
    plugin piping.
    """
    serializer_class = DEFAULT_PIPING_PARAMETER_SERIALIZERS['string']
    queryset = DefaultPipingStrParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChirsOrOwnerAndLockedOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(DefaultPipingStrParameterDetail, self).retrieve(
            request, *args, **kwargs)
        template_data = {"value": ""}
        return services.append_collection_template(response, template_data)


class DefaultPipingIntParameterDetail(generics.RetrieveUpdateAPIView):
    """
    A view for an integer default value for a plugin parameter in a pipeline's
    plugin piping.
    """
    serializer_class = DEFAULT_PIPING_PARAMETER_SERIALIZERS['integer']
    queryset = DefaultPipingIntParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChirsOrOwnerAndLockedOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(DefaultPipingIntParameterDetail, self).retrieve(
            request, *args, **kwargs)
        template_data = {"value": ""}
        return services.append_collection_template(response, template_data)


class DefaultPipingFloatParameterDetail(generics.RetrieveUpdateAPIView):
    """
    A view for a float default value for a plugin parameter in a pipeline's
    plugin piping.
    """
    serializer_class = DEFAULT_PIPING_PARAMETER_SERIALIZERS['float']
    queryset = DefaultPipingFloatParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChirsOrOwnerAndLockedOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(DefaultPipingFloatParameterDetail, self).retrieve(
            request, *args, **kwargs)
        template_data = {"value": ""}
        return services.append_collection_template(response, template_data)


class DefaultPipingBoolParameterDetail(generics.RetrieveUpdateAPIView):
    """
    A view for a boolean default value for a plugin parameter in a pipeline's
    plugin piping.
    """
    serializer_class = DEFAULT_PIPING_PARAMETER_SERIALIZERS['boolean']
    queryset = DefaultPipingBoolParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChirsOrOwnerAndLockedOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(DefaultPipingBoolParameterDetail, self).retrieve(
            request, *args, **kwargs)
        template_data = {"value": ""}
        return services.append_collection_template(response, template_data)


class DefaultPipingPathParameterDetail(generics.RetrieveUpdateAPIView):
    """
    A view for a path default value for a plugin parameter in a pipeline's
    plugin piping.
    """
    serializer_class = DEFAULT_PIPING_PARAMETER_SERIALIZERS['path']
    queryset = DefaultPipingPathParameter.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChirsOrOwnerAndLockedOrNotLockedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(DefaultPipingPathParameterDetail, self).retrieve(
            request, *args, **kwargs)
        template_data = {"value": ""}
        return services.append_collection_template(response, template_data)
