
import json
from collections import deque

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers
from rest_framework.reverse import reverse

from core.graph import Graph
from collectionjson.fields import ItemLinkField
from plugins.models import Plugin, TYPES
from plugins.serializers import DEFAULT_PARAMETER_SERIALIZERS
from plugininstances.models import PluginInstance

from .models import Pipeline, PluginPiping
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
    instances = serializers.HyperlinkedIdentityField(view_name='pipelineinstance-list')
    workflows = serializers.HyperlinkedIdentityField(view_name='workflow-list')

    class Meta:
        model = Pipeline
        fields = ('url', 'id', 'name', 'locked', 'authors', 'category', 'description',
                  'plugin_tree', 'plugin_inst_id', 'owner_username', 'creation_date',
                  'modification_date', 'plugins', 'plugin_pipings', 'default_parameters',
                  'instances', 'workflows')

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
            titles = []
            while len(queue) > 0:
                visited_instance = queue.pop()
                plg_id = visited_instance.plugin.id
                child_instances = list(visited_instance.next.all())
                queue.extend(child_instances)
                lower_ix = curr_ix + 1
                upper_ix = lower_ix + len(child_instances)
                child_indices = list(range(lower_ix, upper_ix))
                parameter_instances = visited_instance.get_parameter_instances()

                # parameter defaults assigned from the plugin instance's parameter values
                defaults = [{'name': p_inst.plugin_param.name, 'default': p_inst.value}
                            for p_inst in parameter_instances]

                if visited_instance.title in titles:  # avoid duplicated titles
                    raise serializers.ValidationError(
                        {'non_field_errors': ["The tree of plugin instances contain "
                                              "duplicated (perhaps empty) titles"]})
                titles.append(visited_instance.title)

                tree_dict['tree'].append({'plugin_id': plg_id,
                                          'title': visited_instance.title,
                                          'plugin_parameter_defaults': defaults,
                                          'child_indices': child_indices})
                curr_ix = upper_ix - 1
        PipelineSerializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        return pipeline

    def update(self, instance, validated_data):
        """
        Overriden to remove parameters that are not allowed to be used on update and
        to add modification date.
        """
        validated_data.pop('plugin_tree', None)
        validated_data.pop('plugin_inst_id', None)
        validated_data.update({'modification_date': timezone.now()})
        return super(PipelineSerializer, self).update(instance, validated_data)

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data
        when creating a new pipeline.
        """
        if not self.instance:  # this validation only happens on create and not on update
            if 'plugin_tree' not in data and 'plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'plugin_tree' "
                                          "or 'plugin_inst_id' must be provided."]})
            if 'plugin_tree' in data:
                # check that defaults for all plugin parameters can be defined
                tree = data['plugin_tree']['tree']
                for node in tree:
                    plg = Plugin.objects.get(pk=node['plugin_id'])
                    parameters = plg.parameters.all()
                    for parameter in parameters:
                        default = parameter.get_default()
                        parameter_default = default.value if default else None
                        if parameter_default is None:  # no default provided by the plugin
                            plg_param_defaults = node['plugin_parameter_defaults']
                            param_default = [d for d in plg_param_defaults if
                                                  d['name'] == parameter.name]
                            if not param_default:  # no default provided by the user
                                error_msg = f"Missing default value for " \
                                            f"parameter {parameter.name} for plugin " \
                                            f"{plg}. Pipeline can not be created until " \
                                            f"all plugin parameters have default values."
                                raise serializers.ValidationError(
                                    {'plugin_tree': [error_msg]})
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
                [f"Plugin instance of %s which is of type {plg.meta.type} and therefore "
                 f"can not be used as the root of a new pipeline." % plg.meta.name])
        return plg_inst

    def validate_plugin_tree(self, plugin_tree):
        """
        Overriden to validate the tree of plugin ids. It should be a list of dictionaries.
        Each dictionary is a tree node containing a unique title within the tree, the
        index of the previous node in the list and either a plugin id or a plugin name
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

        nplugin = len(plugin_list)
        if nplugin == 0:
            msg = ["Invalid empty list in %s" % plugin_tree]
            raise serializers.ValidationError(msg)

        plugin_is_ts_list = []
        titles = []
        for d in plugin_list:
            try:
                prev_ix = d['previous_index']
                if prev_ix is not None:
                    prev_ix = int(prev_ix)

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
                msg = ["Object %s must be a JSON object with 'previous_index' int and "
                       "either 'plugin_id' int or 'plugin_name' and 'plugin_version' "
                       "str properties." % d]
                raise serializers.ValidationError(msg)

            if plg.meta.type == 'fs':
                msg = ["Plugin %s is of type 'fs' and therefore can not be used to "
                       "create a pipeline." % plg]
                raise serializers.ValidationError(msg)

            plugin_is_ts_list.append(plg.meta.type == 'ts')

            title = d.get('title')
            if title is None:
                raise serializers.ValidationError(['All nodes in the pipeline must have '
                                                   'a title'])
            else:
                if title in titles:
                    raise serializers.ValidationError(
                        ["Pipeline tree can not contain duplicated titles"])
                titles.append(title)
                piping_serializer = PluginPipingSerializer(data={'title': title})
                try:
                    piping_serializer.is_valid(raise_exception=True)
                except serializers.ValidationError as e:
                    raise serializers.ValidationError([f'Invalid title: {title}, '
                                                       f'detail: {str(e)}'])

            if 'plugin_parameter_defaults' in d:
                param_defaults = d['plugin_parameter_defaults']
                PipelineSerializer.validate_plugin_parameter_defaults(plg, prev_ix,
                                                                      nplugin,
                                                                      param_defaults)
            else:
                d['plugin_parameter_defaults'] = []

        try:
            tree_dict = PipelineSerializer.get_tree(plugin_list)
            PipelineSerializer.validate_tree(tree_dict)
            if True in plugin_is_ts_list:
                PipelineSerializer.validate_DAG(plugin_list, plugin_is_ts_list)
        except (ValueError, Exception) as e:
            raise serializers.ValidationError([str(e)])
        return tree_dict

    @staticmethod
    def validate_plugin_parameter_defaults(plugin, previous_ix, nplugin,
                                           parameter_defaults):
        """
        Custom method to validate the parameter names and their default values given
        for a plugin in the plugin tree.
        """
        parameters = plugin.parameters.all()
        for d in parameter_defaults:
            try:
                name = d['name']
                default = d['default']
            except KeyError:
                error_msg = "Invalid parameter default object %s. Each default object " \
                            "must have 'name' and 'default' properties." % d
                raise serializers.ValidationError({'plugin_tree': [error_msg]})

            param = [param for param in parameters if param.name == name]
            if not param:
                error_msg = "Could not find any parameter with name %s for plugin %s." % \
                            (name, plugin.meta.name)
                raise serializers.ValidationError({'plugin_tree': [error_msg]})

            default_param_serializer = DEFAULT_PARAMETER_SERIALIZERS[param[0].type](
                data={'value': default})
            if not default_param_serializer.is_valid():
                error_msg = "Invalid default value %s for parameter %s for plugin %s." % \
                            (default, name, plugin.meta.name)
                raise serializers.ValidationError({'plugin_tree': [error_msg]})

            if plugin.meta.type == 'ts' and name == 'plugininstances':
                if previous_ix is None and default:
                    error_msg = f"The plugininstances parameter's default must be " \
                                f"the empty string for 'ts' plugins with null " \
                                f"previous_index"
                    raise serializers.ValidationError({'plugin_tree': [error_msg]})

                if previous_ix is not None and not default:
                    error_msg = f"Invalid default value '{default}' for parameter " \
                                f"{name} for plugin {plugin.meta.name}. Must " \
                                f"contain previous_index."
                    raise serializers.ValidationError({'plugin_tree': [error_msg]})

                if default:
                    try:
                        parent_ixs = [int(parent_ix) for parent_ix in default.split(',')]
                    except ValueError:
                        error_msg = f"The plugininstances value for plugin " \
                                    f"{plugin.meta.name} must be a string " \
                                    f"representing a comma-separated list of integers"
                        raise serializers.ValidationError({'plugin_tree': [error_msg]})

                    if previous_ix not in parent_ixs:
                        error_msg = f"Invalid default value '{default}' for parameter " \
                                    f"{name} for plugin {plugin.meta.name}. Must " \
                                    f"contain previous_index."
                        raise serializers.ValidationError({'plugin_tree': [error_msg]})

                    for ix in parent_ixs:
                        if ix > nplugin - 1:
                            error_msg = f"Invalid default value '{default}' for " \
                                        f"parameter {name} for plugin " \
                                        f"{plugin.meta.name}. Parent index {ix} is out " \
                                        f"of range."
                            raise serializers.ValidationError({'plugin_tree': [error_msg]})

    @staticmethod
    def get_tree(tree_list):
        """
        Custom method to return a dictionary containing a list of nodes representing a
        tree of plugins and the index of the root of the tree. Each node is a dictionary
        containing the plugin id, its parameter defaults and the list of child indices.
        """
        try:
            root_ix = [ix for ix,d in enumerate(tree_list)
                       if d['previous_index'] is None][0]
        except IndexError:
            raise ValueError("Couldn't find the root of the tree in %s" % tree_list)
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
                prev_ix = d['previous_index']
                try:
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
                except (IndexError, TypeError):
                    raise ValueError("Invalid 'previous_index' for node %s" % d)
        return {'root_index': root_ix, 'tree': tree}

    @staticmethod
    def validate_tree(tree_dict):
        """
        Custom method to validate whether the represented tree in tree_dict dictionary
        is a single connected component.
        """
        root_ix = tree_dict['root_index']
        tree = tree_dict['tree']
        num_nodes = len(tree)

        # breath-first traversal
        nodes = []
        queue = deque()
        queue.append(root_ix)
        while len(queue):
            curr_ix = queue.popleft()
            nodes.append(curr_ix)
            queue.extend(tree[curr_ix]['child_indices'])
        if len(nodes) < num_nodes:
            raise ValueError("Pipeline's tree is not connected!")

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
            previous_ix = d['previous_index']
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
            raise ValueError(f"Pipeline's DAG has an indices cycle: {cycle}!")

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

    def get_plugin_tree(self, obj):
        """
        Overriden to get the plugin_tree JSON string.
        """
        return json.dumps(obj.get_plugin_tree())

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

    def get_value(self, obj):
        """
        Overriden to get the default parameter value regardless of its type.
        """
        return obj.value


DEFAULT_PIPING_PARAMETER_SERIALIZERS = {'string': DefaultPipingStrParameterSerializer,
                                        'integer': DefaultPipingIntParameterSerializer,
                                        'float': DefaultPipingFloatParameterSerializer,
                                        'boolean': DefaultPipingBoolParameterSerializer}
