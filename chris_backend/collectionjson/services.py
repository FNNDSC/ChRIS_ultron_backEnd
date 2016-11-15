
from urllib.parse import urlparse

from django.core.urlresolvers import resolve

from rest_framework.response import Response

def get_list_response(list_view_instance, queryset):
    """
    Convenience method to get an HTTP response with a list of objects
    from a list view instance and a queryset
    """
    page = list_view_instance.paginate_queryset(queryset)
    if page is not None:
        serializer = list_view_instance.get_serializer(page, many=True)
        return list_view_instance.get_paginated_response(serializer.data)

    serializer = list_view_instance.get_serializer(queryset, many=True)
    return Response(serializer.data)


def append_collection_links(response, link_dict):
    """
    Convenience method to append document-level links to a response object.
    """
    data = response.data
    if not 'collection_links' in data:
        data['collection_links'] = {}
        
    for (link_relation_name, url) in link_dict.items():
        data['collection_links'][link_relation_name] = url
    return response


def append_collection_template(response, template_data):
    """
    Convenience method to append to a response a collection+json template.
    """
    data = []
    for (k, v) in template_data.items():
        data.append({"name": k, "value": v})
    response.data["template"] = {"data": data}
    return response


def append_collection_querylist(response, query_url_list):
    """
    Convenience method to append to a response a collection+json queries template.
    """
    queries = []
    for query_url in query_url_list:
        relative_url = urlparse(query_url).path
        match = resolve(relative_url)
        filters = match.func.view_class().filter_class.base_filters
        data = []
        for k in filters.keys():
            data.append({"name": k, "value": ""})
        queries.append({'href': query_url, 'rel': 'search', "data": data})
    response.data["queries"] = queries
    return response
