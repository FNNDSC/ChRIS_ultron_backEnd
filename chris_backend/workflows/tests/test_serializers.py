
import logging
import json
from unittest import mock

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import serializers

from plugininstances.models import PluginInstance
from plugins.models import PluginMeta, Plugin
from plugins.models import ComputeResource
from plugins.models import PluginParameter, DefaultStrParameter, DefaultIntParameter
from pipelines.models import Pipeline, PluginPiping
from workflows._types import GivenNodeInfo, ComputeResourceName
from workflows.models import Workflow
from workflows.serializers import WorkflowSerializer


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL
CHRIS_SUPERUSER_PASSWORD = settings.CHRIS_SUPERUSER_PASSWORD


class SerializerTests(TestCase):

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = CHRIS_SUPERUSER_PASSWORD

        self.plugin_fs_name = "simplefsapp"
        self.plugin_fs_parameters = {'dir': {'type': 'string', 'optional': True,
                                             'default': "./"}}
        self.plugin_ds_name = "simpledsapp"
        self.plugin_ds_parameters = {'dummyInt': {'type': 'integer', 'optional': True,
                                                  'default': 111111}}
        self.username = 'foo'
        self.password = 'foo-pass'

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create plugins
        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_fs_name, type='fs')
        (plugin_fs, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_fs.compute_resources.set([self.compute_resource])
        plugin_fs.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name=self.plugin_ds_name, type='ds')
        (plugin_ds, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin_ds.compute_resources.set([self.compute_resource])
        plugin_ds.save()

        # add plugins' parameters
        (plg_param_fs, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_fs,
            name='dir',
            type=self.plugin_fs_parameters['dir']['type'],
            optional=self.plugin_fs_parameters['dir']['optional'])
        default = self.plugin_fs_parameters['dir']['default']
        DefaultStrParameter.objects.get_or_create(plugin_param=plg_param_fs,
                                                   value=default)  # set plugin parameter default

        # add a parameter with a default
        (plg_param_ds, tf) = PluginParameter.objects.get_or_create(
            plugin=plugin_ds,
            name='dummyInt',
            type=self.plugin_ds_parameters['dummyInt']['type'],
            optional=self.plugin_ds_parameters['dummyInt']['optional']
        )
        default = self.plugin_ds_parameters['dummyInt']['default']
        DefaultIntParameter.objects.get_or_create(plugin_param=plg_param_ds,
                                                  value=default)  # set plugin parameter default

        # create user
        user = User.objects.create_user(username=self.username, password=self.password)

        # create a pipeline
        self.pipeline_name = 'Pipeline1'
        (pipeline, tf) = Pipeline.objects.get_or_create(name=self.pipeline_name,
                                                        owner=user, category='test')

        # create two plugin pipings
        self.pips = []
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip1', plugin=plugin_ds,
                                                       pipeline=pipeline)
        self.pips.append(pip)
        (pip, tf) = PluginPiping.objects.get_or_create(title='pip2', plugin=plugin_ds,
                                                       previous=pip, pipeline=pipeline)
        self.pips.append(pip)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class WorkflowSerializerTests(SerializerTests):

    def setUp(self):
        super(WorkflowSerializerTests, self).setUp()

        self.owner = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name=self.plugin_fs_name)
        (self.pl_inst, tf) = PluginInstance.objects.get_or_create(
            plugin=plugin, owner=self.owner,
            compute_resource=plugin.compute_resources.all()[0])

    def test_create(self):
        """
        Test whether overriden 'create' method successfully creates a new workflow after
        deleting 'previous_plugin_inst_id' and 'nodes_info' from serializer data as they
        are not model fields.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)

        data = {'previous_plugin_inst_id': self.pl_inst.id,
                'nodes_info': json.dumps([{"piping_id": self.pips[0].id,
                                           "title": "title1",
                                           "compute_resource_name": "host",
                                           "plugin_parameter_defaults": [{"name": "dummyInt", "default": 3}]},
                                          {"piping_id": self.pips[1].id,
                                           "title": "title2",
                                           "compute_resource_name": "host"}])}

        workflow_serializer = WorkflowSerializer(data=data)
        workflow_serializer.context['request'] = mock.Mock()
        workflow_serializer.context['request'].user = self.owner
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)
        workflow_serializer.is_valid(raise_exception=True)
        workflow_serializer.validated_data['pipeline'] = pipeline
        workflow_serializer.validated_data['owner'] = self.owner
        pipeline_inst = workflow_serializer.create(workflow_serializer.validated_data)

        self.assertNotIn('previous_plugin_inst_id', workflow_serializer.validated_data)
        self.assertNotIn('nodes_info', workflow_serializer.validated_data)
        self.assertIsInstance(pipeline_inst, Workflow)

    def test_validate_previous_plugin_inst_id(self):
        """
        Test whether overriden validate_previous_plugin_inst_id method validates that the
        provided previous plugin instance id exists in the DB and that the user can run
        plugins within the corresponding feed.
        """
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['request'] = mock.Mock()
        workflow_serializer.context['request'].user = self.owner

        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_previous_plugin_inst_id(self.pl_inst.id + 1)
        # create another user
        another_user = User.objects.create_user(username='boo', password='far')
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.context['request'].user = another_user
            workflow_serializer.validate_previous_plugin_inst_id(self.pl_inst.id)

    def test_validate_nodes_info(self):
        """
        Test whether overriden validate_nodes_info method validates the runtime data for
        the workflow. It should be a JSON string encoding a list of dictionaries. Each
        dictionary is a workflow node containing a plugin piping_id, compute_resource_name,
        title and a list of dictionaries called plugin_parameter_defaults. Each
        dictionary in this list has name and default keys.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps({}))
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([{"compute_resource_name": "host"}]))
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([{"piping_id": self.pips[0].id,
                                                                 "compute_resource_name": "unknown"},
                                                                {"piping_id": self.pips[1].id,
                                                                 "compute_resource_name": "host"}]))
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([{"piping_id": self.pips[0].id,
                                                                 "compute_resource_name": "host"},
                                                                {"piping_id": self.pips[1].id,
                                                                 "title": "c"*101,
                                                                 "compute_resource_name": "host"}]))
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([{"piping_id": self.pips[0].id,
                                                                 "title": "pip",
                                                                 "compute_resource_name": "host"},
                                                                {"piping_id": self.pips[1].id,
                                                                 "title": "pip",
                                                                 "compute_resource_name": "host"}]))

        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([{"piping_id": self.pips[0].id,
                                                                 "compute_resource_name": "host"},
                                                                {"piping_id": self.pips[1].id,
                                                                 "title": self.pips[0].title,
                                                                 "compute_resource_name": "host"}]))

        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(
                json.dumps([{"piping_id": self.pips[0].id, "compute_resource_name": "host",
                             "plugin_parameter_defaults": [{"name": "dummyInt", "default": "badInt"}]},
                            {"piping_id": self.pips[1].id,"compute_resource_name": "host"}])
            )
        with self.assertRaises(serializers.ValidationError) as e:
            workflow_serializer.validate_nodes_info(
                json.dumps([{"piping_id": self.pips[0].id,
                             "plugin_parameter_defaults": [{"name": "dummyInt"}]}])
            )

    def test_validate_canonicalizes(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        actual = workflow_serializer.validate_nodes_info(
            json.dumps([{"piping_id": self.pips[0].id, "compute_resource_name": "host"}])
        )
        expected = [
            GivenNodeInfo(
                piping_id=self.pips[0].id,
                compute_resource_name=ComputeResourceName("host"),
                title="pip1",
                plugin_parameter_defaults=[],
                cpu_limit=None,
                memory_limit=None,
                number_of_workers=None,
                gpu_limit=None,
            ),
            GivenNodeInfo(
                piping_id=self.pips[1].id,
                compute_resource_name=None,
                title="pip2",
                plugin_parameter_defaults=[],
                cpu_limit=None,
                memory_limit=None,
                number_of_workers=None,
                gpu_limit=None,
            )
        ]
        self.assertCountEqual(expected, actual)

    def test_no_nodes_info(self):
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        actual = workflow_serializer.validate_nodes_info(None)
        expected = [
            GivenNodeInfo(
                piping_id=self.pips[0].id,
                compute_resource_name=None,
                title="pip1",
                plugin_parameter_defaults=[],
                cpu_limit=None,
                memory_limit=None,
                number_of_workers=None,
                gpu_limit=None,
            ),
            GivenNodeInfo(
                piping_id=self.pips[1].id,
                compute_resource_name=None,
                title="pip2",
                plugin_parameter_defaults=[],
                cpu_limit=None,
                memory_limit=None,
                number_of_workers=None,
                gpu_limit=None,
            )
        ]
        self.assertCountEqual(expected, actual)

    def test_validate_nodes_info_resource_overrides_accepted(self):
        """
        Valid cpu_limit/memory_limit/number_of_workers/gpu_limit overrides
        (including Kubernetes-style string forms) round-trip through
        canonicalization untouched.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        actual = workflow_serializer.validate_nodes_info(json.dumps([
            {"piping_id": self.pips[0].id,
             "cpu_limit": "2000m", "memory_limit": "1Gi",
             "number_of_workers": 2, "gpu_limit": 0},
        ]))
        node = next(n for n in actual if n['piping_id'] == self.pips[0].id)
        self.assertEqual(node['cpu_limit'], "2000m")
        self.assertEqual(node['memory_limit'], "1Gi")
        self.assertEqual(node['number_of_workers'], 2)
        self.assertEqual(node['gpu_limit'], 0)
        # the unmentioned piping defaults stay at None
        other = next(n for n in actual if n['piping_id'] == self.pips[1].id)
        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            self.assertIsNone(other[f])

    def test_validate_nodes_info_resource_out_of_range_rejected(self):
        """
        Resource override values outside [plugin.min_*, plugin.max_*] raise.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        # cpu below min (default min is 1000m)
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([
                {"piping_id": self.pips[0].id, "cpu_limit": 500},
            ]))
        # gpu above max (default max is 0)
        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([
                {"piping_id": self.pips[0].id, "gpu_limit": 5},
            ]))

    def test_validate_nodes_info_resource_bad_format_rejected(self):
        """
        A cpu_limit value that doesn't parse as 'xm' raises.
        """
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        workflow_serializer = WorkflowSerializer()
        workflow_serializer.context['view'] = mock.Mock()
        workflow_serializer.context['view'].get_object = mock.Mock(return_value=pipeline)

        with self.assertRaises(serializers.ValidationError):
            workflow_serializer.validate_nodes_info(json.dumps([
                {"piping_id": self.pips[0].id, "cpu_limit": "abc"},
            ]))


class WorkflowSerializerHelperTests(SerializerTests):
    """
    Direct unit tests for the private helpers extracted from
    ``WorkflowSerializer.validate_nodes_info`` and ``validate_piping_params``.
    """

    def setUp(self):
        super(WorkflowSerializerHelperTests, self).setUp()
        self.serializer = WorkflowSerializer()
        # _build_canonical_node calls validate_piping_overrides, which only
        # consults piping.plugin (no view context required).

    # ---- _parse_nodes_info_json --------------------------------------------------

    def test__parse_nodes_info_json_none_returns_empty_list(self):
        self.assertEqual(WorkflowSerializer._parse_nodes_info_json(None), [])

    def test__parse_nodes_info_json_bad_json_raises(self):
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._parse_nodes_info_json("not-json")

    def test__parse_nodes_info_json_non_list_raises(self):
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._parse_nodes_info_json(json.dumps({"piping_id": 1}))

    def test__parse_nodes_info_json_missing_piping_id_raises(self):
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._parse_nodes_info_json(
                json.dumps([{"compute_resource_name": "host"}]))

    def test__parse_nodes_info_json_round_trip(self):
        payload = [{"piping_id": 1, "title": "x"}]
        self.assertEqual(WorkflowSerializer._parse_nodes_info_json(
            json.dumps(payload)), payload)

    # ---- _register_title ---------------------------------------------------------

    def test__register_title_adds_to_set(self):
        titles = set()
        WorkflowSerializer._register_title("a", titles)
        self.assertIn("a", titles)

    def test__register_title_raises_on_duplicate(self):
        titles = {"a"}
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._register_title("a", titles)

    # ---- _build_canonical_node ---------------------------------------------------

    def test__build_canonical_node_unmentioned_uses_piping_defaults(self):
        titles = set()
        node = self.serializer._build_canonical_node(
            self.pips[0], None, titles)
        self.assertEqual(node['piping_id'], self.pips[0].id)
        self.assertEqual(node['title'], self.pips[0].title)
        self.assertEqual(node['plugin_parameter_defaults'], [])
        for f in ('compute_resource_name', 'cpu_limit', 'memory_limit',
                  'number_of_workers', 'gpu_limit'):
            self.assertIsNone(node[f])
        self.assertIn(self.pips[0].title, titles)

    def test__build_canonical_node_supplied_fills_missing_keys(self):
        titles = set()
        raw = {"piping_id": self.pips[0].id, "title": "myTitle"}
        node = self.serializer._build_canonical_node(
            self.pips[0], raw, titles)
        # supplied keys preserved
        self.assertEqual(node['title'], "myTitle")
        # missing keys defaulted in place
        self.assertIsNone(node['compute_resource_name'])
        self.assertEqual(node['plugin_parameter_defaults'], [])
        for f in ('cpu_limit', 'memory_limit', 'number_of_workers', 'gpu_limit'):
            self.assertIsNone(node[f])
        # the helper mutates the input dict (legacy behavior)
        self.assertIs(node, raw)

    def test__build_canonical_node_falls_back_to_piping_title(self):
        titles = set()
        raw = {"piping_id": self.pips[0].id}
        node = self.serializer._build_canonical_node(
            self.pips[0], raw, titles)
        self.assertEqual(node['title'], self.pips[0].title)

    def test__build_canonical_node_duplicate_title_raises(self):
        titles = {self.pips[0].title}
        with self.assertRaises(serializers.ValidationError):
            self.serializer._build_canonical_node(
                self.pips[0], None, titles)

    def test__build_canonical_node_invalid_resource_override_raises(self):
        titles = set()
        raw = {"piping_id": self.pips[0].id, "cpu_limit": "abc"}
        with self.assertRaises(serializers.ValidationError):
            self.serializer._build_canonical_node(self.pips[0], raw, titles)

    # ---- _validate_compute_resource ----------------------------------------------

    def test__validate_compute_resource_none_passes(self):
        # No compute resource name supplied -> no DB hit, no raise.
        WorkflowSerializer._validate_compute_resource(self.pips[0], None)

    def test__validate_compute_resource_known_passes(self):
        WorkflowSerializer._validate_compute_resource(self.pips[0], "host")

    def test__validate_compute_resource_unknown_raises(self):
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._validate_compute_resource(
                self.pips[0], "no-such-resource")

    # ---- _validate_piping_param_defaults -----------------------------------------

    def test__validate_piping_param_defaults_passes_when_default_present(self):
        # The 'dummyInt' default piping param has value=111111 in setUp, so no
        # user-supplied default is required.
        self.serializer._validate_piping_param_defaults(self.pips[0], [])

    def test__validate_piping_param_defaults_user_supplied_passes(self):
        self.serializer._validate_piping_param_defaults(
            self.pips[0], [{"name": "dummyInt", "default": 7}])

    # ---- _validate_supplied_param_default ----------------------------------------

    def test__validate_supplied_param_default_none_raises(self):
        default_param = self.pips[0].integer_param.first()
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._validate_supplied_param_default(
                self.pips[0].id, default_param, None)

    def test__validate_supplied_param_default_wrong_type_raises(self):
        default_param = self.pips[0].integer_param.first()
        with self.assertRaises(serializers.ValidationError):
            WorkflowSerializer._validate_supplied_param_default(
                self.pips[0].id, default_param, "not-an-int")

    def test__validate_supplied_param_default_valid_passes(self):
        default_param = self.pips[0].integer_param.first()
        WorkflowSerializer._validate_supplied_param_default(
            self.pips[0].id, default_param, 42)


class WorkflowSerializerJobsCountFieldsTests(SerializerTests):
    """
    Verify the SerializerMethodField -> IntegerField swap preserves output
    semantics: annotated workflows surface the annotated counts, non-annotated
    workflows surface 0 in every count field.
    """

    def setUp(self):
        super(WorkflowSerializerJobsCountFieldsTests, self).setUp()
        self.owner = User.objects.get(username=self.username)
        pipeline = Pipeline.objects.get(name=self.pipeline_name)
        (self.workflow, _) = Workflow.objects.get_or_create(
            title='WfForCounts', pipeline=pipeline, owner=self.owner)

    def _serialize(self, workflow):
        ser = WorkflowSerializer(instance=workflow)
        # The url/pipeline/plugin_instances fields are HyperlinkedIdentityField
        # and require a request in context; we only care about the *_jobs ints.
        ser.context['request'] = mock.Mock()
        # Build the representation field-by-field, skipping URL fields, to avoid
        # needing a fully-wired request.
        from workflows.models import JOBS_STATUS_FIELDS
        return {
            field: ser.fields[field].to_representation(
                ser.fields[field].get_attribute(workflow))
            for field, _ in JOBS_STATUS_FIELDS
        }

    def test_non_annotated_workflow_serializes_zeros(self):
        from workflows.models import JOBS_STATUS_FIELDS
        out = self._serialize(self.workflow)
        for field, _ in JOBS_STATUS_FIELDS:
            self.assertEqual(out[field], 0, f"expected 0 for '{field}'")

    def test_annotated_workflow_serializes_annotated_values(self):
        from workflows.models import JOBS_STATUS_FIELDS
        annotated = Workflow.add_jobs_status_count(
            Workflow.objects.filter(pk=self.workflow.pk)).get()
        out = self._serialize(annotated)
        for field, _ in JOBS_STATUS_FIELDS:
            self.assertEqual(out[field], 0)  # no plugin instances yet
