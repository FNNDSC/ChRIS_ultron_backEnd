def additionalproperties_for_plugins_instances_create(result, **_kwargs):
    """
    Set ``additionalProperties: {}`` for the request body of ``plugins_instances_create``
    (``additionalProperties`` cannot be set ordinarily using drf-spectacular ``@extend_schema``).
    This is necessary because ``[POST] api/v1/plugins/N/instances/`` receives
    plugin instance parameters as arbitrary properties.

    :param result: an OpenAPI specification
    """
    result['components']['schemas']['PluginInstanceRequest']['additionalProperties'] = {}
    return result

