
import logging

from django.conf.urls import url, include
from django.test.utils import override_settings
from django.test import TestCase

from rest_framework.routers import DefaultRouter

from collectionjson import services

from .models import Moron
from . import views


@override_settings(ROOT_URLCONF='collectionjson.tests.test_parsers')

class SimpleGetTest(TestCase):
    endpoint = ''

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.CRITICAL)
        self.response = self.client.get(self.endpoint)

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class FunctionTests(SimpleGetTest):
    """
    Test top-level functions in the services module
    """

    endpoint = '/rest-api/moron/'
    
    def setUp(self):

       # create two objects
       Moron.objects.get_or_create(name='bob')
       Moron.objects.get_or_create(name='paul')

       super(FunctionTests, self).setUp()

    def test_get_list_response(self):
        """
        Test whether services.get_list_response() returns a response with two objects
        """
        # get response
        response = self.response
        # get the view and queryset
        view = response.renderer_context['view']
        queryset = view.get_queryset()
        list_response = services.get_list_response(view, queryset)
        # set required response attributes
        list_response.accepted_renderer = response.accepted_renderer
        list_response.accepted_media_type = response.accepted_media_type
        list_response.renderer_context = response.renderer_context
        self.assertContains(list_response, "bob")
        self.assertContains(list_response, "paul")

    def test_append_collection_links(self):
        """
        Test whether services.append_collection_links() appends collection links 
        to its response argument
        """
        response = self.response
        links = {"morons": self.endpoint}
        response = services.append_collection_links(response, links)
        self.assertEqual(response.data['collection_links'],
                         {'morons': self.endpoint})

    def test_append_collection_template(self):
        """
        Test whether services.append_collection_template() appends a collection+json 
        template to its response argument
        """
        response = self.response
        template_data = {"name": ""} 
        response = services.append_collection_template(response, template_data)
        self.assertEqual(response.data['template'],
                         {'data': [{'name': 'name', 'value': ''}]})

    def test_append_collection_querylist(self):
        """
        Test whether services.append_collection_querylist() appends a collection+json
        queries template list to it response argument
        """
        response = self.response
        query_urls = [self.endpoint]
        response = services.append_collection_querylist(response, query_urls)
        self.assertEqual(response.data['queries'],
                         [{'href': query_urls[0], 'rel': 'search',
                           "data": [{"name": "name", "value": ""}]}])


router = DefaultRouter()
router.register('moron', views.MoronModelViewSet)
urlpatterns = [
    url(r'^rest-api/', include(router.urls)),
]

