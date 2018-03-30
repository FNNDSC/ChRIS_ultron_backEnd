"""
ChRIS store API client module.
"""

import requests
from collection_json import Collection

from django.conf import settings

class StoreClient(object):

    def __init__(self, store_url, username, password):
        self.store_url = store_url
        self.username = username
        self.password = password

    def get_plugin_representation(self, plugin_name):
        """
        Get a plugin given its ChRIS store name.
        """
        plugin = {}
        search_params = {'name': plugin_name}
        r = requests.get('http://localhost:8010/api/v1/' + 'search/',
                         params=search_params,
                         auth=(self.username, self.username),
                         timeout=30)
        collection = Collection.from_json(r.text)
        if collection.items:
            item = collection.items[0]
            for descriptor in item.data:
                plugin[descriptor.name] = descriptor.value
            params_url = [link for link in item.links if link.rel=='parameters'][0].href

            r = requests.get(params_url,
                             auth=(self.username, self.username),
                             timeout=30)
            collection = Collection.from_json(r.text)
            params = []
            for item in collection.items:
                param = {}
                for descriptor in item.data:
                    param[descriptor.name] = descriptor.value
                params.append(param)
            plugin['parameters'] = params

        for item in collection.items:
            descriptor = item.data[0].name
            value = item.data[0].value

        requests.exceptions.Timeout
        requests.exceptions.RequestException

        client = docker.from_env()
        # first try to pull the latest image
        try:
            img = client.images.pull(dock_image_name)
        except docker.errors.APIError:
            # use local image ('remove' option automatically removes container when finished)
            byte_str = client.containers.run(dock_image_name, remove=True)
        else:
            byte_str = client.containers.run(img, remove=True)
        app_repr = json.loads(byte_str.decode())
        plugin_types = [plg_type[0] for plg_type in PLUGIN_TYPE_CHOICES]
        if app_repr['type'] not in plugin_types:
            raise ValueError("A plugin's TYPE can only be any of %s. Please fix it in %s"
                             % (plugin_types, dock_image_name))
        return app_repr




