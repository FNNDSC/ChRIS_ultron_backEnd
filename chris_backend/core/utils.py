
import os
import json
import zlib, base64


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
