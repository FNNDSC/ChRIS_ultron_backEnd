
import json
import re

from django.contrib import admin
from django.utils import timezone
from django.urls import path
from django.shortcuts import render
from django import forms
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib import messages
from rest_framework import generics, permissions, serializers
from rest_framework.reverse import reverse

from collectionjson import services

from .models import PluginMeta, Plugin, ComputeResource, TYPES
from .fields import CPUInt, MemoryInt
from .serializers import (ComputeResourceSerializer, PluginMetaSerializer,
                          PluginSerializer, PluginParameterSerializer,
                          DEFAULT_PARAMETER_SERIALIZERS)
from .services.manager import PluginManager


plugin_readonly_fields = [fld.name for fld in Plugin._meta.fields if
                          fld.name != 'compute_resources']


class ComputeResourceAdmin(admin.ModelAdmin):
    readonly_fields = ['creation_date', 'modification_date']
    list_display = ('name', 'compute_url', 'compute_innetwork', 'description', 'id')
    list_filter = ['name', 'creation_date', 'modification_date']
    search_fields = ['name', 'description']

    def add_view(self, request, form_url='', extra_context=None):
        """
        Overriden to only show the read/write fields in the add compute resource page.
        """
        self.fields = ['name', 'compute_url', 'compute_auth_url', 'compute_user',
                       'compute_password', 'compute_auth_token', 'compute_innetwork',
                       'description', 'max_job_exec_seconds']
        return admin.ModelAdmin.add_view(self, request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Overriden to show all compute resources's fields in the compute resource page.
        """
        self.fields = ['name', 'compute_url', 'compute_auth_url', 'compute_user',
                       'compute_password', 'compute_auth_token', 'compute_innetwork',
                       'description', 'max_job_exec_seconds', 'creation_date',
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
    search_fields = ['meta__name', 'version']
    list_filter = ['meta__name', 'creation_date']
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
        template_data = {'name': '', 'compute_url': '', 'compute_auth_url': '',
                         'compute_user': '', 'compute_password': '',
                         'compute_auth_token': '', 'compute_innetwork': '',
                         'description': '', 'max_job_exec_seconds': ''}
        return services.append_collection_template(response, template_data)


class ComputeResourceAdminDetail(generics.RetrieveDestroyAPIView):
    """
    A JSON view for a compute resource that can be used by ChRIS admins to delete the
    compute resource through a REST API.
    """
    http_method_names = ['get', 'delete']
    serializer_class = ComputeResourceSerializer
    queryset = ComputeResource.objects.all()
    permission_classes = (permissions.IsAdminUser,)

    def perform_destroy(self, instance):
        """
        Overriden to only allow the delete if no plugin would be left without a compute
        resource after the operation.
        """
        try:
            instance.delete()
        except ValidationError as e:
            raise serializers.ValidationError({'non_field_errors': [str(e)]})


class PluginAdminSerializer(PluginSerializer):
    """
    A Plugin serializer for the PluginAdminList JSON view.
    """
    fname = serializers.FileField(write_only=True, required=False)
    plugin_store_url = serializers.URLField(write_only=True, required=False)
    compute_names = serializers.CharField(max_length=2000, write_only=True)
    version = serializers.CharField(required=False)
    dock_image = serializers.CharField(required=False)
    execshell = serializers.CharField(required=False)
    selfpath = serializers.CharField(required=False)
    selfexec = serializers.CharField(required=False)

    class Meta(PluginSerializer.Meta):
        fields = PluginSerializer.Meta.fields + ('fname', 'plugin_store_url',
                                                 'compute_names')

    def create(self, validated_data):
        """
        Overriden to validate and save all the plugin descriptors and parameters
        associated with the plugin when creating it.
        """
        compute_resources = validated_data.pop('compute_names')

        if 'name' in validated_data:
            # gather the data that belongs to the plugin meta
            meta_data = {'name': validated_data.pop('name'),
                         'public_repo': validated_data.pop('public_repo', ''),
                         'title': validated_data.pop('title', ''),
                         'license': validated_data.pop('license', ''),
                         'type': validated_data.pop('type', ''),
                         'icon': validated_data.pop('icon', ''),
                         'category': validated_data.pop('category', ''),
                         'authors': validated_data.pop('authors', ''),
                         'documentation': validated_data.pop('documentation', '')}

            # check whether plugin meta does not exist and validate the plugin meta data
            try:
                meta = PluginMeta.objects.get(name=meta_data['name'])
            except ObjectDoesNotExist:
                meta_serializer = PluginMetaSerializer(data=meta_data)
            else:
                #  validate meta, version are unique
                self.validate_meta_version(meta, validated_data['version'])
                #  validate meta, docker image are unique
                self.validate_meta_image(meta, validated_data['dock_image'])
                meta_serializer = PluginMetaSerializer(meta, data=meta_data)
            meta_serializer.is_valid(raise_exception=True)

            # run all default validators for the full set of plugin fields
            request_parameters = validated_data.pop('parameters')
            new_plg_serializer = PluginSerializer(data=validated_data)
            new_plg_serializer.validate = lambda x: x  # no need rerun custom validation
            new_plg_serializer.is_valid(raise_exception=True)

            # validate all the plugin parameters and their default values
            parameters_serializers = []
            for request_param in request_parameters:
                default = request_param.pop('default', None)
                param_serializer = PluginParameterSerializer(data=request_param)
                param_serializer.is_valid(raise_exception=True)
                serializer_dict = {'serializer': param_serializer,
                                   'default_serializer': None}
                if default is not None:
                    param_type = request_param['type']
                    default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param_type](
                        data={'value': default})
                    default_param_serializer.is_valid(raise_exception=True)
                    serializer_dict['default_serializer'] = default_param_serializer
                parameters_serializers.append(serializer_dict)

            # if no validation errors at this point then save everything to the DB!

            validated_data = new_plg_serializer.validated_data
            pl_meta = meta_serializer.save()
            validated_data['meta'] = pl_meta

            plugin = super(PluginAdminSerializer, self).create(validated_data)

            for param_serializer_dict in parameters_serializers:
                param = param_serializer_dict['serializer'].save(plugin=plugin)
                if param_serializer_dict['default_serializer'] is not None:
                    param_serializer_dict['default_serializer'].save(plugin_param=param)
        else:
            plugin_store_url = validated_data.pop('plugin_store_url')
            pl_manager = PluginManager()
            try:
                plugin = pl_manager.register_plugin_by_url(plugin_store_url,
                                                           compute_resources[0].name)
            except Exception as e:
                raise serializers.ValidationError({'non_field_errors': [str(e)]})

        plugin.compute_resources.set(compute_resources)
        return plugin

    def update(self, instance, validated_data):
        """
        Overriden to add modification date.
        """
        compute_resources = validated_data.pop('compute_names')
        instance.compute_resources.set(compute_resources)
        instance.save()
        return super(PluginAdminSerializer, self).update(instance, validated_data)

    def validate_compute_names(self, compute_names):
        """
        Overriden to validate that the compute resource names exist in the DB.
        """
        cr_l = []
        for cr_name in compute_names.split(','):
            cr_name = cr_name.strip()
            if cr_name:
                try:
                    cr = ComputeResource.objects.get(name=cr_name)
                except ComputeResource.DoesNotExist:
                    raise serializers.ValidationError(
                        [f"Compute resource '{cr_name}' does not exist"])
                cr_l.append(cr)
        if not cr_l:
            raise serializers.ValidationError(
                ['At least one valid compute resource name is required'])
        return cr_l

    def validate(self, data):
        """
        Overriden to validate descriptors in the plugin app representation.
        """
        if not self.instance:  # validation only runs for create not for update
            if 'fname' not in data and 'plugin_store_url' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'fname' "
                                          "or 'plugin_store_url' must be provided."]})

            fname = data.pop('fname', None)
            if fname is not None:
                app_repr = self.read_app_representation(fname)

                # check for required descriptors in the app representation
                self.check_required_descriptor(app_repr, 'name')
                self.check_required_descriptor(app_repr, 'version')
                self.check_required_descriptor(app_repr, 'dock_image')
                self.check_required_descriptor(app_repr, 'execshell')
                self.check_required_descriptor(app_repr, 'selfpath')
                self.check_required_descriptor(app_repr, 'selfexec')
                self.check_required_descriptor(app_repr, 'parameters')

                self.validate_app_version(app_repr['version'])

                # delete from the request those integer descriptors with an empty string or
                # otherwise validate them
                if ('min_number_of_workers' in app_repr) and (
                        app_repr['min_number_of_workers'] == ''):
                    del app_repr['min_number_of_workers']
                elif 'min_number_of_workers' in app_repr:
                    app_repr['min_number_of_workers'] = self.validate_app_workers_descriptor(
                        app_repr['min_number_of_workers'])

                if ('max_number_of_workers' in app_repr) and (
                        app_repr['max_number_of_workers'] == ''):
                    del app_repr['max_number_of_workers']
                elif 'max_number_of_workers' in app_repr:
                    app_repr['max_number_of_workers'] = self.validate_app_workers_descriptor(
                        app_repr['max_number_of_workers'])

                if ('min_gpu_limit' in app_repr) and (app_repr['min_gpu_limit'] == ''):
                    del app_repr['min_gpu_limit']
                elif 'min_gpu_limit' in app_repr:
                    app_repr['min_gpu_limit'] = self.validate_app_gpu_descriptor(
                        app_repr['min_gpu_limit'])

                if ('max_gpu_limit' in app_repr) and (app_repr['max_gpu_limit'] == ''):
                    del app_repr['max_gpu_limit']
                elif 'max_gpu_limit' in app_repr:
                    app_repr['max_gpu_limit'] = self.validate_app_gpu_descriptor(
                        app_repr['max_gpu_limit'])

                if ('min_cpu_limit' in app_repr) and (app_repr['min_cpu_limit'] == ''):
                    del app_repr['min_cpu_limit']
                elif 'min_cpu_limit' in app_repr:
                    app_repr['min_cpu_limit'] = self.validate_app_cpu_descriptor(
                        app_repr['min_cpu_limit'])

                if ('max_cpu_limit' in app_repr) and (app_repr['max_cpu_limit'] == ''):
                    del app_repr['max_cpu_limit']
                elif 'max_cpu_limit' in app_repr:
                    app_repr['max_cpu_limit'] = self.validate_app_cpu_descriptor(
                        app_repr['max_cpu_limit'])

                if ('min_memory_limit' in app_repr) and app_repr['min_memory_limit'] == '':
                    del app_repr['min_memory_limit']
                elif 'min_memory_limit' in app_repr:
                    app_repr['min_memory_limit'] = self.validate_app_memory_descriptor(
                        app_repr['min_memory_limit'])

                if ('max_memory_limit' in app_repr) and app_repr['max_memory_limit'] == '':
                    del app_repr['max_memory_limit']
                elif 'max_memory_limit' in app_repr:
                    app_repr['max_memory_limit'] = self.validate_app_memory_descriptor(
                        app_repr['max_memory_limit'])

                # validate limits
                err_msg = 'The minimum number of workers should be less than the maximum.'
                self.validate_app_descriptor_limits(app_repr, 'min_number_of_workers',
                                                    'max_number_of_workers', err_msg)

                err_msg = 'Minimum cpu limit should be less than maximum cpu limit.'
                self.validate_app_descriptor_limits(app_repr, 'min_cpu_limit',
                                                    'max_cpu_limit', err_msg)

                err_msg = 'Minimum memory limit should be less than maximum memory limit.'
                self.validate_app_descriptor_limits(app_repr, 'min_memory_limit',
                                                    'max_memory_limit', err_msg)

                err_msg = 'Minimum gpu limit should be less than maximum gpu limit.'
                self.validate_app_descriptor_limits(app_repr, 'min_gpu_limit',
                                                    'max_gpu_limit', err_msg)

                # validate plugin parameters in the request data
                app_repr['parameters'] = self.validate_app_parameters(app_repr['parameters'])

                # update the request data
                data.update(app_repr)
        return data

    @staticmethod
    def read_app_representation(representation_file):
        """
        Custom method to read the submitted plugin app representation file.
        """
        try:
            app_repr = json.loads(representation_file.read().decode())
            representation_file.seek(0)
        except Exception:
            raise serializers.ValidationError(
                {'fname': ['Invalid json representation file.']})
        return app_repr

    @staticmethod
    def check_required_descriptor(app_repr, descriptor_name):
        """
        Custom method to check that a required descriptor is in the plugin app
        representation.
        """
        if not (descriptor_name in app_repr):
            raise serializers.ValidationError(
                {'fname': [f'Descriptor {descriptor_name} must be in the app '
                                     f'representation dictionary.']})

    @staticmethod
    def validate_app_version(version):
        """
        Custom method to check that a proper version type and format has been submitted.
        """
        if not isinstance(version, str):
            raise serializers.ValidationError(
                {'fname': ['Invalid type for plugin app version field. Must be '
                                     'a string.']})
        if not re.match(r"^[0-9.]+$", version):
            raise serializers.ValidationError(
                {'fname': [f'Invalid plugin app version number format '
                                     f'{version}.']})
        return version

    @staticmethod
    def validate_meta_version(meta, version):
        """
        Custom method to check if plugin meta and version are unique together.
        """
        try:
            Plugin.objects.get(meta=meta, version=version)
        except ObjectDoesNotExist:
            pass
        else:
            msg = f'Plugin with name {meta.name} and version {version} already exists.'
            raise serializers.ValidationError({'non_field_errors': [msg]})

    @staticmethod
    def validate_meta_image(meta, dock_image):
        """
        Custom method to check if plugin meta and docker image are unique together.
        """
        try:
            Plugin.objects.get(meta=meta, dock_image=dock_image)
        except ObjectDoesNotExist:
            pass
        else:
            raise serializers.ValidationError(
                {'non_field_errors': [f'Docker image {dock_image} already used in a '
                                      f'previous version of plugin {meta.name}. '
                                      f'Please properly version the new image.']})

    @staticmethod
    def validate_app_parameters(parameter_list):
        """
        Custom method to validate plugin parameters.
        """
        for param in parameter_list:
            if 'type' not in param:
                raise serializers.ValidationError(
                    {'fname': ['Parameter type is required.']})
            # translate from back-end type to front-end type, eg. bool->boolean
            param_type = [key for key in TYPES if TYPES[key] == param['type']]
            if not param_type:
                raise serializers.ValidationError(
                    {'fname': ['Invalid parameter type %s.' % param['type']]})
            param['type'] = param_type[0]
            default = param['default'] if 'default' in param else None
            optional = param['optional'] if 'optional' in param else None
            if optional:
                if param['type'] in ('path', 'unextpath'):
                    raise serializers.ValidationError(
                        {'fname': ["Parameters of type 'path' or 'unextpath' "
                                             "cannot be optional."]})
                if default is None:
                    raise serializers.ValidationError(
                        {'fname': ['A default value is required for optional '
                                             'parameters.']})
            elif 'ui_exposed' in param and not param['ui_exposed']:
                raise serializers.ValidationError(
                    {'fname': ['Any parameter that is not optional must be '
                                         'exposed to the UI.']})
            if param['type'] == 'boolean' and 'action' not in param:
                param['action'] = 'store_false' if default else 'store_true'
        return parameter_list

    @staticmethod
    def validate_app_workers_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum workers descriptors.
        """
        error_msg = 'Minimum and maximum number of workers must be positive integers.'
        int_d = PluginAdminSerializer.validate_app_int_descriptor(descriptor, error_msg)
        if int_d < 1:
            raise serializers.ValidationError({'fname': [error_msg]})
        return int_d

    @staticmethod
    def validate_app_cpu_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum cpu descriptors.
        """
        try:
            return CPUInt(descriptor)
        except ValueError as e:
            raise serializers.ValidationError({'fname': [str(e)]})

    @staticmethod
    def validate_app_memory_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum memory descriptors.
        """
        try:
            return MemoryInt(descriptor)
        except ValueError as e:
            raise serializers.ValidationError({'fname': [str(e)]})

    @staticmethod
    def validate_app_gpu_descriptor(descriptor):
        """
        Custom method to validate plugin maximum and minimum gpu descriptors.
        """
        error_msg = 'Minimum and maximum gpu must be non-negative integers.'
        return PluginAdminSerializer.validate_app_int_descriptor(descriptor, error_msg)

    @staticmethod
    def validate_app_int_descriptor(descriptor, error_msg=''):
        """
        Custom method to validate a positive integer descriptor.
        """
        try:
            int_d = int(descriptor)
            assert int_d >= 0
        except (ValueError, AssertionError):
            raise serializers.ValidationError({'fname': [error_msg]})
        return int_d

    @staticmethod
    def validate_app_descriptor_limits(app_repr, min_descriptor_name, max_descriptor_name,
                                       error_msg=''):
        """
        Custom method to validate that a descriptor's minimum is smaller than its maximum.
        """
        if (min_descriptor_name in app_repr) and (max_descriptor_name in app_repr) \
                and (app_repr[max_descriptor_name] < app_repr[min_descriptor_name]):
            raise serializers.ValidationError({'fname': [error_msg]})


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
        template_data = {'fname': '', 'compute_names': '', 'plugin_store_url': ''}
        return services.append_collection_template(response, template_data)


class PluginAdminDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A JSON view for a plugin that can be used by ChRIS admins to delete the plugin
    through a REST API.
    """
    http_method_names = ['get', 'put', 'delete']
    serializer_class = PluginAdminSerializer
    queryset = Plugin.objects.all()
    permission_classes = (permissions.IsAdminUser,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to add a collection+json template to the response.
        """
        response = super(PluginAdminDetail, self).retrieve(request, *args, **kwargs)
        template_data = {'compute_names': ''}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to remove descriptors that are not allowed to be updated before
        serializer validation.
        """
        data = self.request.data
        data.pop('version', None)
        data.pop('dock_image', None)
        data.pop('execshell', None)
        data.pop('selfpath', None)
        data.pop('selfexec', None)
        data.pop('plugin_store_url', None)
        return super(PluginAdminDetail, self).update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """
        Overriden to delete the associated plugin meta if this is the last plugin.
        """
        if instance.meta.plugins.count() == 1:
            instance.meta.delete()  # the cascade deletes the plugin too
        else:
            instance.delete()


admin.site.register(ComputeResource, ComputeResourceAdmin)
admin.site.register(PluginMeta, PluginMetaAdmin)
admin.site.register(Plugin, PluginAdmin)
