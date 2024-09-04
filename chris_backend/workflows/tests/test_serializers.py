
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
                plugin_parameter_defaults=[]
            ),
            GivenNodeInfo(
                piping_id=self.pips[1].id,
                compute_resource_name=None,
                title="pip2",
                plugin_parameter_defaults=[]
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
                plugin_parameter_defaults=[]
            ),
            GivenNodeInfo(
                piping_id=self.pips[1].id,
                compute_resource_name=None,
                title="pip2",
                plugin_parameter_defaults=[]
            )
        ]
        self.assertCountEqual(expected, actual)
