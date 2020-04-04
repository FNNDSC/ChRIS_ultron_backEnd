
from django.contrib import admin
from django.utils import timezone
from django import forms

from .models import Plugin, ComputeResource
from .services.manager import PluginManager


readonly_fields = [fld.name for fld in Plugin._meta.fields if
                   fld.name != 'compute_resource']


class PluginAdminForm(forms.ModelForm):
    name = forms.CharField(max_length=100, required=False)
    version = forms.CharField(max_length=10, required=False)
    url = forms.URLField(max_length=300, required=False)

    def clean(self):
        """
        Overriden to validate the full set of plugin descriptors and save the newly created
        plugin to the DB.
        """
        if self.instance.pk is None:  # create plugin operation
            pl_manager = PluginManager()
            compute_resource = self.cleaned_data.get('compute_resource')
            url = self.cleaned_data.pop('url', None)
            if url:
                try:
                    self.instance = pl_manager.add_plugin_by_url(url, compute_resource)
                    self.cleaned_data['name'] = self.instance.name  # set name form data
                except Exception as e:
                    raise forms.ValidationError(e)
            else:
                name = self.cleaned_data.get('name')
                if not name:
                    raise forms.ValidationError("A plugin's name or url is required")
                # get user-provided version (can be blank)
                version = self.cleaned_data.get('version')
                try:
                    self.instance = pl_manager.add_plugin(name, version, compute_resource)
                except Exception as e:
                    raise forms.ValidationError(e)
            self.cleaned_data['version'] = self.instance.version  # set version form data


class PluginAdmin(admin.ModelAdmin):
    form = PluginAdminForm
    list_display = ('name', 'version', 'compute_resource', 'type', 'id')
    search_fields = ['name', 'version']
    list_filter = ['compute_resource', 'type', 'creation_date', 'modification_date',
                   'category']
    change_form_template = 'admin/plugins/change_form.html'

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the required fields in the add plugin page.
        """
        self.fieldsets = [
            ('Choose associated compute resource', {'fields': ['compute_resource']}),
            ('Identify plugin by name and version', {'fields': [('name', 'version')]}),
            ('Or identify plugin by url', {'fields': ['url']}),
        ]
        self.readonly_fields = []
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all plugin's fields in the view plugin page.
        """
        self.fieldsets = [
            ('Associated compute resource', {'fields': ['compute_resource']}),
            ('Plugin properties', {'fields': readonly_fields}),
        ]
        self.readonly_fields = readonly_fields
        return admin.ModelAdmin.change_view(self, request, object_id, form_url,
                                            extra_context)

    def save_model(self, request, obj, form, change):
        """
        Overriden to properly create a plugin from the fields in the add plugin page.
        """
        if change:
            obj.modification_date = timezone.now()
        else:
            obj = form.instance
        super().save_model(request, obj, form, change)

    # def has_change_permission(self, request, obj=None):
    #     """
    #     Overriden to disable the editing of fields in the view plugin page.
    #     """
    #     return False


admin.site.register(Plugin, PluginAdmin)
admin.site.register(ComputeResource)

