
import logging
import time

from django.conf import settings

from requests import get, post, exceptions


logger = logging.getLogger(__name__)


class PfdcmClient(object):
    """
    A pfcdm API client.
    """

    def __init__(self):
        self._pfdcm_address = settings.PFDCM_ADDRESS.rstrip('/')
        self.content_type = 'application/json'

        # urls of the high level API resources
        self.pacs_list_url = self._pfdcm_address + '/api/v1/PACSservice/list/'
        self.pacs_query_url = self._pfdcm_address + '/api/v1/PACS/sync/pypx/'
        self.pacs_retrieve_url = self._pfdcm_address + '/api/v1/PACS/thread/pypx/'

    def get_pacs_list(self, timeout=30):
        """
        Get a list of PACS names.
        """
        headers = {'Content-Type': self.content_type, 'Accept': self.content_type}

        for i in range(5):
            try:
                resp = get(self.pacs_list_url, timeout=timeout, headers=headers)
            except (exceptions.Timeout, exceptions.RequestException) as e:
                logger.error(f'Error while retrieving data from pfdcm url '
                             f'-->{self.pacs_list_url}<--, detail: {str(e)}')
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                return resp.json()

    def query(self, pacs_name, query, timeout=30):
        """
        Send a PACS query dictionary to pfdcm.
        """
        headers = {'Content-Type': self.content_type, 'Accept': self.content_type}
        data = {
            'PACSservice' : {'value': pacs_name},
            'listenerService' : {'value': 'default'},
            'PACSdirective' : query
        }
        for i in range(5):
            try:
                resp = post(self.pacs_query_url, json=data, timeout=timeout,
                            headers=headers)
            except (exceptions.Timeout, exceptions.RequestException) as e:
                logger.error(f'Error while querying pfdcm url '
                             f'-->{self.pacs_query_url}<--, detail: {str(e)}')
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                result = resp.json()
                if result.get('status'):
                    pypx = result.get('pypx')
                    if pypx and 'data' in pypx:
                        return pypx['data']
                return []

    def retrieve(self, pacs_name, query, timeout=30):
        """
        Send a PACS query dictionary to pfdcm to initiate a PACS retrieve.
        """
        headers = {'Content-Type': self.content_type, 'Accept': self.content_type}
        data = {
            'PACSservice' : {'value': pacs_name},
            'listenerService' : {'value': 'default'},
            'PACSdirective' : query,
            'withFeedBack': True,
            'then': 'retrieve'
        }
        for i in range(5):
            try:
                resp = post(self.pacs_retrieve_url, json=data, timeout=timeout,
                            headers=headers)
            except (exceptions.Timeout, exceptions.RequestException) as e:
                logger.error(f'Error while querying pfdcm url '
                             f'-->{self.pacs_retrieve_url}<--, detail: {str(e)}')
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                return resp.json()
