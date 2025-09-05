
import logging
import json

from django.urls import path, include
from django.test.utils import override_settings
from django.test import TestCase

from collection_json import Collection
from rest_framework import status
from rest_framework.routers import DefaultRouter

from .models import Dummy, Person, Employee, Simple
from . import views


def create_models():
    #import pdb; pdb.set_trace()
    bob = Employee.objects.create(name='Bob LawLaw')
    dummy = Dummy.objects.create(name='Yolo McSwaggerson', employee=bob)
    dummy.persons.add(Person.objects.create(name='Peter'))
    dummy.persons.add(Person.objects.create(name='Paul'))

@override_settings(ROOT_URLCONF='collectionjson.tests.test_renderers')
class SimpleGetTest(TestCase):
    endpoint = ''

    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)
        self.response = self.client.get(self.endpoint)
        content = json.loads(self.response.content.decode('utf8'))
        self.total = content['collection'].pop('total', None)  # remove the non-standard 'total' property
        self.collection = Collection.from_json(json.dumps(content))

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class TestCollectionJsonRenderer(SimpleGetTest):
    endpoint = '/rest-api/dummy/'

    def setUp(self):
        create_models()
        super(TestCollectionJsonRenderer, self).setUp()

    def test_it_has_the_right_response_code(self):
        self.assertEqual(self.response.status_code, status.HTTP_200_OK)

    def test_it_has_the_right_content_type(self):
        content_type = self.response['Content-Type']
        self.assertEqual(content_type, 'application/vnd.collection+json')

    def test_it_has_the_version_number(self):
        self.assertEqual(self.collection.version, '1.0')

    def test_it_has_an_href(self):
        href = self.collection.href
        self.assertEqual(href, 'http://testserver/rest-api/dummy/')

    def test_it_has_the_correct_total(self):
        self.assertEqual(self.total, 1)

    def get_dummy(self):
        return self.collection.items[0]

    def test_the_dummy_item_has_an_href(self):
        href = self.get_dummy().href
        self.assertTrue(href.startswith('http://testserver/rest-api/dummy/'))

    def test_the_dummy_item_contains_name(self):
        name = self.get_dummy().data.find('name')[0].value
        self.assertEqual(name, 'Yolo McSwaggerson')

    def get_dummy_link(self, rel):
        links = self.get_dummy()['links']
        return next(x for x in links if x['rel'] == rel)

    def test_the_dummy_item_links_to_child_elements(self):
        href = self.get_dummy().links.find(rel='employee')[0].href
        self.assertTrue(href.startswith('http://testserver/rest-api/employee/'))

    def test_link_fields_are_rendered_as_links(self):
        href = self.get_dummy().links.find(rel='other_stuff')[0].href
        self.assertEqual(href, 'http://other-stuff.com/')

    def test_empty_link_fields_are_not_rendered_as_links(self):
        links = self.get_dummy().links.find(rel='empty_link')
        self.assertEqual(len(links), 0)

    def test_attribute_links_are_rendered_as_links(self):
        href = self.get_dummy().links.find(rel='some_link')[0].href
        self.assertEqual(href, 'http://testserver/rest-api/employee/1/')

    def test_many_to_many_relationships_are_rendered_as_links(self):
        persons = self.get_dummy().links.find(rel='persons')
        self.assertTrue(persons[0].href.startswith('http://testserver/rest-api/person/'))
        self.assertTrue(persons[1].href.startswith('http://testserver/rest-api/person/'))


class TestNoSerializerViews(SimpleGetTest):
    endpoint = '/rest-api/no-serializer/'

    def setUp(self):
        create_models()
        super(TestNoSerializerViews, self).setUp()

    def test_views_without_a_serializer_work(self):
        value = self.collection.items[0].data.find('foo')[0].value
        self.assertEqual(value, '1')


class TestNormalModels(SimpleGetTest):
    endpoint = '/rest-api/normal-model/'

    def setUp(self):
        Simple.objects.create(name='Foobar Baz')
        super(TestNormalModels, self).setUp()

    def test_items_dont_have_a_href(self):
        href_count = len(self.collection.items[0].find(name='href'))
        self.assertEqual(href_count, 0)


class TestCollectionJsonRendererPagination(SimpleGetTest):
    endpoint = '/rest-api/paginated/'

    def test_paginated_views_display_data(self):
        foo = self.collection.items[0].find(name='foo')[0]
        self.assertEqual(foo.value, 1)

    def test_paginated_views_display_next(self):
        next_link = self.collection.links.find(rel='next')[0]
        self.assertEqual(next_link.href, 'http://test.com/colleciton/next')

    def test_paginated_views_display_previous(self):
        next_link = self.collection.links.find(rel='previous')[0]
        self.assertEqual(next_link.href, 'http://test.com/colleciton/previous')


class TestCollectionJsonRendererPaginationWithNone(SimpleGetTest):
    endpoint = '/rest-api/none-paginated/'

    def test_paginated_view_does_not_display_next(self):
        self.assertEqual(len(self.collection.links.find(rel='next')), 0)

    def test_paginated_view_does_not_display_previous(self):
        self.assertEqual(len(self.collection.links.find(rel='previous')), 0)


class TestErrorHandling(SimpleGetTest):
    endpoint = '/rest-api/parse-error/'

    def test_errors_are_reported(self):
        self.assertEqual(self.collection.error.message, 'lol nice one')


class TestUrlRewrite(SimpleGetTest):
    endpoint = '/rest-api/url-rewrite/'

    def test_the_href_url_can_be_rewritten(self):
        rewritten_url = "http://rewritten.com/rest-api/url-rewrite/"
        self.assertEqual(self.collection.href, rewritten_url)

@override_settings(ROOT_URLCONF='collectionjson.tests.test_renderers')
class TestEmpty(TestCase):

    def test_empty_content_works(self):
        response = self.client.get('/rest-api/empty/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content.decode('utf8'), '')


router = DefaultRouter()
router.register('dummy', views.DummyReadOnlyModelViewSet)
router.register('employee', views.EmployeeReadOnlyModelViewSet)
router.register('person', views.PersonReadOnlyModelViewSet)
router.register('normal-model', views.SimpleViewSet)
urlpatterns = [
    path('rest-api/', include(router.urls)),
    path('rest-api/no-serializer/', views.NoSerializerView.as_view()),
    path('rest-api/paginated/', views.PaginatedDataView.as_view()),
    path('rest-api/none-paginated/', views.NonePaginatedDataView.as_view()),
    path('rest-api/parse-error/', views.ParseErrorView.as_view()),
    path('rest-api/url-rewrite/', views.UrlRewriteView.as_view()),
    path('rest-api/empty/', views.EmptyView.as_view()),
]
