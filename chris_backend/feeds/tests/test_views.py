
import json

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from rest_framework import status

from plugins.models import Plugin
from feeds.models import Note, Tag, Feed, Comment, FeedFile
from feeds import views


class ViewTests(TestCase):
    
    def setUp(self):     
        self.username = 'foo'
        self.password = 'bar'
        self.other_username = 'boo'
        self.other_password = 'far'
        self.feedname = "Feed1"
        self.content_type='application/vnd.collection+json'
        
        # create basic models
        
        # create two users
        User.objects.create_user(username=self.other_username, password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)
        
        # create two plugins of different types
        Plugin.objects.get_or_create(name="mri_convert", type="ds")
        (plugin, tf) = Plugin.objects.get_or_create(name="pacspull", type="fs")
        
        # create a feed using a "fs" plugin
        (feed, tf) = Feed.objects.get_or_create(name=self.feedname, plugin=plugin)
        feed.owner = [user]
        feed.save()
    

class CustomFunctionsTests(ViewTests):
    """
    Test top-level functions in the views module
    """
    def setUp(self):
       super(CustomFunctionsTests, self).setUp()

       # create two comments
       feed = Feed.objects.get(name=self.feedname)
       user = User.objects.get(username=self.username)
       Comment.objects.get_or_create(title="com1",feed=feed, owner=user)
       Comment.objects.get_or_create(title="com2",feed=feed, owner=user)

    def test_get_list_response(self):
        """
        Test whether views.get_list_response() returns a response with two comments
        """
        self.client.login(username=self.username, password=self.password)
        feed = Feed.objects.get(name=self.feedname)
        # get comment list for feed1
        response = self.client.get(reverse("comment-list", kwargs={"pk": feed.id}))
        # get the view and queryset
        view = response.renderer_context['view']
        queryset = view.get_comments_queryset()
        list_response = views.get_list_response(view, queryset)
        # set required response attributes
        list_response.accepted_renderer = response.accepted_renderer
        list_response.accepted_media_type = response.accepted_media_type
        list_response.renderer_context = response.renderer_context
        self.assertContains(list_response, "com1")
        self.assertContains(list_response, "com2")

    def test_append_plugins_link(self):
        """
        Test whether views.append_plugins_link() appends the list of plugins
        to its response argument
        """
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse("feed-list"))
        request = response.renderer_context['request']
        response = views.append_plugins_link(request, response)
        self.assertContains(response, reverse('plugin-list'))
        

class NoteDetailViewTests(ViewTests):
    """
    Test the note-detail view
    """

    def setUp(self):
        super(NoteDetailViewTests, self).setUp()     
        feed = Feed.objects.get(name=self.feedname)
        self.read_update_url = reverse("note-detail", kwargs={"pk": feed.id})
        self.put = json.dumps({"template": {"data": [{"name": "title", "value": "Note1"},
                                          {"name": "content", "value": "My first note"}]}})

    def test_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "title")
        self.assertContains(response, "content")

    def test_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Note1")
        self.assertContains(response, "My first note")

    def test_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class FeedListViewTests(ViewTests):
    """
    Test the feed-list view
    """

    def setUp(self):
        super(FeedListViewTests, self).setUp()     
        plugin = Plugin.objects.get(name="pacspull")
        
        self.create_read_url = reverse("feed-list")
        self.post = json.dumps({"template": {"data": [{"name": "name", "value": "Feed2"},
                                          {"name": "plugin", "value": plugin.id}]}})

    def test_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Feed2")

        
"""       
    def test_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "title")
        self.assertContains(response, "content")

    def test_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Note 1")
        self.assertContains(response, "My first note")

    def test_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
"""      
