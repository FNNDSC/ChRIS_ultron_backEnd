from typing import Any

def postprocess_remove_collectionjson(result, **_kwargs):
    """
    Delete all `vnd.collection+json` content types from the given `result`.

    :param result: an OpenAPI specification
    """
    for path in result['paths'].values():
        for operation in path.values():
            if 'parameters' in operation:
                operation['parameters'] = [p for p in operation['parameters'] if not _is_format_qs(p)]
            _del_collectionjson_content(operation.get('requestBody', {}))
            for response in operation.get('responses', {}).values():
                _del_collectionjson_content(response)
    return result


def _is_format_qs(parameter: dict[str, Any]):
    return (
        parameter.get('in', None) == 'query'
        and parameter.get('name', None) == 'format'
        and parameter.get('schema', {}).get('type', None) == 'string'
        and set(parameter.get('schema', {}).get('enum', [])) == {'collection+json', 'json'}
    )


def _del_collectionjson_content(x):
    if 'content' not in x:
        return
    if 'application/vnd.collection+json' in x['content']:
        del x['content']['application/vnd.collection+json']
