def nonrequired_fields(result, **_kwargs):
    """
    FileBrowserLinkFile has either linked_file or linked_folder.

    drf_spectacular lists all fields as required. This hook makes
    the two fields optional.
    """
    required: list[str] = result['components']['schemas']['FileBrowserLinkFile']['required']

    for field in ('linked_file', 'linked_folder'):
        if (i := required.index(field)) >= 0:
            del required[i]

    return result
