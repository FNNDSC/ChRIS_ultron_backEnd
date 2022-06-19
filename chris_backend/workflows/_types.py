from dataclasses import dataclass
from typing import TypedDict, NewType, List, Any, Optional, Sequence, Tuple, Dict, Union

from pipelines.models import PluginPiping, DefaultPipingStrParameter, DefaultPipingIntParameter, \
    DefaultPipingFloatParameter, DefaultPipingBoolParameter
from plugins.models import ComputeResource, PluginParameter

PipingId = NewType('PipingId', int)
ComputeResourceName = NewType('ComputeResourceName', str)
DefaultPipingParameter = Union[
    DefaultPipingStrParameter,
    DefaultPipingIntParameter,
    DefaultPipingFloatParameter,
    DefaultPipingBoolParameter
]


class GivenWorkflowPluginParameterDefault(TypedDict):
    name: str
    default: Any


class GivenNodeInfo(TypedDict):
    """
    Values which client may submit when creating a workflow instance
    to customize how plugin instances are created from their respective piping.
    """
    piping_id: PipingId
    compute_resource_name: Optional[ComputeResourceName]
    title: str
    plugin_parameter_defaults: List[GivenWorkflowPluginParameterDefault]


@dataclass(frozen=True)
class WorkflowPluginInstanceTemplate:
    """
    Resolved data ready to be used to create a plugin instance.
    """
    piping: PluginPiping
    compute_resource: ComputeResource
    title: str
    params: Sequence[Tuple[PluginParameter, Any]]


@dataclass(frozen=True)
class WorkflowPluginInstanceTemplateFactory:
    """
    Converter for :class:`GivenNodeInfo` to :class:`WorkflowPluginInstanceTemplate`
    """
    tree: Dict[PipingId, Dict]

    def get_piping(self, piping_id: PipingId) -> PluginPiping:
        return self.tree[piping_id]['piping']

    def get_compute_resource(self, piping: PluginPiping, name: Optional[ComputeResourceName]) -> ComputeResource:
        compute_resources = piping.plugin.compute_resources
        if name:
            compute_resources = compute_resources.filter(name=name)
        return compute_resources.first()

    def inflate(self, node_info: GivenNodeInfo) -> WorkflowPluginInstanceTemplate:
        piping = self.get_piping(node_info['piping_id'])
        return WorkflowPluginInstanceTemplate(
            piping=self.get_piping(node_info['piping_id']),
            compute_resource=self.get_compute_resource(piping, node_info['compute_resource_name']),
            title=node_info['title'],
            params=self._reconcile_params(node_info['plugin_parameter_defaults'], piping)
        )

    @classmethod
    def _reconcile_params(cls,
                          plugin_parameter_defaults: List[GivenWorkflowPluginParameterDefault],
                          piping: PluginPiping
                          ) -> Sequence[Tuple[PluginParameter, Any]]:
        piping_default_params = []
        piping_default_params.extend(list(piping.string_param.all()))
        piping_default_params.extend(list(piping.integer_param.all()))
        piping_default_params.extend(list(piping.float_param.all()))
        piping_default_params.extend(list(piping.boolean_param.all()))
        reconciled_params = (cls._reconcile_param(p, plugin_parameter_defaults) for p in piping_default_params)
        return [p for p in reconciled_params if p is not None]

    @staticmethod
    def _reconcile_param(default_param: DefaultPipingParameter,
                         plugin_parameter_defaults: List[GivenWorkflowPluginParameterDefault]
                         ) -> Optional[Tuple[PluginParameter, Any]]:
        plugin_param = default_param.plugin_param
        l = [d for d in plugin_parameter_defaults if d.get('name') == plugin_param.name]

        default_value = None
        if plugin_param.get_default() is not None:
            default_value = plugin_param.get_default().value

        if l:
            param_default = l[0]['default']
            return plugin_param, param_default
        elif default_param.value != default_value:
            # if default piping parameter value is different from the plugin's
            # provided default (if any) then also create a new plg inst parameter
            return default_param.plugin_param, default_param.value
        return None
