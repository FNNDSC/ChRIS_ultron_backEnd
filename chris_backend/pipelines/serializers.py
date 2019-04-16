
import json

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework.reverse import reverse

from collectionjson.fields import ItemLinkField
from plugins.models import Plugin, TYPES
from plugininstances.models import PluginInstance

from .models import Pipeline, PluginPiping
from .models import DefaultPipingFloatParameter, DefaultPipingIntParameter
from .models import DefaultPipingBoolParameter, DefaultPipingPathParameter
from .models import DefaultPipingStrParameter


class PipelineSerializer(serializers.HyperlinkedModelSerializer):
    plugin_id_tree = serializers.JSONField(write_only=True, required=False)
    plugin_inst_id = serializers.IntegerField(min_value=1, write_only=True,
                                              required=False)
    owner_username = serializers.ReadOnlyField(source='owner.username')
    plugins = serializers.HyperlinkedIdentityField(view_name='pipeline-plugin-list')
    plugin_pipings = serializers.HyperlinkedIdentityField(
        view_name='pipeline-pluginpiping-list')
    default_parameters = serializers.HyperlinkedIdentityField(
        view_name='pipeline-defaultparameter-list')
    instances = serializers.HyperlinkedIdentityField(view_name='pipelineinstance-list')

    class Meta:
        model = Pipeline
        fields = ('url', 'id', 'name', 'locked', 'authors', 'category', 'description',
                  'plugin_id_tree', 'plugin_inst_id', 'owner_username', 'plugins',
                  'plugin_pipings', 'default_parameters', 'instances')

    def create(self, validated_data):
        """
        Overriden to create the pipeline and associate to it a tree of plugins computed
        either from an existing plugin instance or from a passed tree.
        """
        validated_data.pop('locked', None)  # locked is not accepted at creation
        tree_dict = validated_data.pop('plugin_id_tree', None)
        root_plg_inst = validated_data.pop('plugin_inst_id', None)
        pipeline = super(PipelineSerializer, self).create(validated_data)

        if not tree_dict:  # generate tree_dict from passed plugin instance
            tree_dict = {'root_index': 0, 'tree': []}
            curr_ix = 0
            queue = [root_plg_inst]
            while len(queue) > 0:
                visited_instance = queue.pop()
                plg_id = visited_instance.plugin.id
                child_instances = list(visited_instance.next.all())
                queue.extend(child_instances)
                lower_ix = curr_ix + 1
                upper_ix = lower_ix + len(child_instances)
                child_indices = list(range(lower_ix, upper_ix))
                tree_dict['tree'].append({'plugin_id': plg_id,
                                          'child_indices': child_indices})
                curr_ix = upper_ix - 1
        PipelineSerializer._add_plugin_tree_to_pipeline(pipeline, tree_dict)
        return pipeline

    def update(self, instance, validated_data):
        """
        Overriden to remove parameters that are not allowed to be used on update.
        """
        validated_data.pop('plugin_id_tree', None)
        validated_data.pop('plugin_inst_id', None)
        return super(PipelineSerializer, self).update(instance, validated_data)

    def validate(self, data):
        """
        Overriden to validate that at least one of two fields are in data
        when creating a new pipeline.
        """
        if not self.instance:  # this validation only happens on create and not on update
            if 'plugin_id_tree' not in data and 'plugin_inst_id' not in data:
                raise serializers.ValidationError(
                    {'non_field_errors': ["At least one of the fields 'plugin_id_tree' "
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
                {'plugin_inst_id': ["Couldn't find any plugin instance with id %s." %
                                    plugin_inst_id]})
        plg = plg_inst.plugin
        if plg.type == 'fs':
            raise serializers.ValidationError(
                {'plugin_inst_id':
                     ["Plugin instance of %s which is of type 'fs' and therefore can "
                      "not be used as the root of a new pipeline." % plg.name]})
        return plg_inst

    def validate_plugin_id_tree(self, plugin_id_tree):
        """
        Overriden to validate the tree of plugin ids. It should be a list of dictionaries.
        Each dictionary is a tree node containing a plugin id and the index of the
        previous node in the list.
        """
        try:
            plugin_id_list = list(json.loads(plugin_id_tree))
        except json.decoder.JSONDecodeError:
            raise serializers.ValidationError(
                {'plugin_id_tree': ["Invalid JSON string %s." % plugin_id_tree]})
        except Exception:
            raise serializers.ValidationError(
                {'plugin_id_tree': ["Invalid tree list in %s" % plugin_id_tree]})
        if len(plugin_id_list) == 0:
            raise serializers.ValidationError(
                {'plugin_id_tree': ["Invalid empty list in %s" % plugin_id_tree]})

        for d in plugin_id_list:
            try:
                prev_ix = d['previous_index']
                plg_id = d['plugin_id']
                plg = Plugin.objects.get(pk=plg_id)
            except ObjectDoesNotExist:
                raise serializers.ValidationError(
                    {'plugin_id_tree': ["Couldn't find any plugin with id %s" % plg_id]})
            except Exception:
                raise serializers.ValidationError(
                    {'plugin_id_tree':
                         ["Object %s must be a JSON object with 'plugin_id' and "
                          "'previous_index' properties." % d]})
            if plg.type == 'fs':
                raise serializers.ValidationError(
                    {'plugin_id_tree': ["Plugin %s is of type 'fs' and therefore can "
                                        "not be used to create a pipeline." % plg]})
        try:
            tree_dict = PipelineSerializer.get_tree(plugin_id_list)
            PipelineSerializer.validate_tree(tree_dict)
        except (ValueError, Exception) as e:
            raise serializers.ValidationError({'plugin_id_tree': [str(e)]})
        return tree_dict

    def validate_locked(self, locked):
        """
        Overriden to raise a validation error when the locked value is false and there
        are plugin parameters in the pipeline without default values.
        """
        error_msg = 'Pipeline can not be unlocked until all plugin parameters have ' \
                    'default values.'
        if not locked and self.instance:
            try:
                self.instance.check_parameter_default_values()
            except ValueError:
                raise serializers.ValidationError({'locked': [error_msg]})
        return locked

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
        queue = [root_ix]
        while len(queue):
            curr_ix = queue.pop(0)
            nodes.append(curr_ix)
            queue.extend(tree[curr_ix]['child_indices'])
        if len(nodes) < num_nodes:
            raise ValueError("Tree is not connected!")

    @staticmethod
    def get_tree(tree_list):
        """
        Custom method to return a dictionary containing a list of nodes representing a
        tree of plugins and the index of the root of the tree. Each node is a dictionary
        containing the plugin id and the list of child indices.
        """
        try:
            root_ix = [ix for ix,d in enumerate(tree_list)
                       if d['previous_index'] is None][0]
        except IndexError:
            raise ValueError("Couldn't find the root of the tree in %s" % tree_list)
        tree = [None] * len(tree_list)
        tree[root_ix] = {'plugin_id': tree_list[root_ix]['plugin_id'], 'child_indices':[]}
        for ix, d in enumerate(tree_list):
            if ix != root_ix:
                if not tree[ix]:
                    tree[ix] = {'plugin_id': d['plugin_id'], 'child_indices': []}
                prev_ix = d['previous_index']
                try:
                    if tree[prev_ix]:
                        tree[prev_ix]['child_indices'].append(ix)
                    else:
                        tree[prev_ix] = {'plugin_id': tree_list[prev_ix]['plugin_id'],
                                         'child_indices': [ix]}
                except (IndexError, TypeError):
                    raise ValueError("Invalid 'previous_index' for node %s" % d)
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
        root_plg_piping = PluginPiping.objects.create(pipeline=pipeline, plugin=root_plg)
        root_plg_piping.save()
        # breath-first traversal
        piping_queue = [root_plg_piping]
        ix_queue = [root_ix]
        while len(piping_queue):
            curr_ix = ix_queue.pop(0)
            curr_piping = piping_queue.pop(0)
            for ix in tree[curr_ix]['child_indices']:
                plg = Plugin.objects.get(pk=tree[ix]['plugin_id'])
                plg_piping = PluginPiping.objects.create(pipeline=pipeline, plugin=plg,
                                                         previous=curr_piping)
                plg_piping.save()
                ix_queue.append(ix)
                piping_queue.append(plg_piping)


class PluginPipingSerializer(serializers.HyperlinkedModelSerializer):
    plugin_id = serializers.ReadOnlyField(source='plugin.id')
    pipeline_id = serializers.ReadOnlyField(source='pipeline.id')
    previous_id = serializers.ReadOnlyField(source='previous.id')
    previous = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                 read_only=True)
    plugin = serializers.HyperlinkedRelatedField(view_name='plugin-detail',
                                                 read_only=True)
    pipeline = serializers.HyperlinkedRelatedField(view_name='pipeline-detail',
                                                   read_only=True)

    class Meta:
        model = PluginPiping
        fields = ('url', 'id', 'plugin_id', 'pipeline_id', 'previous_id', 'previous',
                  'plugin', 'pipeline')


class DefaultPipingStrParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingStrParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')


class DefaultPipingIntParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingIntParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')


class DefaultPipingFloatParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingFloatParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')


class DefaultPipingBoolParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingBoolParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')


class DefaultPipingPathParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
    param_id = serializers.ReadOnlyField(source='plugin_param.id')
    param_name = serializers.ReadOnlyField(source='plugin_param.name')
    type = serializers.ReadOnlyField(source='plugin_param.type')
    plugin_piping = serializers.HyperlinkedRelatedField(view_name='pluginpiping-detail',
                                                   read_only=True)
    plugin_param = serializers.HyperlinkedRelatedField(view_name='pluginparameter-detail',
                                                       read_only=True)

    class Meta:
        model = DefaultPipingPathParameter
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')


class GenericDefaultPipingParameterSerializer(serializers.HyperlinkedModelSerializer):
    previous_plugin_piping_id = serializers.ReadOnlyField(
        source='plugin_piping.previous_id')
    plugin_piping_id = serializers.ReadOnlyField(source='plugin_piping.id')
    plugin_id = serializers.ReadOnlyField(source='plugin_piping.plugin_id')
    plugin_name = serializers.ReadOnlyField(source='plugin_param.plugin.name')
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
        fields = ('url', 'id', 'value', 'type', 'plugin_piping_id',
                  'previous_plugin_piping_id', 'param_name', 'param_id', 'plugin_piping',
                  'plugin_name', 'plugin_id', 'plugin_param')

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
                                        'boolean': DefaultPipingBoolParameterSerializer,
                                        'path': DefaultPipingPathParameterSerializer}
