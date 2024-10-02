def additionalproperties_for_plugins_instances_create(result, **_kwargs):
    """
    Set ``additionalProperties: {}`` for the request body of ``plugins_instances_create``
    (``additionalProperties`` cannot be set ordinarily using drf-spectacular ``@extend_schema``).
    This is necessary because ``[POST] api/v1/plugins/N/instances/`` receives
    plugin instance parameters as arbitrary properties.

    :param result: an OpenAPI specification
    """
    if 'PluginInstanceRequest' not in result['components']['schemas']:
        return result
    plugin_instance_request = result['components']['schemas']['PluginInstanceRequest']
    assert plugin_instance_request['type'] == 'object'
    plugin_instance_request['additionalProperties'] = {}
    plugin_instance_request['properties']['previous_id'] = {
        'type': 'integer',
        'minimum': 1,
        'maximum': 2147483647,
        'nullable': True
    }
    return result
