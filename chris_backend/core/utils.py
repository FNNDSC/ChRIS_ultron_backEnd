
import os
import json
import zlib
import base64


def get_file_resource_link(file_serializer, obj):
    """
    Utility function to get the hyperlink to the actual file resource from a
    file serializer.
    """
    fields = file_serializer.fields.items()
    # get the current url
    url_field = [v for (k, v) in fields if k == 'url'][0]
    view = url_field.view_name
    request = file_serializer.context['request']
    format = file_serializer.context['format']
    url = url_field.get_url(obj, view, request, format)
    # return url = current url + file name
    return url + os.path.basename(obj.fname.name)


def json_zip2str(json_data):
    """
    Return a string of compressed JSON data, suitable for transmission
    back to a client.
    """
    return base64.b64encode(
        zlib.compress(
            json.dumps(json_data).encode('utf-8')
        )
    ).decode('ascii')


def filter_files_by_n_slashes(queryset, value):
    """
    Utility function to return the files that have the queried number of slashes in
    their fname property. If the queried number ends in 'u' or 'U' then only one
    file per each last "folder" in the path is returned (useful to efficiently get
    the list of immediate folders under the path).
    """
    value = value.lower()
    try:
        if value.endswith('u'):
            val = int(value[:-1])
        else:
            val = int(value)
    except Exception:
        return queryset
    lookup = r'^[^/]+'
    for i in range(val):
        lookup += '/[^/]+'
    lookup += '$'
    qs = queryset.filter(fname__regex=lookup)
    if value.endswith('u'):
        return unique_files_queryset_by_folder(qs)
    return qs


def unique_files_queryset_by_folder(queryset):
    """
    Utility function to return only one file per each last "folder" in the path
    (useful to efficiently get the list of immediate folders under the path).
    """
    ids = []
    hash_set = set()
    for f in queryset.all():
        path = f.fname.name
        last_slash_ix = path.rindex('/')
        path = path[:last_slash_ix]
        if path not in hash_set:
            ids.append(f.id)
            hash_set.add(path)
    return queryset.filter(pk__in=ids)
