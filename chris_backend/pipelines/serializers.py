
import os
import json
from collections import deque

import yaml

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers
from rest_framework.reverse import reverse
from drf_spectacular.utils import OpenApiTypes, extend_schema_field

from core.graph import Graph
from core.models import ChrisFolder
from core.serializers import ChrisFileSerializer
from collectionjson.fields import ItemLinkField
from plugins.enums import TYPES
from plugins.fields import CPUInt, MemoryInt
from plugins.models import Plugin
from plugins.serializers import DEFAULT_PARAMETER_SERIALIZERS
from plugininstances.models import PluginInstance

from .models import Pipeline, PluginPiping, PipelineSourceFile, PipelineSourceFileMeta
from .models import DefaultPipingFloatParameter, DefaultPipingIntParameter
from .models import DefaultPipingBoolParameter, DefaultPipingStrParameter


class PluginPipingSerializer(serializers.HyperlinkedModelSerializer):
    previous_id = serializers.ReadOnlyField(source='previous.id')
    plugin_id = serializers.ReadOnlyField(source='plugin.id')
    plugin_name = serializers.ReadOnlyField(source='plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin.version')
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    previous = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)

    class Meta:
        model = PluginPiping
        fields = ('url', 'id', 'previous_id', 'title', 'plugin_id', 'plugin_name',
                  'plugin_version', 'pipeline_id', 'cpu_limit', 'memory_limit',
                  'number_of_workers', 'gpu_limit', 'previous', 'plugin', 'pipeline')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance is not None:  # on update
            self.fields['title'].read_only = True

    def _get_plugin(self):
        """
        Custom internal method to return the Plugin associated to this piping. On update
        the plugin is taken from the existing instance; on validation outside a view
        (e.g. from PipelineSerializer.validate_plugin_tree) the plugin must be supplied
        via the serializer's context.
        """
        if self.instance is not None:
            return self.instance.plugin
        return self.context['plugin']

    def validate_gpu_limit(self, gpu_limit):
        """
        Overriden to validate gpu_limit is within the proper limits.
        """
        plugin = self._get_plugin()
        self.validate_value_within_interval(gpu_limit,
                                            plugin.min_gpu_limit,
                                            plugin.max_gpu_limit)
        return gpu_limit

    def validate_number_of_workers(self, number_of_workers):
        """
        Overriden to validate number_of_workers is within the proper limits.
        """
        plugin = self._get_plugin()
        self.validate_value_within_interval(number_of_workers,
                                            plugin.min_number_of_workers,
                                            plugin.max_number_of_workers)
        return number_of_workers

    def validate_cpu_limit(self, cpu_limit):
        """
        Overriden to validate cpu_limit is within the proper limits.
        """
        plugin = self._get_plugin()
        self.validate_value_within_interval(cpu_limit,
                                            plugin.min_cpu_limit,
                                            plugin.max_cpu_limit)
        return cpu_limit

    def validate_memory_limit(self, memory_limit):
        """
        Overriden to validate memory_limit is within the proper limits.
        """
        plugin = self._get_plugin()
        self.validate_value_within_interval(memory_limit,
                                            plugin.min_memory_limit,
                                            plugin.max_memory_limit)
        return memory_limit

    @staticmethod
    def validate_value_within_interval(val, min_val, max_val):
        if val is None:
            return
        if val < min_val or val > max_val:
            raise serializers.ValidationError(["This field value is out of range."])


class PipelineSerializer(serializers.HyperlinkedModelSerializer):
    plugin_tree = serializers.JSONField(write_only=True, required=False)
    plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                              required=False)
    name = serializers.CharField(required=False)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    plugins = serializers.HyperlinkedIdentityField(view_name='pipeline-plugin-list')
    plugin_pipings = serializers.HyperlinkedIdentityField(
        view_name='pipeline-pluginpiping-list')
    default_parameters = serializers.HyperlinkedIdentityField(
        view_name='pipeline-defaultparameter-list')
    workflows = serializers.HyperlinkedIdentityField(view_name='workflow-list')
    json_repr = serializers.HyperlinkedIdentityField(
        view_name='pipeline-customjson-detail')

    class Meta:
        model = Pipeline
        fields = ('url', 'id', 'name', 'locked', 'authors', 'category', 'description',
                  'plugin_tree', 'plugin_inst_id', 'owner_username', 'creation_date',
                  'modification_date', 'plugins', 'plugin_pipings', 'default_parameters',
                  'workflows', 'json_repr')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance is not None: # on update
            self.fields['plugin_tree'].read_only = True
            self.fields['plugin_inst_id'].read_only = True

    def create(self, validated_data):
        """
        Overriden to create the pipeline and associate to it a tree of plugins computed
        either from an existing plugin instance or from a passed tree.
        """
        tree_dict = validated_data.pop('plugin_tree', None)
        root_plg_inst = validated_data.pop('plugin_inst_id', None)

        pipeline = super(PipelineSerializer, self).create(validated_data)

        if not tree_dict:
            tree_dict = PipelineSerializer._build_tree_dict_from_instance(root_plg_inst)

        PipelineSerializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        return pipeline

    @staticmethod
    def _build_tree_dict_from_instance(root_plg_inst):
        """
        Custom internal method to walk the plugin-instance tree rooted at root_plg_inst 
        and produce a tree_dict with the canonical (root_index, tree[]) 
        shape used by _add_plugin_tree_to_pipeline.
        """
        # first tree traversal
        tree_dict, inst_id_to_ix = PipelineSerializer._collect_tree_from_instance(
            root_plg_inst)
        
        # second tree traversal
        PipelineSerializer._resolve_instance_tree_ts_indices(tree_dict, inst_id_to_ix)
        return tree_dict

    @staticmethod
    def _collect_tree_from_instance(root_plg_inst):
        """
        Custom internal method to walk the plugin instance tree and build the tree list 
        (with Plugin objects still in 'plugin_id' for the second pass) and an 
        instance-id-to-index mapping. 
        Raises ValidationError if any two visited instances share the same title.
        """
        tree_dict = {'root_index': 0, 'tree': []}
        curr_ix = 0
        queue = [root_plg_inst]
        inst_id_to_ix = {}
        titles = set()

        while len(queue) > 0:
            visited_instance = queue.pop()

            if visited_instance.title in titles:  # avoid duplicated titles
                raise serializers.ValidationError(
                    {'non_field_errors': ["The tree of plugin instances contain "
                                          "duplicated (perhaps empty) titles"]})

            titles.add(visited_instance.title)
            inst_id_to_ix[visited_instance.id] = curr_ix
            child_instances = list(visited_instance.next.all())
            queue.extend(child_instances)

            lower_ix = curr_ix + 1
            upper_ix = lower_ix + len(child_instances)
            child_indices = list(range(lower_ix, upper_ix))

            tree_dict['tree'].append(
                PipelineSerializer._instance_to_tree_node(visited_instance,
                                                          child_indices))
            curr_ix = upper_ix - 1

        return tree_dict, inst_id_to_ix

    @staticmethod
    def _instance_to_tree_node(visited_instance, child_indices):
        """
        Custom internal method to build a single canonical tree node dict from a visited 
        PluginInstance.
        Note: 'plugin_id' is left as the Plugin object here for the ts-resolution
        pass; _resolve_instance_tree_ts_indices flattens it to the integer pk.
        """
        # parameter defaults assigned from the plugin instance's parameter values
        defaults = [{'name': p_inst.plugin_param.name, 'default': p_inst.value}
                    for p_inst in visited_instance.get_parameter_instances()]
        
        return {'plugin_id': visited_instance.plugin,
                'title': visited_instance.title,
                'cpu_limit': visited_instance.cpu_limit,
                'memory_limit': visited_instance.memory_limit,
                'number_of_workers': visited_instance.number_of_workers,
                'gpu_limit': visited_instance.gpu_limit,
                'plugin_parameter_defaults': defaults,
                'child_indices': child_indices}

    @staticmethod
    def _resolve_instance_tree_ts_indices(tree_dict, inst_id_to_ix):
        """
        Custom internal method to rewrite the 'plugininstances' default from 
        comma-separated instance ids to comma-separated tree indices for any 'ts' 
        plugin in the tree. Also flattens 'plugin_id' from the Plugin object to 
        its primary key.
        """
        root_ix = tree_dict['root_index']
        tree = tree_dict['tree']
        queue = deque()
        queue.append(root_ix)

        while len(queue):
            curr_ix = queue.popleft()
            curr_node = tree[curr_ix]
            queue.extend(curr_node['child_indices'])

            for d in curr_node['plugin_parameter_defaults']:
                name = d['name']
                default = d['default']
                plg = curr_node['plugin_id']

                if name == 'plugininstances' and plg.meta.type == 'ts':
                    parent_ixs = [str(inst_id_to_ix[int(s)])
                                  for s in default.split(',')]
                    d['default'] = ','.join(parent_ixs)
                    break

            tree[curr_ix]['plugin_id'] = curr_node['plugin_id'].id

    def update(self, instance, validated_data):
        """
        Overriden to add the modification date.
        """
        validated_data.update({'modification_date': timezone.now()})
        return super(PipelineSerializer, self).update(instance, validated_data)

    def validate(self, data):
        """
        Overriden to validate that required fields are in data when creating a new
        pipeline. Also to delete 'locked' parameter if the pipeline is not locked.
        """
        if self.instance:
            if not self.instance.locked and 'locked' in data:
                # this pipeline was made available to the public so it cannot be locked
                del data['locked']
        else:
            if 'name' not in data:
                raise serializers.ValidationError(
                    {'name': ["This field is required."]})

            if 'plugin_tree' not in data and 'plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'plugin_tree' "
                                          "or 'plugin_inst_id' must be provided."]})
        return data
    
    def validate_name(self, name):
        """
        Overriden to validate the pipeline name is unique.
        """
        try:
            Pipeline.objects.get(name=name)
        except ObjectDoesNotExist:
            pass
        else:
            msg = f'Pipeline with name {name} already exists.'
            raise serializers.ValidationError([msg])
        return name

    def validate_plugin_inst_id(self, plugin_inst_id):
        """
        Overriden to validate the plugin instance id.
        """
        try:
            plg_inst = PluginInstance.objects.get(pk=plugin_inst_id)
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                ["Couldn't find any plugin instance with id %s." % plugin_inst_id])
        
        plg = plg_inst.plugin
        if plg.meta.type != 'ds':
            raise serializers.ValidationError(
                [f"Plugin instance of {plg.meta.name} which is of type {plg.meta.type} "
                 f"and therefore can not be used as the root of a new pipeline."])
        return plg_inst

    def validate_plugin_tree(self, plugin_tree):
        """
        Overriden to validate the input tree list. It should be a list of dictionaries.
        Each dictionary is a tree node containing a unique title within the tree, the
        title of the previous node in the list and either a plugin id or a plugin name
        and a plugin version.
        """
        plugin_list = PipelineSerializer._parse_plugin_tree(plugin_tree)
        title_to_ix = PipelineSerializer._build_title_to_ix(plugin_list)

        plugin_is_ts_list = []
        found_root_node = False

        for d in plugin_list:
            plg, prev_title, found_root_node = PipelineSerializer._validate_node_plugin(
                d, title_to_ix, found_root_node)
            
            PipelineSerializer._validate_node_resources(plg, d)

            plugin_is_ts_list.append(plg.meta.type == 'ts')

            PipelineSerializer._normalize_node_parameter_defaults(
                d, plg, prev_title, title_to_ix)
            
            d['previous'] = None if prev_title is None else title_to_ix[prev_title]

        if not found_root_node:
            raise serializers.ValidationError([f"Couldn't find the root of the tree"])

        if True in plugin_is_ts_list:
            PipelineSerializer.validate_DAG(plugin_list, plugin_is_ts_list)

        return PipelineSerializer.get_tree(plugin_list)

    @staticmethod
    def _parse_plugin_tree(plugin_tree):
        """
        Custom internal method to parse the user-supplied plugin_tree (a JSON string 
        of a list of node dicts) and return the list. Raises ValidationError for invalid 
        JSON, non-list payloads, or empty lists.
        """
        try:
            plugin_list = list(json.loads(plugin_tree))
        except json.decoder.JSONDecodeError:
            # overriden validation methods automatically add the field name to the msg
            raise serializers.ValidationError(
                ["Invalid JSON string %s." % plugin_tree])
        except Exception:
            raise serializers.ValidationError(
                ["Invalid tree list in %s" % plugin_tree])

        if len(plugin_list) == 0:
            raise serializers.ValidationError(
                ["Invalid empty list in %s" % plugin_tree])
        return plugin_list

    @staticmethod
    def _build_title_to_ix(plugin_list):
        """
        Custom internal method to build the title-to-index map for the plugin tree list, 
        ensuring every node has a unique title. Raises ValidationError on missing or 
        duplicated titles.
        """
        title_to_ix = {}

        for ix, d in enumerate(plugin_list):
            title = d.get('title')

            if title is None:
                raise serializers.ValidationError(
                    ['All nodes in the pipeline must have a title'])
            
            if title in title_to_ix:
                raise serializers.ValidationError(
                    ["Pipeline tree can not contain duplicated titles"])
            
            title_to_ix[title] = ix
        return title_to_ix

    @staticmethod
    def _validate_node_plugin(d, title_to_ix, found_root_node):
        """
        Custom internal method to validate a single tree node's `previous` and plugin 
        fields. Returns (plugin, prev_title, updated_found_root_node). 
        Mutates d['plugin_id'] to the resolved Plugin's id when only plugin_name and 
        plugin_version were provided. 
        Raises ValidationError if the previous pointer is invalid, the plugin can't be 
        found, the node is malformed, or the resolved plugin is of type 'fs'.
        """
        try:
            prev_title = d['previous']
        except KeyError:
            raise serializers.ValidationError(
                [PipelineSerializer._malformed_node_error(d)])

        found_root_node = PipelineSerializer._validate_previous_pointer(
            prev_title, title_to_ix, found_root_node)
        plg = PipelineSerializer._resolve_node_plugin(d)

        if plg.meta.type == 'fs':
            raise serializers.ValidationError(
                ["Plugin %s is of type 'fs' and therefore can not be used to "
                 "create a pipeline." % plg])
        return plg, prev_title, found_root_node

    @staticmethod
    def _validate_previous_pointer(prev_title, title_to_ix, found_root_node):
        """
        Custom internal method to validate a tree node's `previous` value against 
        title_to_ix. Returns the (possibly updated) found_root_node flag. 
        Raises ValidationError when previous is None on a second root or when previous 
        references an unknown title.
        """
        if prev_title is None:
            if found_root_node:
                raise serializers.ValidationError(
                    ["Pipeline's tree is not connected!"])
            return True
        
        if prev_title not in title_to_ix:
            raise serializers.ValidationError(
                [f"Could not find any node with title {prev_title}"])
        return found_root_node

    @staticmethod
    def _resolve_node_plugin(d):
        """
        Custom internal method to resolve and return the Plugin for a tree node.
        If d['plugin_id'] is present it is used directly; otherwise plugin_name and 
        plugin_version are required. d['plugin_id'] is back-filled with the resolved 
        Plugin's id in the latter case. Raises ValidationError if the plugin can't be
        found or the node is malformed.
        """
        plg_name = plg_version = plg_id = None
        try:
            if 'plugin_id' not in d:
                plg_name = d['plugin_name']
                plg_version = d['plugin_version']
                plg = Plugin.objects.get(meta__name=plg_name, version=plg_version)
                d['plugin_id'] = plg.id
            else:
                plg_id = int(d['plugin_id'])
                plg = Plugin.objects.get(pk=plg_id)
        except ObjectDoesNotExist:
            if 'plugin_id' not in d:
                msg = ["Couldn't find any plugin with name %s and version %s." %
                       (plg_name, plg_version)]
            else:
                msg = ["Couldn't find any plugin with id %s." % plg_id]
            raise serializers.ValidationError(msg)
        except Exception:
            raise serializers.ValidationError(
                [PipelineSerializer._malformed_node_error(d)])
        return plg

    @staticmethod
    def _malformed_node_error(d):
        """
        Shared error string for tree nodes that are missing required keys or
        have non-coercible plugin_id values.
        """
        return (f"Object {d} must be a JSON object with a previous (str or null) "
                "property and either plugin_id (int) or plugin_name (str) and  "
                "plugin_version (str) properties.")

    @staticmethod
    def _validate_node_resources(plg, d):
        """
        Custom internal method to validate per-piping resource overrides (cpu_limit, 
        memory_limit, number_of_workers, gpu_limit) using PluginPipingSerializer. 
        Raises a ValidationError that includes the offending node's title when the
        underlying serializer rejects any field.
        """
        data = {'title': d['title']}

        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            if f in d:
                data[f] = d[f]

        piping_serializer = PluginPipingSerializer(data=data, context={'plugin': plg})
        try:
            piping_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            raise serializers.ValidationError(
                [f"Invalid data for: '{d['title']}', detail: {str(e)}"])

    @staticmethod
    def _normalize_node_parameter_defaults(d, plg, prev_title, title_to_ix):
        """
        Custom internal method to validate and normalize the node's 
        plugin_parameter_defaults. If absent, an empty list is installed in d. 
        For 'ts' plugins, rewrites the 'plugininstances' default from comma-separated 
        titles to comma-separated indices.
        """
        if 'plugin_parameter_defaults' in d:
            PipelineSerializer.validate_plugin_parameter_defaults(
                plg, prev_title, title_to_ix, d['plugin_parameter_defaults'])

            for default_d in d['plugin_parameter_defaults']:
                if default_d['name'] == 'plugininstances':
                    if default_d['default']:  # map list of titles to indices
                        parent_ixs = [str(title_to_ix[t]) for t in
                                      default_d['default'].split(',')]
                        default_d['default'] = ','.join(parent_ixs)
                    break
        else:
            d['plugin_parameter_defaults'] = []

    @staticmethod
    def validate_plugin_parameter_defaults(plugin, previous_title,
                                           titles, req_param_defaults):
        """
        Custom method to validate the parameter names and their default values for a
        node in the plugin tree.
        """
        for param in plugin.parameters.all():
            param_default = param.get_default()
            param_default_value = param_default.value if param_default else None
            req_default = [d for d in req_param_defaults if d.get('name') == param.name]

            if param_default_value is None and not req_default:
                # no default provided by the plugin or the user
                error_msg = f"Missing default value for parameter {param.name} " \
                            f"for plugin {plugin}. Pipeline can not be created " \
                            f"until all plugin parameters have default values."
                raise serializers.ValidationError([error_msg])

            if req_default:
                PipelineSerializer._validate_user_default(
                    plugin, previous_title, titles, param, req_default[0])

    @staticmethod
    def _validate_user_default(plugin, previous_title, titles, param, req_default_entry):
        """
        Custom internal method to validate a single user-supplied parameter default 
        entry: extract its name and value, run the type-specific value check, and 
        (for 'ts' plugins on the 'plugininstances' parameter) run the ts-specific
        validations.
        """
        name = req_default_entry['name']
        try:
            default = req_default_entry['default']
        except KeyError:
            error_msg = f"Invalid parameter default object " \
                        f"{req_default_entry}. Each valid default object must " \
                        f"have 'name' and 'default' properties."
            raise serializers.ValidationError([error_msg])

        default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param.type](
            data={'value': default})
        
        if not default_param_serializer.is_valid():
            error_msg = f"Invalid default value {default} for parameter {name} " \
                        f"for plugin {plugin.meta.name}."
            raise serializers.ValidationError([error_msg])

        if name == 'plugininstances' and plugin.meta.type == 'ts':
            PipelineSerializer._validate_ts_plugininstances_default(
                plugin, previous_title, titles, default)

    @staticmethod
    def _validate_ts_plugininstances_default(plugin, previous_title, titles, default):
        """
        Custom internal method to validate the 'plugininstances' parameter default for 
        'ts' plugins. Dispatches to two helpers: one that enforces the empty/non-empty
        pairing with previous_title, and one that validates the parent-titles list when 
        default is non-empty.
        """
        PipelineSerializer._validate_ts_default_consistency(
            plugin, previous_title, default)
        
        if default:
            PipelineSerializer._validate_ts_parent_titles_list(
                plugin, previous_title, titles, default)

    @staticmethod
    def _validate_ts_default_consistency(plugin, previous_title, default):
        """
        Custom internal method to enforce the empty/non-empty pairing rules between 
        previous_title and default for the 'plugininstances' parameter of 'ts' plugins.
        """
        if previous_title is None and default:
            error_msg = f"The plugininstances parameter's default must be " \
                        f"the empty string for 'ts' plugins with null " \
                        f"previous"
            raise serializers.ValidationError([error_msg])

        if previous_title is not None and not default:
            error_msg = f"Invalid default value '{default}' for parameter " \
                        f"plugininstances for plugin {plugin.meta.name}. " \
                        f"Must contain the title of the previous."
            raise serializers.ValidationError([error_msg])

    @staticmethod
    def _validate_ts_parent_titles_list(plugin, previous_title, titles, default):
        """
        Custom internal method to validate the comma-separated list of parent titles 
        in the 'ts' 'plugininstances' default: titles must be unique, must all exist in
        `titles` and must include the previous_title.
        """
        parent_titles = default.split(',')

        if len(parent_titles) > len(set(parent_titles)):
            error_msg = f"Invalid default value '{default}' for " \
                        f"parameter plugininstances for plugin " \
                        f"{plugin.meta.name}. Duplicated title."
            raise serializers.ValidationError([error_msg])
        
        for title in parent_titles:
            if title not in titles:
                error_msg = f"Invalid default value '{default}' for " \
                            f"parameter plugininstances for plugin " \
                            f"{plugin.meta.name}. Could not find any " \
                            f"node with title '{title}'"
                raise serializers.ValidationError([error_msg])
            
        if previous_title not in parent_titles:
            error_msg = f"Invalid default value '{default}' for " \
                        f"parameter plugininstances for plugin " \
                        f"{plugin.meta.name}. Must contain the title " \
                        f"of the previous."
            raise serializers.ValidationError([error_msg])

    @staticmethod
    def validate_DAG(tree_list, plugin_is_ts_list):
        """
        Custom method to validate whether the represented DAG (Directed Acyclic Graph) in
        tree_list doesn't have cycles.
        """
        nvert = len(tree_list)
        g = Graph(nvert, directed=True)
        root_vert = 1

        for ix, d in enumerate(tree_list):
            previous_ix = d['previous']
            if previous_ix is None:
                root_vert = ix + 1
            else:
                g.insert_edge(previous_ix+1, ix+1)  # graph's vertices are int >= 1

            if plugin_is_ts_list[ix] and d['plugin_parameter_defaults']:
                for default_d in d['plugin_parameter_defaults']:
                    if default_d['name'] == 'plugininstances':
                        default = default_d['default']

                        if default:
                            parent_ixs = [int(str_ix) for str_ix in default.split(',')]
                            
                            for p_ix in parent_ixs:
                                if p_ix != previous_ix:
                                    g.insert_edge(p_ix + 1, ix + 1)
                        break

        g.dfs(root_vert)

        if g.cycle:
            cycle = ','.join([str(vert-1) for vert in g.cycle])
            error_msg = f"Pipeline's DAG has an indices cycle: {cycle}!"
            raise serializers.ValidationError([error_msg])

    @staticmethod
    def get_tree(tree_list):
        """
        Custom method to return a dictionary containing a list of nodes representing a
        tree of plugins and the index of the root of the tree. Each node is a dictionary
        containing the node's title, plugin id, its parameter defaults, the list of
        child indices, and any per-piping resource overrides (cpu_limit, memory_limit,
        number_of_workers, gpu_limit) that were present on the input node.
        """
        resource_fields = ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit')

        def _make_node(d):
            node = {'plugin_id': d['plugin_id'],
                    'title': d['title'],
                    'plugin_parameter_defaults': d['plugin_parameter_defaults'],
                    'child_indices': []}
            
            for f in resource_fields:
                if f in d:
                    node[f] = d[f]
            return node

        root_ix = [ix for ix,d in enumerate(tree_list) if d['previous'] is None][0]

        tree = [None] * len(tree_list)
        tree[root_ix] = _make_node(tree_list[root_ix])

        for ix, d in enumerate(tree_list):
            if ix != root_ix:
                if not tree[ix]:
                    tree[ix] = _make_node(d)

                prev_ix = d['previous']
                if tree[prev_ix]:
                    tree[prev_ix]['child_indices'].append(ix)
                else:
                    tree[prev_ix] = _make_node(tree_list[prev_ix])
                    tree[prev_ix]['child_indices'].append(ix)
        return {'root_index': root_ix, 'tree': tree}

    @staticmethod
    def _piping_resource_kwargs(node):
        """
        Custom internal method to build the per-piping resource kwargs for 
        PluginPiping.objects.create from a canonical tree node. cpu_limit/memory_limit 
        may arrive as Kubernetes-style strings ('150m', '1Gi') from the YAML/JSON 
        pipeline source path or as plain ints from the plugin-instance path. 
        CPUInt/MemoryInt accept both and yield the int form the model field expects on 
        save. None values are skipped so the field's default applies.
        """
        converters = {'cpu_limit': CPUInt, 'memory_limit': MemoryInt}
        kwargs = {}

        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            if f in node and node[f] is not None:
                converter = converters.get(f)
                kwargs[f] = converter(node[f]) if converter else node[f]
        return kwargs

    @staticmethod
    def _add_plugin_tree_to_pipeline(pipeline, tree_dict):
        """
        Custom internal method to associate a tree of plugins to a pipeline in the DB.
        """
        # here a piping precedes another piping if its corresponding plugin precedes
        # the other piping's plugin in the pipeline
        plg_pipings_dict = PipelineSerializer._create_pipings_bfs(pipeline, tree_dict)
        PipelineSerializer._finalize_ts_pipings(plg_pipings_dict)

    @staticmethod
    def _create_piping(pipeline, node, previous_piping):
        """
        Custom internal method to create a single PluginPiping for the given canonical 
        tree node, persist its parameter defaults and return it. previous_piping is 
        None for the root.
        """
        plg = Plugin.objects.get(pk=node['plugin_id'])
        kwargs = PipelineSerializer._piping_resource_kwargs(node)

        plg_piping = PluginPiping.objects.create(title=node['title'],
                                                 pipeline=pipeline,
                                                 plugin=plg,
                                                 previous=previous_piping,
                                                 **kwargs)
        
        plg_piping.save(parameter_defaults=node['plugin_parameter_defaults'])
        return plg_piping

    @staticmethod
    def _create_pipings_bfs(pipeline, tree_dict):
        """
        Custom internal method for breadth-first creation of PluginPiping rows for every 
        node in the canonical tree. Returns an index-to-piping dict.
        """
        root_ix = tree_dict['root_index']
        tree = tree_dict['tree']
        root_plg_piping = PipelineSerializer._create_piping(
            pipeline, tree[root_ix], None)
        plg_pipings_dict = {root_ix: root_plg_piping}

        piping_queue = deque()
        piping_queue.append(root_plg_piping)
        ix_queue = deque()
        ix_queue.append(root_ix)

        while len(piping_queue):
            curr_ix = ix_queue.popleft()
            curr_piping = piping_queue.popleft()
            
            for ix in tree[curr_ix]['child_indices']:
                plg_piping = PipelineSerializer._create_piping(pipeline, tree[ix], 
                                                               curr_piping)
                plg_pipings_dict[ix] = plg_piping
                ix_queue.append(ix)
                piping_queue.append(plg_piping)
        return plg_pipings_dict

    @staticmethod
    def _finalize_ts_pipings(plg_pipings_dict):
        """
        Custom internal method to rewrite the 'plugininstances' default from
        comma-separated tree indices to comma-separated piping ids for every 'ts' piping.
        """
        # update the 'plugininstances' param with parent piping ids for any 'ts' piping
        for plg_piping in plg_pipings_dict.values():
            if plg_piping.plugin.meta.type == 'ts':
                param = plg_piping.string_param.filter(
                    plugin_param__name='plugininstances').first()
                
                if param and param.value:
                    parent_ixs = [int(parent_ix) for parent_ix in param.value.split(',')]
                    parent_pip_ids = [str(plg_pipings_dict[ix].id) for ix in parent_ixs]
                    param.value = ','.join(parent_pip_ids)
                    param.save()


class PipelineCustomJsonSerializer(serializers.HyperlinkedModelSerializer):
    plugin_tree = serializers.SerializerMethodField()

    class Meta:
        model = Pipeline
        fields = ('url', 'name', 'locked', 'authors', 'category', 'description',
                  'plugin_tree')

    def get_plugin_tree(self, obj) -> str:
        """
        Overriden to get the plugin_tree JSON string.
        """
        return json.dumps(obj.get_plugin_tree())


class PipelineSourceFileSerializer(ChrisFileSerializer):
    fname = serializers.FileField(use_url=False, required=True)
    ftype = serializers.ReadOnlyField(source='meta.type')
    type = serializers.CharField(write_only=True, required=False)
    uploader_username = serializers.ReadOnlyField(source='meta.uploader.username')
    pipeline_id = serializers.ReadOnlyField(source='meta.pipeline.id')
    pipeline_name = serializers.ReadOnlyField(source='meta.pipeline.name')

    class Meta:
        model = PipelineSourceFile
        fields = ('url', 'id', 'creation_date', 'fname', 'fsize', 'public', 'type',
                  'ftype', 'uploader_username', 'owner_username', 'pipeline_id',
                  'pipeline_name', 'file_resource', 'parent_folder', 'owner')

    def create(self, validated_data):
        """
        Overriden to create the pipeline from the source file data, set the file's saving
        path, parent folder and meta info.
        """
        owner = validated_data.get('owner')
        uploader = validated_data.pop('uploader')
        type = validated_data.pop('type', 'yaml')

        # create pipeline
        pipeline_repr = validated_data.pop('pipeline')
        pipeline_serializer = PipelineSerializer(data=pipeline_repr)
        pipeline_serializer.is_valid(raise_exception=True)
        pipeline = pipeline_serializer.save(owner=uploader)  # uploader owns the pipeline

        # file will be stored to Swift at:
        # SWIFT_CONTAINER_NAME/PIPELINES/<uploader_username>/<filename>
        folder_path = f'PIPELINES/{uploader.username}'
        (parent_folder, tf) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                owner=owner)
        if tf:
            parent_folder.grant_public_access()

        fname = validated_data['fname']
        filename = os.path.basename(fname.name).replace(',', '')
        validated_data['parent_folder'] = parent_folder
        source_file = PipelineSourceFile(**validated_data)
        source_file.public = True
        source_file.fname.name = f'{folder_path}/{filename}'
        source_file.save()

        # create file's meta info
        PipelineSourceFileMeta.objects.get_or_create(type=type, pipeline=pipeline,
                                                     source_file=source_file,
                                                     uploader=uploader)
        return source_file

    def validate_fname(self, fname):
        """
        Overriden to handle a file name that only contain commas and white spaces.
        """
        name = os.path.basename(fname.name)

        if name.replace(',', '').strip() == '':
            raise serializers.ValidationError([f"Invalid object name '{name}'."])
        return fname

    def validate(self, data):
        """
        Overriden to validate and transform the pipeline data in the source file to the
        json canonical representation.
        """
        type = data.get('type', 'yaml')
        pipeline_repr = ''

        if type == 'yaml':
            pipeline_repr = self.read_yaml_pipeline_representation(data['fname'])
            pipeline_repr = self.get_yaml_pipeline_canonical_representation(pipeline_repr)

        elif type == 'json':
            pipeline_repr = self.read_json_pipeline_representation(data['fname'])
            pipeline_repr = self.get_json_pipeline_canonical_representation(pipeline_repr)

        data['pipeline'] = pipeline_repr
        return data

    @staticmethod
    def read_yaml_pipeline_representation(pipeline_source_file):
        """
        Custom method to read the submitted yaml pipeline source file.
        """
        try:
            pipeline_repr = yaml.safe_load(pipeline_source_file.read().decode())
            pipeline_source_file.seek(0)
        except Exception:
            error_msg = "Invalid yaml representation file."
            raise serializers.ValidationError({'fname': [error_msg]})
        return pipeline_repr

    @staticmethod
    def read_json_pipeline_representation(pipeline_source_file):
        """
        Custom method to read the submitted json pipeline source file.
        """
        try:
            pipeline_repr = json.loads(pipeline_source_file.read().decode())
            pipeline_source_file.seek(0)
        except Exception:
            error_msg = "Invalid json representation file."
            raise serializers.ValidationError({'fname': [error_msg]})
        return pipeline_repr

    @staticmethod
    def get_yaml_pipeline_canonical_representation(pipeline_repr):
        """
        Custom method to convert the submitted yaml pipeline representation to the
        canonical JSON representation.
        """
        plugin_tree = [
            PipelineSourceFileSerializer._build_canonical_yaml_node(node)
            for node in pipeline_repr.get('plugin_tree', [])
        ]
        pipeline_repr['plugin_tree'] = json.dumps(plugin_tree)
        return pipeline_repr

    @staticmethod
    def _parse_plugin_name_and_version(plugin_str):
        """
        Custom internal method to parse the YAML 'plugin' string of the form 
        '<name> v<version>' (with arbitrary whitespace) and return 
        (plugin_name, plugin_version). Raises ValidationError on malformed input.
        """
        try:
            plg_list = plugin_str.strip().split(' ')
            plugin_name = plg_list[0]
            plugin_version = plg_list[1:][-1][1:]
        except Exception:
            raise serializers.ValidationError(
                {'fname': ["Missing plugin name or version."]})
        return plugin_name, plugin_version

    @staticmethod
    def _convert_plugin_parameter_defaults(defaults_dict):
        """
        Custom internal method to convert a {param_name: default} mapping (YAML form)
        into the canonical list of {'name', 'default'} entries.
        """
        return [{'name': key, 'default': value}
                for key, value in defaults_dict.items()]

    @staticmethod
    def _build_canonical_yaml_node(node):
        """
        Custom internal method to build a single canonical tree node from a YAML 
        pipeline_tree node. Raises ValidationError if 'plugin' is missing or malformed.
        """
        plugin = node.get('plugin')

        if not plugin:
            raise serializers.ValidationError(
                {'fname': ["A 'plugin' key is required for all plugin_tree nodes."]})
        plugin_name, plugin_version = (
            PipelineSourceFileSerializer._parse_plugin_name_and_version(plugin))

        plg_param_defaults = (
            PipelineSourceFileSerializer._convert_plugin_parameter_defaults(
                node.get('plugin_parameter_defaults', {})))

        canonical_node = {
            'title': node.get('title'),
            'plugin_name': plugin_name,
            'plugin_version': plugin_version,
            'previous': node.get('previous'),
        }

        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            if f in node:
                canonical_node[f] = node[f]

        if plg_param_defaults:
            canonical_node['plugin_parameter_defaults'] = plg_param_defaults
        return canonical_node

    @staticmethod
    def get_json_pipeline_canonical_representation(pipeline_repr):
        """
        Custom method to convert the submitted json pipeline representation to the
        canonical JSON representation.
        """
        plugin_tree = pipeline_repr.get('plugin_tree', [])
        pipeline_repr['plugin_tree'] = json.dumps(plugin_tree)
        return pipeline_repr

class DefaultPipingStrParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_piping_title = serializers.ReadOnlyField(source='plugin_piping.title')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin_param.plugin.version')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingStrParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id', 'plugin_piping_title',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_version', 'plugin_id', 'plugin_param')


class DefaultPipingIntParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_piping_title = serializers.ReadOnlyField(source='plugin_piping.title')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin_param.plugin.version')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingIntParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id', 'plugin_piping_title',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_version', 'plugin_id', 'plugin_param')


class DefaultPipingFloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_piping_title = serializers.ReadOnlyField(source='plugin_piping.title')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin_param.plugin.version')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingFloatParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id', 'plugin_piping_title',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_version', 'plugin_id', 'plugin_param')


class DefaultPipingBoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_piping_title = serializers.ReadOnlyField(source='plugin_piping.title')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin_param.plugin.version')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingBoolParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id', 'plugin_piping_title',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_version', 'plugin_id', 'plugin_param')


class GenericDefaultPipingParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_piping_title = serializers.ReadOnlyField(source='plugin_piping.title')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.meta.name')
    plugin_version = serializers.ReadOnlyField(source='plugin_param.plugin.version')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    value = serializers.SerializerMethodField()
    url = ItemLinkField('_get_url')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingStrParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id', 'plugin_piping_title',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_version', 'plugin_id', 'plugin_param')

    @extend_schema_field(OpenApiTypes.URI)
    def _get_url(self, obj):
        """
        Custom internal method to get the correct url for the serialized object 
        regardless of its type.
        """
        request = self.context['request']
        # here default piping parameter detail view names are assumed to
        # follow a convention
        view_name = 'defaultpiping' + TYPES[obj.plugin_param.type] + 'parameter-detail'
        return reverse(view_name, request=request, kwargs={"pk": obj.id})

    def get_value(self, obj) -> str | int | float | bool:
        """
        Overriden to get the default parameter value regardless of its type.
        """
        return obj.value


DEFAULT_PIPING_PARAMETER_SERIALIZERS = {'string': DefaultPipingStrParameterSerializer,
                                        'integer': DefaultPipingIntParameterSerializer,
                                        'float': DefaultPipingFloatParameterSerializer,
                                        'boolean': DefaultPipingBoolParameterSerializer}
