from rest_framework.relations import (
    HyperlinkedRelatedField,
    HyperlinkedIdentityField,
)
from rest_framework.serializers import HyperlinkedModelSerializer
from rest_framework.renderers import JSONRenderer

from rest_framework.fields import SerializerMethodField


class LinkField(SerializerMethodField):
    def __init__(self, method_name, *args, **kwargs):
        self.method_name = method_name
        super(LinkField, self).__init__(method_name, *args, **kwargs)


class CollectionJsonRenderer(JSONRenderer):
    media_type = 'application/vnd.collection+json'
    format = 'collection+json'

    def _transform_field(self, key, value):
        return {'name': key, 'value': value}

    def _simple_transform_item(self, item):
        data = [self._transform_field(k, v) for (k, v) in item.items()]
        return {'data': data}

    def _get_id_field(self, serializer):
        if isinstance(serializer, HyperlinkedModelSerializer):
            return serializer.url_field_name
        else:
            return None

    def _get_related_fields(self, fields, id_field):
        return [k for (k, v) in fields
                if k != id_field
                and (isinstance(v, HyperlinkedRelatedField)
                or isinstance(v, HyperlinkedIdentityField)
                or isinstance(v, LinkField))]

    def _get_item_field_links(self, field_name, item):
        data = item[field_name]

        if data is None:
            return []
        elif isinstance(data, list):
            return [self._make_link(field_name, x) for x in data]
        else:
            return [self._make_link(field_name, data)]

    def _transform_item(self, serializer, item):
        fields = serializer.fields.items()
        id_field = self._get_id_field(serializer)
        related_fields = self._get_related_fields(fields, id_field)

        data = [self._transform_field(k, item[k])
                for k in item.keys()
                if k != id_field and k not in related_fields]
        result = {'data': data}

        if id_field:
            result['href'] = item[id_field]

        links = []
        for x in related_fields:
            links.extend(self._get_item_field_links(x, item))

        if links:
            result['links'] = links

        return result

    def _transform_items(self, view, data):
        if isinstance(data, dict):
            data = [data]

        if hasattr(view, 'get_serializer'):
            serializer = view.get_serializer()
            return map(lambda x: self._transform_item(serializer, x), data)
        else:
            return map(self._simple_transform_item, data)

    def _is_paginated(self, data):
        pagination_keys = ('next', 'previous', 'results')
        return all(k in data for k in pagination_keys)

    def _get_pagination_links(self, data):
        results = []
        if data.get('next', None):
            results.append(self._make_link('next', data['next']))

        if data.get('previous', None):
            results.append(self._make_link('previous', data['previous']))

        return results

    def _get_items_from_paginated_data(self, data):
        return data.get('results')

    def _make_link(self, rel, href):
        return {'rel': rel, 'href': href}

    def _get_error(self, data):
        return {
            'error': {
                'message': data['detail']
            }
        }

    def _get_items_and_links(self, view, data):
        # This lookup of the Api Root string isn't
        # the right long-term approach. Even if we
        # looked it up properly from the default
        # router, we would still need to handle
        # custom routers. Works okay for now.
        # ------------------------------------------
        if view.get_view_name() == 'Api Root':
            links = [self._make_link(key, data[key]) for key in data.keys()]
            items = []
        else:
            links = []
            if self._is_paginated(data):
                links.extend(self._get_pagination_links(data))
                data = self._get_items_from_paginated_data(data)

            items = self._transform_items(view, data)

        return {
            'items': items,
            'links': links,
        }

    def _transform_data(self, request, response, view, data):
        collection = {
            "version": "1.0",
            "href": self.get_href(request),
        }

        if response.exception:
            collection.update(self._get_error(data))
        else:
            collection.update(self._get_items_and_links(view, data))

        return {'collection': collection}

    def get_href(self, request):
        return request.build_absolute_uri()

    def render(self, data, media_type=None, renderer_context=None):
        request = renderer_context['request']
        view = renderer_context['view']
        response = renderer_context['response']

        if data:
            data = self._transform_data(request, response, view, data)

        return super(CollectionJsonRenderer, self).render(data, media_type,
                                                          renderer_context)
