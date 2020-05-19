
from django.contrib import admin
from django.utils import timezone
from django.urls import path
from django.shortcuts import render
from django import forms
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.contrib import messages

from .models import Plugin, ComputeResource
from .services.manager import PluginManager


plugin_readonly_fields = [fld.name for fld in Plugin._meta.fields if
                          fld.name != 'compute_resources']


class ComputeResourceAdmin(admin.ModelAdmin):
    readonly_fields = ['creation_date', 'modification_date']
    list_display = ('name', 'description', 'id')
    list_filter = ['name', 'creation_date', 'modification_date']
    search_fields = ['name', 'description']

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the required fields in the add compute resource page.
        """
        self.fields = ['name', 'description']
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all compute resources's fields in the compute resource page.
        """
        self.fields = ['name', 'description', 'creation_date', 'modification_date']
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
        return super().delete_queryset(request, queryset)


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
            compute_resources = list(self.cleaned_data.get('compute_resources'))
            url = self.cleaned_data.pop('url', None)
            if url:
                try:
                    cr = compute_resources.pop()
                    self.instance = pl_manager.register_plugin_by_url(url, cr.name)
                    name = self.instance.name
                    version = self.instance.version
                    for cr in compute_resources:
                        # registering by (name, version) avoids contacting the ChRIS store
                        # when the plugin already exists in ChRIS
                        self.instance = pl_manager.register_plugin(name, version, cr.name)
                except Exception as e:
                    raise forms.ValidationError(e)
            else:
                name = self.cleaned_data.get('name')
                if not name:
                    raise forms.ValidationError("A plugin's name or url is required")
                # get user-provided version (can be blank)
                version = self.cleaned_data.get('version')
                try:
                    cr = compute_resources.pop()
                    self.instance = pl_manager.register_plugin(name, version, cr.name)
                    version = self.instance.version
                    for cr in compute_resources:
                        self.instance = pl_manager.register_plugin(name, version, cr.name)
                except Exception as e:
                    raise forms.ValidationError(e)
            # reset form validated data
            self.cleaned_data['name'] = name
            self.cleaned_data['version'] = version
            self.cleaned_data['compute_resources'] = self.instance.compute_resources.all()


class PluginAdmin(admin.ModelAdmin):
    form = PluginAdminForm
    list_display = ('name', 'version', 'type', 'id')
    search_fields = ['name', 'version']
    list_filter = ['type', 'creation_date', 'modification_date', 'category']
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
        self.readonly_fields = [f for f in plugin_readonly_fields]
        self.readonly_fields.append('get_registered_compute_resources')
        self.fieldsets = [
            ('Compute resources', {'fields': ['compute_resources',
                                              'get_registered_compute_resources']}),
            ('Plugin properties', {'fields': plugin_readonly_fields}),
        ]
        return admin.ModelAdmin.change_view(self, request, object_id, form_url,
                                            extra_context)

    def save_model(self, request, obj, form, change):
        """
        Overriden to properly create a plugin from the fields in the add plugin page.
        """
        if change:
            obj.modification_date = timezone.now()
        super().save_model(request, obj, form, change)

    # def has_change_permission(self, request, obj=None):
    #     """
    #     Overriden to disable the editing of fields in the view plugin page.
    #     """
    #     return False

    def get_urls(self):
        urls = super(PluginAdmin, self).get_urls()
        custom_urls = [
            path('add_plugins/',
                 self.admin_site.admin_view(self.add_plugins_from_file_view),
                 name="add_plugins"),
        ]
        return custom_urls + urls

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


admin.site.register(Plugin, PluginAdmin)
admin.site.register(ComputeResource, ComputeResourceAdmin)
