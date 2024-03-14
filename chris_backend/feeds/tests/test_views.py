
import logging
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import status

from plugins.models import PluginMeta, Plugin, ComputeResource
from plugininstances.models import PluginInstance
from feeds.models import Note, Tag, Tagging, Feed, Comment


COMPUTE_RESOURCE_URL = settings.COMPUTE_RESOURCE_URL


class ViewTests(TestCase):
    
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        # create superuser chris (owner of root folders)
        self.chris_username = 'chris'
        self.chris_password = 'chris1234'
        User.objects.create_user(username=self.chris_username, password=self.chris_password)

        self.content_type='application/vnd.collection+json'

        self.username = 'foo'
        self.password = 'bar'
        self.other_username = 'boo'
        self.other_password = 'far'
             
        self.plugin_name = "pacspull"
        self.plugin_type = "fs"
        self.plugin_parameters = {'mrn': {'type': 'string', 'optional': False},
                                  'img_type': {'type': 'string', 'optional': True}}
        self.feedname = "Feed1"

        (self.compute_resource, tf) = ComputeResource.objects.get_or_create(
            name="host", compute_url=COMPUTE_RESOURCE_URL)

        # create basic models
        
        # create users
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)
        
        # create two plugins of different types

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='mri_convert', type='ds')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()

        (pl_meta, tf) = PluginMeta.objects.get_or_create(name='pacspull', type='fs')
        (plugin, tf) = Plugin.objects.get_or_create(meta=pl_meta, version='0.1')
        plugin.compute_resources.set([self.compute_resource])
        plugin.save()
        
        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user, title='test',
            compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = self.feedname
        pl_inst.feed.save()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)
        

class NoteDetailViewTests(ViewTests):
    """
    Test the note-detail view.
    """

    def setUp(self):
        super(NoteDetailViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.read_update_url = reverse("note-detail", kwargs={"pk": feed.id})
        self.put = json.dumps({"template": {"data": [{"name": "title", "value": "Note1"},
                                          {"name": "content", "value": "My first note"}]}})

    def test_note_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "title")
        self.assertContains(response, "content")

    def test_note_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "title")
        self.assertContains(response, "content")

    def test_note_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_note_detail_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_note_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Note1")
        self.assertContains(response, "My first note")

    def test_note_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_note_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class FeedListViewTests(ViewTests):
    """
    Test the feed-list view.
    """

    def setUp(self):
        super(FeedListViewTests, self).setUp()     
              
        self.list_url = reverse("feed-list")

        # create an additional feed using a "fs" plugin instance
        plugin = Plugin.objects.get(meta__name="pacspull")
        user = User.objects.get(username=self.username)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = "Feed2"
        pl_inst.feed.save()
    
    def test_feed_create_failure_post_not_allowed(self):
        self.client.login(username=self.username, password=self.password)
        # try to create a new feed with a POST request to the list of feeds
        post = json.dumps({"template": {"data": [{"name": "name", "value": "Feed2"}]}})
        response = self.client.post(self.list_url, data=post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_feed_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Feed1")
        self.assertContains(response, "Feed2")

    def test_feed_list_success_chris_user_lists_all_users_feeds(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Feed1")
        self.assertContains(response, "Feed2")

    def test_feed_list_success_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "Feed1")
        self.assertNotContains(response, "Feed2")

    def test_feed_list_from_other_users_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "Feed1")
        self.assertNotContains(response, "Feed2")


class FeedListQuerySearchViewTests(ViewTests):
    """
    Test the feed-list-query-search view.
    """

    def setUp(self):
        super(FeedListQuerySearchViewTests, self).setUp()     
              
        self.list_url = reverse("feed-list-query-search") + '?name=' + self.feedname

        # create an additional feed using a "fs" plugin instance
        plugin = Plugin.objects.get(meta__name="pacspull")
        user = User.objects.get(username=self.username)
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = "Feed2"
        pl_inst.feed.save()

    def test_feed_list_query_search_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.feedname)
        self.assertNotContains(response, "Feed2")

    def test_feed_list_query_search_success_chris_user_lists_all_matching_feeds(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.feedname)

    def test_feed_list_query_search_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_list_query_search_from_other_users_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "Feed2")
        

class FeedDetailViewTests(ViewTests):
    """
    Test the feed-detail view.
    """

    def setUp(self):
        super(FeedDetailViewTests, self).setUp()     
        feed = Feed.objects.get(name=self.feedname)
        
        self.read_update_delete_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "name", "value": "Updated"},
                                  {"name": "owner", "value": self.other_username}]}})
          
    def test_feed_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, self.feedname)

    def test_feed_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_detail_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Updated")
        new_owner = User.objects.get(username=self.other_username)
        feed = Feed.objects.get(name="Updated")
        self.assertIn(new_owner, feed.owner.all())

    def test_feed_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_update_failure_new_unregistered_owner(self):
        put = json.dumps({"template": {"data": [{"name": "owner", "value": "foouser"}]}})
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        feed = Feed.objects.get(name=self.feedname)
        self.assertFalse(len(feed.owner.all()) > 1)

    def test_feed_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Feed.objects.count(), 0)

    def test_feed_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CommentListViewTests(ViewTests):
    """
    Test the comment-list view.
    """

    def setUp(self):
        super(CommentListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.create_read_url = reverse("comment-list", kwargs={"pk": feed.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "title", "value": "Comment1"}]}})

        # create two comments
        user = User.objects.get(username=self.username)
        Comment.objects.get_or_create(title="Comment2",feed=feed, owner=user)
        Comment.objects.get_or_create(title="Comment3",feed=feed, owner=user)

    def test_comment_create_success_related_feed_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Comment1")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    def test_comment_create_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_list_success_related_feed_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Comment2")
        self.assertContains(response, "Comment3")

    def test_comment_list_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        

class CommentDetailViewTests(ViewTests):
    """
    Test the comment-detail view.
    """

    def setUp(self):
        super(CommentDetailViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})

        # create a comment
        user = User.objects.get(username=self.username)
        (comment, tf) = Comment.objects.get_or_create(title="Comment1",
                                                      feed=feed, owner=user)

        self.read_update_delete_url = reverse("comment-detail", kwargs={"pk": comment.id})       
        self.put = json.dumps({
            "template": {"data": [{"name": "title", "value": "Updated"}]}})
          
    def test_comment_detail_success_related_feed_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "Comment1")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    def test_comment_detail_success_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "Comment1")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    def test_comment_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Updated")

    def test_comment_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_comment_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class TagListViewTests(ViewTests):
    """
    Test the tag-list view.
    """

    def setUp(self):
        super(TagListViewTests, self).setUp()
        self.create_read_url = reverse("tag-list")
        self.post = json.dumps(
            {"template": {"data": [{"name": "name", "value": "Tag1"},
                                   {"name": "color", "value": "Black"}]}})

        # create two tags
        user = User.objects.get(username=self.username)
        Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)
        Tag.objects.get_or_create(name="Tag3", color="red", owner=user)
        
    def test_tag_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Tag1")

    def test_tag_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Tag2")
        self.assertContains(response, "Tag3")

    def test_tag_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_tag_list_for_other_users_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertNotContains(response, "Tag2")
        self.assertNotContains(response, "Tag3")


class TagDetailViewTests(ViewTests):
    """
    Test the tag-detail view.
    """

    def setUp(self):
        super(TagDetailViewTests, self).setUp()

        # create a tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag1", color="blue", owner=user)

        self.read_update_delete_url = reverse("tag-detail", kwargs={"pk": tag.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "name", "value": "Updated"},
                                  {"name": "color", "value": "black"}]}})

    def test_tag_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "Tag1")

    def test_tag_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_detail_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Updated")

    def test_tag_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Tag.objects.count(), 0)

    def test_tag_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedTagListViewTests(ViewTests):
    """
    Test the feed-tag-list view.
    """

    def setUp(self):
        super(FeedTagListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.list_url = reverse("feed-tag-list", kwargs={"pk": feed.id})

        # create Tag2 tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)

        # tag self.feedname with Tag2
        Tagging.objects.get_or_create(tag=tag, feed=feed)

        # create a new feed by creating a "fs" plugin instance

        plugin = Plugin.objects.get(meta__name="pacspull")
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = "new"
        pl_inst.feed.save()

        # create Tag3 tag
        (tag, tf) = Tag.objects.get_or_create(name="Tag3", color="red", owner=user)

        # tag the new feed with Tag3
        feed = Feed.objects.get(name="new")
        Tagging.objects.get_or_create(tag=tag, feed=feed)

    def test_feed_tag_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Tag2")
        self.assertNotContains(response, "Tag3") # tag list is feed-specific

    def test_feed_tag_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_tag_list_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_feed_tag_list_from_other_feed_owners_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        feed = Feed.objects.get(name=self.feedname)
        owner = User.objects.get(username=self.username)
        new_owner = User.objects.get(username=self.other_username)
        # make new_owner an owner of the feed together with the feed's current owner
        feed.owner.set([owner, new_owner])
        feed.save()
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "Tag2") # a feed owner can not see another feed owner's tags


class TagFeedListViewTests(ViewTests):
    """
    Test the tag-feed-list view.
    """

    def setUp(self):
        super(TagFeedListViewTests, self).setUp()

        # create Tag2 tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)

        self.list_url = reverse("tag-feed-list", kwargs={"pk": tag.id})

        # tag self.feedname with Tag2
        feed = Feed.objects.get(name=self.feedname)
        Tagging.objects.get_or_create(tag=tag, feed=feed)

        # create a new feed by creating a "fs" plugin instance
        plugin = Plugin.objects.get(meta__name="pacspull")
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = "new"
        pl_inst.feed.save()

        # create Tag3 tag
        (tag, tf) = Tag.objects.get_or_create(name="Tag3", color="red", owner=user)

        # tag the new feed with Tag3
        feed = Feed.objects.get(name="new")
        Tagging.objects.get_or_create(tag=tag, feed=feed)

    def test_tag_feed_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, self.feedname)
        self.assertNotContains(response, "new")  # feed list is tag-specific

    def test_tag_feed_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_feed_list_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedTaggingListViewTests(ViewTests):
    """
    Test the feed-tagging-list view.
    """

    def setUp(self):
        super(FeedTaggingListViewTests, self).setUp()

        feed = Feed.objects.get(name=self.feedname)
        self.create_read_url = reverse("feed-tagging-list", kwargs={"pk": feed.id})

        # create Tag1 tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag1", color="green", owner=user)

        self.post = json.dumps(
            {"template": {"data": [{"name": "tag_id", "value": tag.id}]}})

        # create Tag2 tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)

        # tag self.feedname with Tag2
        Tagging.objects.get_or_create(tag=tag, feed=feed)

    def test_feed_tagging_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tag = Tag.objects.get(name="Tag1")
        self.assertEqual(response.data["tag_id"], tag.id)
        feed = Feed.objects.get(name=self.feedname)
        self.assertEqual(response.data["feed_id"], feed.id)

    def test_feed_tagging_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_tagging_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        tag = Tag.objects.get(name="Tag2")
        self.assertContains(response, tag.id)

    def test_feed_tagging_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_tagging_list_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_tagging_list_from_other_feed_owners_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        feed = Feed.objects.get(name=self.feedname)
        owner = User.objects.get(username=self.username)
        new_owner = User.objects.get(username=self.other_username)
        # make new_owner an owner of the feed together with the feed's current owner
        feed.owner.set([owner, new_owner])
        feed.save()
        response = self.client.get(self.create_read_url)
        tag = Tag.objects.get(name="Tag2")
        self.assertNotContains(response, tag.id) # a feed owner can not see another feed owner's taggings


class TagTaggingListViewTests(ViewTests):
    """
    Test the tag-tagging-list view.
    """

    def setUp(self):
        super(TagTaggingListViewTests, self).setUp()

        feed = Feed.objects.get(name=self.feedname)

        # create Tag2 tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)

        self.create_read_url = reverse("tag-tagging-list", kwargs={"pk": tag.id})

        self.post = json.dumps(
            {"template": {"data": [{"name": "feed_id", "value": feed.id}]}})

        # create a new feed by creating a "fs" plugin instance
        plugin = Plugin.objects.get(meta__name="pacspull")
        pl_inst = PluginInstance.objects.create(
            plugin=plugin, owner=user, compute_resource=plugin.compute_resources.all()[0])
        pl_inst.feed.name = "new"
        pl_inst.feed.save()

        # tag new feed with Tag2
        feed = Feed.objects.get(name="new")
        Tagging.objects.get_or_create(tag=tag, feed=feed)

        # create Tag3 tag
        (tag, tf) = Tag.objects.get_or_create(name="Tag3", color="red", owner=user)

        # tag self.feedname with Tag3
        Tagging.objects.get_or_create(tag=tag, feed=feed)

    def test_tag_tagging_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tag = Tag.objects.get(name="Tag2")
        self.assertEqual(response.data["tag_id"], tag.id)
        feed = Feed.objects.get(name=self.feedname)
        self.assertEqual(response.data["feed_id"], feed.id)

    def test_tag_tagging_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_tagging_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        feed = Feed.objects.get(name="new")
        self.assertContains(response, feed.id)
        feed = Feed.objects.get(name=self.feedname)
        self.assertNotContains(response, feed.id)

    def test_tag_tagging_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_tagging_list_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TaggingDetailViewTests(ViewTests):
    """
    Test the tagging-detail view.
    """

    def setUp(self):
        super(TaggingDetailViewTests, self).setUp()

        # create a tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag1", color="blue", owner=user)

        # tag self.feedname with Tag1
        feed = Feed.objects.get(name=self.feedname)
        (tagging, tf) = Tagging.objects.get_or_create(tag=tag, feed=feed)

        self.read_delete_url = reverse("tagging-detail", kwargs={"pk": tagging.id})

    def test_tagging_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_delete_url)
        tag = Tag.objects.get(name="Tag1")
        self.assertEqual(response.data["tag_id"], tag.id)
        feed = Feed.objects.get(name=self.feedname)
        self.assertContains(response, feed.id)

    def test_tagging_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tagging_detail_failure_not_related_tag_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tagging_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Tagging.objects.count(), 0)

    def test_tagging_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tagging_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedPluginInstanceListViewTests(ViewTests):
    """
    Test the feed-plugininstance-list view.
    """

    def setUp(self):
        super(FeedPluginInstanceListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.list_url = reverse("feed-plugininstance-list", kwargs={"pk": feed.id})

        # create two files in the DB "already uploaded" to the server from two different
        # plugin instances that write to the same feed
        plg_inst = PluginInstance.objects.get(title='test')

        # create a second 'ds' plugin instance in the same feed tree
        user = User.objects.get(username=self.username)
        plugin = Plugin.objects.get(meta__name="mri_convert")
        PluginInstance.objects.get_or_create(
            plugin=plugin, owner=user, previous_id=plg_inst.id, title='test1',
            compute_resource=plugin.compute_resources.all()[0])

    def test_feed_plugin_instance_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        # it shows all the plugin instances associated to the feed
        self.assertContains(response, "test")
        self.assertContains(response, "test1")

    def test_feed_plugin_instance_list_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_plugin_instance_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
