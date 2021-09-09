
from django.contrib import admin
from django.utils import timezone
from django.urls import path
from django.shortcuts import render
from django import forms
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.contrib import messages
from rest_framework import generics, permissions, serializers
from rest_framework.reverse import reverse

from collectionjson import services

from .models import PluginMeta, Plugin, ComputeResource
from .serializers import ComputeResourceSerializer, PluginSerializer
from .services.manager import PluginManager


plugin_readonly_fields = [fld.name for fld in Plugin._meta.fields if
                          fld.name != 'compute_resources']


class ComputeResourceAdmin(admin.ModelAdmin):
    readonly_fields = ['creation_date', 'modification_date']
    list_display = ('name', 'compute_url', 'description', 'id')
    list_filter = ['name', 'creation_date', 'modification_date']
    search_fields = ['name', 'description']

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the required fields in the add compute resource page.
        """
        self.fields = ['name', 'compute_url', 'description']
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all compute resources's fields in the compute resource page.
        """
        self.fields = ['name', 'compute_url', 'description', 'creation_date',
                       'modification_date']
        return admin.ModelAdmin.change_view(self, request, object_id, form_url,
                                            extra_context)

    def save_model(self, request, obj, form, change):
        """
        Overriden to set the modification date.
        """
        if change:
            obj.modification_date = timezone.now()
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """
        Overriden to prevent deleting compute resources that would leave orphan
        plugins after the operation.
        """
        try:
            super().delete_model(request, obj)
        except ValidationError as e:
            messages.set_level(request, messages.ERROR)
            messages.error(request, e.message)

    def delete_queryset(self, request, queryset):
        """
        Overriden to prevent deleting compute resources that would leave orphan
        plugins after the operation. This customizes the deletion process for the
        “delete selected objects” action.
        """
        for compute_resource in queryset:
            plg_ids = compute_resource.get_plugins_with_self_as_single_compute_resource()
            if plg_ids:
                messages.set_level(request, messages.ERROR)
                msg = "Can not delete compute resource '%s'. Please do not check it " \
                      "for the delete or otherwise first register its associated " \
                      "plugins with IDs %s with another compute resource."
                messages.error(request, msg % (compute_resource, plg_ids))
                return None
        super().delete_queryset(request, queryset)


class PluginMetaAdmin(admin.ModelAdmin):
    readonly_fields = ['name', 'title', 'stars', 'public_repo', 'license', 'type', 'icon',
                       'category', 'authors', 'documentation', 'creation_date',
                       'modification_date']
    list_display = ('name', 'type', 'id')
    list_filter = ['type', 'creation_date', 'modification_date', 'category']
    search_fields = ['name']

    def has_change_permission(self, request, obj=None):
        """
        Overriden to disable the editing of fields in the view plugin meta page.
        """
        return False

    def has_add_permission(self, request):
        """
        Overriden to remove the add plugin meta button.
        """
        return False


class UploadFileForm(forms.Form):
    file = forms.FileField()


class PluginAdminForm(forms.ModelForm):
    name = forms.CharField(max_length=100, required=False)
    version = forms.CharField(max_length=10, required=False)
    url = forms.URLField(max_length=300, required=False)

    def clean(self):
        """
        Overriden to validate the full set of plugin descriptors and save the newly
        created plugin to the DB.
        """
        if self.instance.pk is None:  # create plugin operation
            pl_manager = PluginManager()
            compute_resources = self.cleaned_data.get('compute_resources')
            if compute_resources is None:
                raise forms.ValidationError('Please choose a compute resource')
            url = self.cleaned_data.pop('url', None)
            cr = compute_resources[0]
            if url:
                try:
                    self.instance = pl_manager.register_plugin_by_url(url, cr.name)
                except Exception as e:
                    raise forms.ValidationError(e)
            else:
                name = self.cleaned_data.get('name')
                if not name:
                    raise forms.ValidationError("A plugin's name or url is required")
                # get user-provided version (can be blank)
                version = self.cleaned_data.get('version')
                try:
                    self.instance = pl_manager.register_plugin(name, version, cr.name)
                except Exception as e:
                    raise forms.ValidationError(e)
            # reset form validated data
            self.cleaned_data['name'] = self.instance.meta.name
            self.cleaned_data['version'] = self.instance.version
            current_compute_resources = list(self.instance.compute_resources.all())
            compute_resources = list(compute_resources) + current_compute_resources
            self.instance.compute_resources.set(compute_resources)
            self.cleaned_data['compute_resources'] = self.instance.compute_resources.all()


class PluginAdmin(admin.ModelAdmin):
    form = PluginAdminForm
    list_display = ('meta', 'version', 'id')
    search_fields = ['meta', 'version']
    list_filter = ['meta', 'creation_date']
    change_form_template = 'admin/plugins/plugin/change_form.html'
    change_list_template = 'admin/plugins/plugin/change_list.html'

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the required fields in the add plugin page.
        """
        self.readonly_fields = []
        self.fieldsets = [
            ('Compute resources', {'fields': ['compute_resources']}),
            ('Identify plugin by name and version', {'fields': [('name', 'version')]}),
            ('Or identify plugin by url', {'fields': ['url']}),
        ]
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all plugin's fields in the view plugin page.
        """
        self.readonly_fields = [fl for fl in plugin_readonly_fields]
        self.readonly_fields.append('get_registered_compute_resources')
        self.fieldsets = [
            ('Compute resources', {'fields': ['compute_resources',
                                              'get_registered_compute_resources']}),
            ('Plugin properties', {'fields': plugin_readonly_fields}),
        ]
        return admin.ModelAdmin.change_view(self, request, object_id, form_url,
                                            extra_context)

    # def save_model(self, request, obj, form, change):
    #     """
    #     Overriden to set the modification date..
    #     """
    #     if change:
    #         obj.modification_date = timezone.now()
    #     super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super(PluginAdmin, self).get_urls()
        custom_urls = [
            path('add_plugins/',
                 self.admin_site.admin_view(self.add_plugins_from_file_view),
                 name="add_plugins"),
        ]
        return custom_urls + urls

    def delete_model(self, request, obj):
        """
        Overriden to delete the associated meta if this is the last associated plugin.
        """
        meta = obj.meta
        super().delete_model(request, obj)
        if meta.plugins.count() == 0:
            meta.delete()  # delete the meta if this is the last associated plugin

    def delete_queryset(self, request, queryset):
        """
        Overriden to delete plugin metas if their last associated plugin is deleted.
        This customizes the deletion process for the “delete selected objects” action.
        """
        pl_metas = []
        for plugin in queryset:
            if plugin.meta.plugins.count() == 1:
                pl_metas.append(plugin.meta)
        super().delete_queryset(request, queryset)
        for meta in pl_metas:
            meta.delete()

    def add_plugins_from_file_view(self, request):
        """
        Custom view to handle the add plugins from file page.
        """
        # custom view should return an HttpResponse
        context = dict(
            # Include common variables for rendering the admin template.
            self.admin_site.each_context(request),
            # Anything else you want in the context...
            opts=self.opts,
        )
        if request.method == 'POST':
            file_form = UploadFileForm(request.POST, request.FILES)
            if file_form.is_valid():
                # handle uploaded file (request.FILES['file'])
                summary = self.register_plugins_from_file(request.FILES['file'])
                context['summary'] = summary
                return render(request,
                              'admin/plugins/plugin/add_plugins_from_file_result.html',
                              context)
        else:
            file_form = UploadFileForm()
        context['file_form'] = file_form
        return render(request,
                      'admin/plugins/plugin/add_plugins_from_file.html',
                      context)

    def register_plugins_from_file(self, f):
        """
        Custom method to register plugins from a text file f. The first string of each
        line of the file is the plugin's name or url, the second string is the version
        (can be empty) and the third string is the associated compute environment. Any
        plugin in the file must already be previously uploaded to the ChRIS store.
        """
        summary = {'success': [], 'error': []}
        val = URLValidator()
        pl_manager = PluginManager()
        for line in f:
            try:  # check file must be a text file
                strings = line.decode().strip().split()
            except UnicodeDecodeError:
                summary = {'success': [], 'error': []}
                break
            if len(strings) == 1:
                summary['error'].append({'plugin_name': strings[0],
                                         'code': 'Missing compute resource identifier.'})
            elif len(strings) > 1:
                try:
                    val(strings[0])  # check whether the first string is a url
                except ValidationError:
                    # register by name
                    plg_name = strings[0]
                    if len(strings) == 2:
                        plg_version = None
                        compute_resource = strings[1]
                    else:
                        plg_version = strings[1]
                        compute_resource = strings[2]
                    try:
                        pl_manager.register_plugin(plg_name, plg_version,
                                                   compute_resource)
                    except Exception as e:
                        summary['error'].append({'plugin_name': plg_name, 'code': str(e)})
                    else:
                        summary['success'].append({'plugin_name': plg_name})
                else:
                    # register by url
                    plg_url = strings[0]
                    compute_resource = strings[1]
                    try:
                        pl_manager.register_plugin_by_url(plg_url, compute_resource)
                    except Exception as e:
                        summary['error'].append({'plugin_name': plg_url, 'code': str(e)})
                    else:
                        summary['success'].append({'plugin_name': plg_url})
        return summary


class ComputeResourceAdminList(generics.ListCreateAPIView):
    """
    A JSON view for the collection of compute resources that can be used by ChRIS admins
    to add a new compute resource through a REST API (alternative to the HTML-based admin
    site).
    """
    http_method_names = ['get', 'post']
    serializer_class = ComputeResourceSerializer
    queryset = ComputeResource.objects.all()
    permission_classes = (permissions.IsAdminUser,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template to the response.
        """
        response = super(ComputeResourceAdminList, self).list(request, *args, **kwargs)
        # append write template
        template_data = {'name': '', 'compute_url': '', 'description': ''}
        return services.append_collection_template(response, template_data)


class PluginAdminSerializer(PluginSerializer):
    """
    A Plugin serializer for the PluginAdminList JSON view.
    """
    plugin_store_url = serializers.URLField(write_only=True)
    compute_name = serializers.CharField(max_length=100, write_only=True)
    version = serializers.CharField(required=False)
    dock_image = serializers.CharField(required=False)
    execshell = serializers.CharField(required=False)
    selfpath = serializers.CharField(required=False)
    selfexec = serializers.CharField(required=False)

    class Meta(PluginSerializer.Meta):
        fields = PluginSerializer.Meta.fields + ('plugin_store_url', 'compute_name')

    def validate(self, data):
        """
        Overriden to validate and register a plugin from a ChRIS store with a compute
        resource associated with this ChRIS instance.
        """
        # remove write_only fields that not part of the Plugin model
        cr_name = data.pop('compute_name')
        plugin_store_url = data.pop('plugin_store_url')
        pl_manager = PluginManager()
        try:
            self.instance = pl_manager.register_plugin_by_url(plugin_store_url, cr_name)
        except Exception as e:
            raise serializers.ValidationError({'non_field_errors': [str(e)]})
        return data


class PluginAdminList(generics.ListCreateAPIView):
    """
    A JSON view for the collection of plugins that can be used by ChRIS admins to
    register plugins through a REST API (alternative to the HTML-based admin site).
    """
    http_method_names = ['get', 'post']
    serializer_class = PluginAdminSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAdminUser,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json template
        to the response.
        """
        response = super(PluginAdminList, self).list(request, *args, **kwargs)
        # append document-level link relations
        links = {'compute_resources': reverse('admin-computeresource-list',
                                              request=request)}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {'plugin_store_url': '', 'compute_name': ''}
        return services.append_collection_template(response, template_data)


admin.site.register(ComputeResource, ComputeResourceAdmin)
admin.site.register(PluginMeta, PluginMetaAdmin)
admin.site.register(Plugin, PluginAdmin)
