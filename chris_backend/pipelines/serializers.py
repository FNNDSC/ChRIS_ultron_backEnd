
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
from core.serializers import file_serializer
from collectionjson.fields import ItemLinkField
from plugins.enums import TYPES
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
                  'plugin_version', 'pipeline_id', 'previous', 'plugin', 'pipeline')


class PipelineSerializer(serializers.HyperlinkedModelSerializer):
    plugin_tree = serializers.JSONField(write_only=True, required=False)
    plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                              required=False)
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

    def create(self, validated_data):
        """
        Overriden to create the pipeline and associate to it a tree of plugins computed
        either from an existing plugin instance or from a passed tree.
        """
        tree_dict = validated_data.pop('plugin_tree', None)
        root_plg_inst = validated_data.pop('plugin_inst_id', None)
        pipeline = super(PipelineSerializer, self).create(validated_data)

        if not tree_dict:  # generate tree_dict from passed plugin instance
            tree_dict = {'root_index': 0, 'tree': []}
            curr_ix = 0
            queue = [root_plg_inst]
            inst_id_to_ix = {}  # inititalize plugin instance id-to-index mapping
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
                parameter_instances = visited_instance.get_parameter_instances()

                # parameter defaults assigned from the plugin instance's parameter values
                defaults = [{'name': p_inst.plugin_param.name, 'default': p_inst.value}
                            for p_inst in parameter_instances]

                tree_dict['tree'].append({'plugin_id': visited_instance.plugin,
                                          'title': visited_instance.title,
                                          'plugin_parameter_defaults': defaults,
                                          'child_indices': child_indices})
                curr_ix = upper_ix - 1

            # breath-first traversal to map list of titles to indices in ts plugins
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

        PipelineSerializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        return pipeline

    def update(self, instance, validated_data):
        """
        Overriden to add the modification date.
        """
        validated_data.update({'modification_date': timezone.now()})
        return super(PipelineSerializer, self).update(instance, validated_data)

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data when
        creating a new pipeline.
        """
        if not self.instance:  # this validation only happens on create and not on update
            if 'plugin_tree' not in data and 'plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'plugin_tree' "
                                          "or 'plugin_inst_id' must be provided."]})
        return data

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
        try:
            plugin_list = list(json.loads(plugin_tree))
        except json.decoder.JSONDecodeError:
            # overriden validation methods automatically add the field name to the msg
            msg = ["Invalid JSON string %s." % plugin_tree]
            raise serializers.ValidationError(msg)
        except Exception:
            msg = ["Invalid tree list in %s" % plugin_tree]
            raise serializers.ValidationError(msg)
        if len(plugin_list) == 0:
            msg = ["Invalid empty list in %s" % plugin_tree]
            raise serializers.ValidationError(msg)

        title_to_ix = {}   # inititalize title-to-index mapping
        for ix, d in enumerate(plugin_list):
            title = d.get('title')
            if title is None:
                raise serializers.ValidationError(['All nodes in the pipeline must have '
                                                   'a title'])
            if title in title_to_ix:
                raise serializers.ValidationError(
                    ["Pipeline tree can not contain duplicated titles"])
            piping_serializer = PluginPipingSerializer(data={'title': title})
            try:
                piping_serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                raise serializers.ValidationError([f"Invalid title: '{title}', "
                                                   f"detail: {str(e)}"])
            title_to_ix[title] = ix

        plugin_is_ts_list = []
        found_root_node = False
        for d in plugin_list:
            try:
                prev_title = d['previous']
                if prev_title is None:
                    if found_root_node:
                        raise serializers.ValidationError(
                            ["Pipeline's tree is not connected!"])
                    found_root_node = True
                elif prev_title not in title_to_ix:
                    raise serializers.ValidationError(
                        [f"Could not find any node with title {prev_title}"])

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
            except serializers.ValidationError:
                raise
            except Exception:
                msg = [f"Object {d} must be a JSON object with a previous (str or null) "
                       "property and either plugin_id (int) or plugin_name (str) and  "
                       "plugin_version (str) properties."]
                raise serializers.ValidationError(msg)

            if plg.meta.type == 'fs':
                msg = ["Plugin %s is of type 'fs' and therefore can not be used to "
                       "create a pipeline." % plg]
                raise serializers.ValidationError(msg)

            plugin_is_ts_list.append(plg.meta.type == 'ts')

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

            # map previous title to an index
            d['previous'] = None if prev_title is None else title_to_ix[prev_title]

        if not found_root_node:
            raise serializers.ValidationError([f"Couldn't find the root of the tree"])

        if True in plugin_is_ts_list:
            PipelineSerializer.validate_DAG(plugin_list, plugin_is_ts_list)

        return PipelineSerializer.get_tree(plugin_list)

    @staticmethod
    def validate_plugin_parameter_defaults(plugin, previous_title,
                                           titles, req_param_defaults):
        """
        Custom method to validate the parameter names and their default values for a
        node in the plugin tree.
        """
        parameters = plugin.parameters.all()

        for param in parameters:
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
                name = req_default[0]['name']
                try:
                    default = req_default[0]['default']
                except KeyError:
                    error_msg = f"Invalid parameter default object " \
                                f"{req_default[0]}. Each valid default object must " \
                                f"have 'name' and 'default' properties."
                    raise serializers.ValidationError([error_msg])

                default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param.type](
                    data={'value': default})
                if not default_param_serializer.is_valid():
                    error_msg = f"Invalid default value {default} for parameter {name} " \
                                f"for plugin {plugin.meta.name}."
                    raise serializers.ValidationError([error_msg])

                if name == 'plugininstances' and plugin.meta.type == 'ts':
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

                    if default:
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
        containing the node's title, plugin id, its parameter defaults and the
        list of child indices.
        """
        root_ix = [ix for ix,d in enumerate(tree_list) if d['previous'] is None][0]
        tree = [None] * len(tree_list)
        plugin_id = tree_list[root_ix]['plugin_id']
        title = tree_list[root_ix]['title']
        defaults = tree_list[root_ix]['plugin_parameter_defaults']
        tree[root_ix] = {'plugin_id': plugin_id,
                         'title': title,
                         'plugin_parameter_defaults': defaults,
                         'child_indices': []}
        for ix, d in enumerate(tree_list):
            if ix != root_ix:
                if not tree[ix]:
                    plugin_id = d['plugin_id']
                    title = d['title']
                    defaults = d['plugin_parameter_defaults']
                    tree[ix] = {'plugin_id': plugin_id,
                                'title': title,
                                'plugin_parameter_defaults': defaults,
                                'child_indices': []}
                prev_ix = d['previous']
                if tree[prev_ix]:
                    tree[prev_ix]['child_indices'].append(ix)
                else:
                    plugin_id = tree_list[prev_ix]['plugin_id']
                    title = tree_list[prev_ix]['title']
                    defaults = tree_list[prev_ix]['plugin_parameter_defaults']
                    tree[prev_ix] = {'plugin_id': plugin_id,
                                     'title': title,
                                     'plugin_parameter_defaults': defaults,
                                     'child_indices': [ix]}
        return {'root_index': root_ix, 'tree': tree}

    @staticmethod
    def _add_plugin_tree_to_pipeline(pipeline, tree_dict):
        """
        Internal custom method to associate a tree of plugins to a pipeline in the DB.
        """
        # here a piping precedes another piping if its corresponding plugin precedes
        # the other piping's plugin in the pipeline
        root_ix = tree_dict['root_index']
        tree = tree_dict['tree']
        root_plg = Plugin.objects.get(pk=tree[root_ix]['plugin_id'])
        title = tree[root_ix]['title']
        root_plg_piping = PluginPiping.objects.create(title=title, pipeline=pipeline,
                                                      plugin=root_plg)
        defaults = tree[root_ix]['plugin_parameter_defaults']
        root_plg_piping.save(parameter_defaults=defaults)

        plg_pipings_dict = {root_ix: root_plg_piping}  # map from indices to pipings

        # breath-first traversal
        piping_queue = deque()
        piping_queue.append(root_plg_piping)
        ix_queue = deque()
        ix_queue.append(root_ix)
        while len(piping_queue):
            curr_ix = ix_queue.popleft()
            curr_piping = piping_queue.popleft()
            for ix in tree[curr_ix]['child_indices']:
                plg = Plugin.objects.get(pk=tree[ix]['plugin_id'])
                title = tree[ix]['title']
                plg_piping = PluginPiping.objects.create(title=title, pipeline=pipeline,
                                                         plugin=plg, previous=curr_piping)
                defaults = tree[ix]['plugin_parameter_defaults']
                plg_piping.save(parameter_defaults=defaults)
                plg_pipings_dict[ix] = plg_piping
                ix_queue.append(ix)
                piping_queue.append(plg_piping)

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


@file_serializer(required=True)
class PipelineSourceFileSerializer(serializers.HyperlinkedModelSerializer):
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
        pipeline = pipeline_serializer.save(owner=owner)

        # file will be stored to Swift at:
        # SWIFT_CONTAINER_NAME/PIPELINES/<uploader_username>/<filename>
        folder_path = f'PIPELINES/{uploader.username}'
        (parent_folder, tf) = ChrisFolder.objects.get_or_create(path=folder_path,
                                                                owner=owner)
        if tf:
            parent_folder.grant_public_access()

        fname = validated_data['fname']
        filename = os.path.basename(fname.name)
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
        plugin_tree = []
        for node in pipeline_repr.get('plugin_tree', []):
            plugin = node.get('plugin')
            if not plugin:
                error_msg = "A 'plugin' key is required for all plugin_tree nodes."
                raise serializers.ValidationError({'fname': [error_msg]})
            try:
                plg_list = plugin.strip().split(' ')
                plugin_name = plg_list[0]
                plugin_version = plg_list[1:][-1][1:]
            except Exception:
                error_msg = "Missing plugin name or version."
                raise serializers.ValidationError({'fname': [error_msg]})

            defaults_dict = node.get('plugin_parameter_defaults', {})
            plg_param_defaults = []
            for key in defaults_dict:
                plg_param_defaults.append({'name': key, 'default': defaults_dict[key]})

            canonical_node = {
                'title': node.get('title'),
                'plugin_name': plugin_name,
                'plugin_version': plugin_version,
                'previous': node.get('previous')
            }
            if plg_param_defaults:
                canonical_node['plugin_parameter_defaults'] = plg_param_defaults

            plugin_tree.append(canonical_node)

        pipeline_repr['plugin_tree'] = json.dumps(plugin_tree)
        return pipeline_repr

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
        Custom method to get the correct url for the serialized object regardless of
        its type.
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
