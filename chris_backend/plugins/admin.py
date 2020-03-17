
from django.contrib import admin
from django.utils import timezone
from django import forms

from .models import Plugin, ComputeResource
from .services.manager import PluginManager


add_view_fields = ['name', 'version', 'compute_resource']
readonly_fields = [fld.name for fld in Plugin._meta.fields if
                   fld.name != 'compute_resource']
all_fields = ['compute_resource'] + readonly_fields


class PluginAdminForm(forms.ModelForm):

    def clean(self):
        """
        Overriden to validate the full set of plugin descriptors and save the newly created
        plugin to the DB.
        """
        if self.instance.pk is None:  # create plugin operation
            name = self.cleaned_data['name']
            version = self.cleaned_data['version']
            compute_resource = self.cleaned_data['compute_resource']
            pl_manager = PluginManager()
            try:
                self.instance = pl_manager.add_plugin(name, version, compute_resource)
            except Exception as e:
                raise forms.ValidationError(e)


class PluginAdmin(admin.ModelAdmin):
    form = PluginAdminForm
    list_display = ('name', 'version', 'compute_resource', 'type', 'id')
    search_fields = ['name', 'version']
    list_filter = ['compute_resource', 'type', 'creation_date', 'modification_date',
                   'category']

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the required fields in the add plugin page.
        """
        self.fields = add_view_fields
        self.readonly_fields = []
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all plugin's fields in the view plugin page.
        """
        self.fields = all_fields
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

