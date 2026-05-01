
import logging

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultIntParameter
from pipelines.models import Pipeline
from pipelines.models import PluginPiping
from pipelines.models import DEFAULT_PIPING_PARAMETER_MODELS


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ModelTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'prefix': {'type': 'string', 'optional': False}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create plugin
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

        # add plugin's parameters
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='prefix',
            type=self.plugin_ds_parameters['prefix']['type'],
            optional=self.plugin_ds_parameters['prefix']['optional'])  # this plugin parameter has no default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name, owner=user)

        # create two plugin pipings
        self.pips = []
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip1', plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip)
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip2', plugin=plugin_ds,
                                                       previous=pip, pipeline=pipeline)
        self.pips.append(pip)

        # create default values for the piping parameters as the corresponding plugin
        # didn't set a default
        param_type = self.plugin_ds_parameters['prefix']['type']
        default_model_class = DEFAULT_PIPING_PARAMETER_MODELS[param_type]
        for i in range(2):
            (default_piping_param, tf) = default_model_class.objects.get_or_create(
                plugin_piping=self.pips[i], plugin_param=plg_param_ds)
            if i == 0:
                default_piping_param.value = ""
            else:
                default_piping_param.value = "test" + str(i)
            default_piping_param.save()


    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class PipelineModelTests(ModelTests):

    def test_get_pipings_parameters_names(self):
        """
        Test whether custom get_pipings_parameters_names method returns the list of all
        the plugin parameter names for all the associated plugin pipings. The name of the
        parameters should be transformed to have the plugin id, piping id and previous
        piping id as a prefix.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        param = plugin_ds.parameters.get(name='prefix')
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        param_names = pipeline.get_pipings_parameters_names()
        self.assertEqual(len(param_names), 2)
        self.assertEqual(param_names[0], "%s_%s_%s_%s" %
                         (plugin_ds.id, self.pips[0].id, "null", param.name))
        self.assertEqual(param_names[1], "%s_%s_%s_%s" %
                         (plugin_ds.id, self.pips[1].id, self.pips[0].id, param.name))

    def test_get_pipings_tree(self):
        """
        Test whether custom get_pipings_tree method returns a dictionary containing a
        dictionary representing a tree of pipings and the id of the piping that is the
        root of the tree. The keys of the dictionary tree should be the pipings' ids and
        the values the dictionaries containing the piping and the list of child pipings' ids.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        tree_dict = pipeline.get_pipings_tree()
        root_id = tree_dict['root_id']
        tree = tree_dict['tree']
        self.assertEqual(root_id, self.pips[0].id)
        self.assertEqual(tree[root_id], {'piping': self.pips[0], 'child_ids': [self.pips[1].id]})

    def test_check_parameter_defaults(self):
        """
        Test whether custom check_parameter_defaults method raises an exception if
        any of the plugin parameters associated to any of the pipings in the pipeline
        doesn't have a default value.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        # add a new plugin piping to pipeline but do not set a default value for
        # the plugin parameter
        PluginPiping.objects.get_or_create(plugin=plugin_ds, pipeline=pipeline,
                                           previous=self.pips[1])
        with self.assertRaises(ValueError):
            pipeline.check_parameter_defaults()

    def test_get_accesible_pipelines(self):
        """
        Test whether custom get_accesible_pipelines method returns a filtered queryset
        with all the pipelines that are accessible to a given user (not locked or
        otherwise own by the user).
        """
        user1 = User.objects.get(username=self.username)
        # create new user
        user2 = User.objects.create_user(username='testuser', password='testuser-pass')
        accessible_pipelines_user1 = Pipeline.get_accesible_pipelines(user1)
        self.assertEqual(len(accessible_pipelines_user1),1)
        self.assertEqual(accessible_pipelines_user1[0], Pipeline.objects.all()[0])
        self.assertEqual(len(Pipeline.get_accesible_pipelines(user2)), 0)

    def test_get_plugin_tree(self):
        """
        Test whether get_plugin_tree returns the BFS-ordered list of canonical
        node dicts for the pipeline (one per piping, with plugin_id, title,
        previous title, and plugin_parameter_defaults).
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_tree = pipeline.get_plugin_tree()
        self.assertEqual(len(plugin_tree), 2)
        self.assertEqual(plugin_tree[0]['title'], 'pip1')
        self.assertIsNone(plugin_tree[0]['previous'])
        self.assertEqual(plugin_tree[1]['title'], 'pip2')
        self.assertEqual(plugin_tree[1]['previous'], 'pip1')

    def test__build_tree_nodes_from_defaults(self):
        """
        Test that _build_tree_nodes_from_defaults aggregates default-parameter
        rows into the per-piping node dicts and the auxiliary id/title/ts maps.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        defaults = pipeline.get_default_parameters()
        nodes, id_to_title, is_ts = Pipeline._build_tree_nodes_from_defaults(defaults)
        self.assertEqual(set(nodes.keys()), {'pip1', 'pip2'})
        self.assertIsNone(nodes['pip1']['previous'])
        self.assertEqual(nodes['pip2']['previous'], 'pip1')
        self.assertEqual(id_to_title[self.pips[0].id], 'pip1')
        self.assertEqual(id_to_title[self.pips[1].id], 'pip2')
        # neither piping is a 'ts' plugin in the fixture
        self.assertFalse(is_ts['pip1'])
        self.assertFalse(is_ts['pip2'])
        # one default parameter ('prefix') per piping
        self.assertEqual(len(nodes['pip1']['plugin_parameter_defaults']), 1)
        self.assertEqual(nodes['pip1']['plugin_parameter_defaults'][0]['name'],
                         'prefix')

    def test__resolve_ts_parent_titles_rewrites_ids(self):
        """
        Test that _resolve_ts_parent_titles replaces the comma-separated piping
        ids in the 'plugininstances' default with the corresponding piping titles.
        """
        node = {'plugin_parameter_defaults': [
            {'name': 'plugininstances', 'default': '7,9'},
            {'name': 'other', 'default': 'x'},
        ]}
        Pipeline._resolve_ts_parent_titles(node, {7: 'a', 9: 'b'})
        self.assertEqual(node['plugin_parameter_defaults'][0]['default'], 'a,b')
        # other entries are untouched
        self.assertEqual(node['plugin_parameter_defaults'][1]['default'], 'x')

    def test__resolve_ts_parent_titles_empty_default(self):
        """
        Test that _resolve_ts_parent_titles is a no-op when 'plugininstances'
        default is the empty string.
        """
        node = {'plugin_parameter_defaults': [
            {'name': 'plugininstances', 'default': ''},
        ]}
        Pipeline._resolve_ts_parent_titles(node, {})
        self.assertEqual(node['plugin_parameter_defaults'][0]['default'], '')

    def test__build_title_adjacency(self):
        """
        Test that _build_title_adjacency identifies the root title and produces
        the expected child-list dict.
        """
        nodes = {
            'a': {'plugin_parameter_defaults': [], 'previous': None},
            'b': {'plugin_parameter_defaults': [], 'previous': 'a'},
            'c': {'plugin_parameter_defaults': [], 'previous': 'a'},
            'd': {'plugin_parameter_defaults': [], 'previous': 'b'},
        }
        is_ts = {'a': False, 'b': False, 'c': False, 'd': False}
        root, adjacency = Pipeline._build_title_adjacency(nodes, is_ts, {})
        self.assertEqual(root, 'a')
        self.assertEqual(set(adjacency['a']), {'b', 'c'})
        self.assertEqual(adjacency['b'], ['d'])
        self.assertEqual(adjacency['c'], [])
        self.assertEqual(adjacency['d'], [])

    def test__bfs_order_plugin_tree(self):
        """
        Test that _bfs_order_plugin_tree visits root first, then its children in
        the order given by the adjacency, then their children, etc.
        """
        nodes = {'a': {'title': 'a'}, 'b': {'title': 'b'},
                 'c': {'title': 'c'}, 'd': {'title': 'd'}}
        adjacency = {'a': ['b', 'c'], 'b': ['d'], 'c': [], 'd': []}
        ordered = Pipeline._bfs_order_plugin_tree('a', adjacency, nodes)
        self.assertEqual([n['title'] for n in ordered], ['a', 'b', 'c', 'd'])


class PluginPipingModelTests(ModelTests):

    def test_save(self):
        """
        Test whether overriden save method saves the default plugin parameters' values
        associated with this piping.
        """
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        # add a parameter with a default
        (plg_param_ds, tf)= PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyInt',
            type='integer',
            optional=True
        )
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param_ds, value=1)  # set plugin parameter default
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        pip = PluginPiping()
        pip.plugin = plugin_ds
        pip.pipeline = pipeline
        pip.save()
        defaults = pip.integer_param.all()
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0].value, 1)

    def test_check_parameter_defaults(self):
        """
        Test whether custom check_parameter_defaults method raises an exception if
        any of the plugin parameters associated to the piping doesn't have a default value.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        plugin_ds = Plugin.objects.get(meta__name=self.plugin_ds_name)
        # add a new plugin piping to pipeline but do not set a default value for
        # the plugin parameter
        (pip, tf) = PluginPiping.objects.get_or_create(plugin=plugin_ds, pipeline=pipeline,
                                           previous=self.pips[1])
        with self.assertRaises(ValueError):
            pip.check_parameter_defaults()
