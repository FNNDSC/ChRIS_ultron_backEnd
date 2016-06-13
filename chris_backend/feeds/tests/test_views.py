
import json

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from plugins.models import Plugin
from feeds.models import Note, Tag, Feed, Comment, FeedFile
from feeds import views

class CustomFunctionsTests(TestCase):
    """
    Test top-level functions in the views module
    """
    def setUp(self):
        user = User.objects.create_user('foo', password='bar')
        (plugin, tf) = Plugin.objects.get_or_create(name="pacspull", type="ds")
        (feed, tf) = Feed.objects.get_or_create(name="feed1", plugin=plugin)
        feed.owner = [user]
        feed.save()
        (comment, tf) = Comment.objects.get_or_create(title="com1",feed=feed, owner=user)
        (comment, tf) = Comment.objects.get_or_create(title="com2",feed=feed, owner=user)

    def test_get_list_response(self):
        """
        Test whether views.get_list_response() returns a response with two comments
        """
        self.client.login(username='foo', password='bar')
        feed = Feed.objects.get(name="feed1")
        response = self.client.get(reverse("comment-list", kwargs={"pk": feed.id}))
        view = response.renderer_context['view']
        queryset = view.get_comments_queryset()
        content = views.get_list_response(view, queryset)
        self.assertContains(content, "com1")
        self.assertContains(content, "com2")

    def test_append_plugins_link(self):
        """
        Test whether views.append_plugins_link() appends the list of plugins
        to its response argument
        """
        self.client.login(username='foo', password='bar')
        response = self.client.get(reverse("feed-list"))
        request = response.renderer_context['request']
        response = views.append_plugins_link(request, response)
        self.assertContains(response, reverse('plugin-list'))
        
"""
class FeedListViewTests(TestCase):

    def setUp(self):
        Feed.objects.get_or_create(title="A Title", slug="a-slug")

    def test_list(self):
        url = reverse("feed-list")
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200, "incorrect response status code")
        data = json.loads(response.content)
"""
