
import json

from django.conf.urls import url, include
from django.test.utils import override_settings
from django.test import TestCase

from collection_json import Collection
from rest_framework import status
from rest_framework.routers import DefaultRouter

from collectionjson.renderers import CollectionJsonRenderer
from .models import Moron
from . import views


@override_settings(ROOT_URLCONF='collectionjson.tests.test_parsers')
class SimplePOSTTest(TestCase):
    endpoint = ''

    def setUp(self):
        self.content_type='application/vnd.collection+json'
        self.post = json.dumps({"template": {"data": [{"name": "name", "value": "Bob"}]}})
        self.response = self.client.post(self.endpoint, data=self.post,
                                    content_type=self.content_type)


class TestCollectionJsonParser(SimplePOSTTest):
    endpoint = '/rest-api/moron/'

    def setUp(self):
        super(TestCollectionJsonParser, self).setUp()

    def test_create_success(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.response.data["name"], "Bob")


router = DefaultRouter()
router.register('moron', views.MoronModelViewSet)
urlpatterns = [
    url(r'^rest-api/', include(router.urls)),
]

