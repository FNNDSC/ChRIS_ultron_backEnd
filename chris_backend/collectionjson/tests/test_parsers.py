
import json

from django.conf.urls import url, include
from django.test.utils import override_settings
from django.test import TestCase

from rest_framework import status
from rest_framework.routers import DefaultRouter

from . import views


@override_settings(ROOT_URLCONF='collectionjson.tests.test_parsers')
class SimplePOSTTest(TestCase):
    endpoint = ''

    def setUp(self):
        self.content_type='application/vnd.collection+json'


class TestCollectionJsonParser(SimplePOSTTest):
    endpoint = '/rest-api/moron/'

    def setUp(self):
        super(TestCollectionJsonParser, self).setUp()

    def test_create_success(self):
        post = json.dumps({"template": {"data": [{"name": "name", "value": "Bob"}]}})
        response = self.client.post(self.endpoint, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Bob")

    def test_create_failure_invalid_template_not_dict(self):
        post = json.dumps([{"template": {"data": [{"name": "name", "value": "Bob"}]}}])
        response = self.client.post(self.endpoint, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_failure_invalid_template_missing_field(self):
        post = json.dumps({"templlte": {"data": [{"name": "name", "value": "Bob"}]}})
        response = self.client.post(self.endpoint, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


router = DefaultRouter()
router.register('moron', views.MoronModelViewSet)
urlpatterns = [
    url(r'^rest-api/', include(router.urls)),
]

