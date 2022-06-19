from typing import TypedDict, NewType, List, Any, Optional


PipingId = NewType('PipingId', int)
ComputeResourceName = NewType('ComputeResourceName', int)


class GivenWorkflowPluginParameterDefault(TypedDict):
    name: str
    default: Any


class GivenNodeInfo(TypedDict):
    """
    Values which client may submit when creating a workflow instance
    to customize how plugin instances are created from their respective piping.
    """
    piping_id: PipingId
    compute_resource_name: ComputeResourceName
    title: Optional[str]
    plugin_parameter_defaults: Optional[List[GivenWorkflowPluginParameterDefault]]
