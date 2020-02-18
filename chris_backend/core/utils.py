
import os


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
