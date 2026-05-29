def users_get_username(result, **_kwargs):
    """
    This hook mutates the OpenAPI schema so that ``username`` is indicated as
    required and readOnly.
    """
    user = result['components']['schemas']['User']
    assert user['type'] == 'object'
    assert 'username' in user['properties']

    user['properties']['username']['readOnly'] = True
    if 'username' not in user['required']:
        user['required'].append('username')
    return result
