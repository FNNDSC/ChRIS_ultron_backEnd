
import os, json, io

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.auth.models import User
from django.conf import settings

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

    def test_note_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_url)
        self.assertContains(response, "title")
        self.assertContains(response, "content")

    def test_note_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_note_detail_failure_access_denied(self):
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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_note_update_failure_access_denied(self):
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

        # create an additional feed using a "fs" plugin
        user = User.objects.get(username=self.username)
        (feed, tf) = Feed.objects.get_or_create(name="Feed3", plugin=plugin)
        feed.owner = [user]
        feed.save()

    def test_feed_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Feed2")
        self.assertEqual(response.data["owners"], [self.username])

    def test_feed_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Feed1")
        self.assertContains(response, "Feed3")

    def test_feed_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_list_from_other_users_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertNotContains(response, "Feed1")
        self.assertNotContains(response, "Feed3")


class FeedDetailViewTests(ViewTests):
    """
    Test the feed-detail view
    """

    def setUp(self):
        super(FeedDetailViewTests, self).setUp()     
        feed = Feed.objects.get(name=self.feedname)
        
        self.read_update_delete_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.put = json.dumps({
            "template": {"data": [{"name": "name", "value": "Updated"},
                                  {"name": "owners", "value": [self.other_username]}]}})
          
    def test_feed_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, self.feedname)

    def test_feed_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_detail_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Updated")
        self.assertCountEqual(response.data["owners"],
                              [self.username, self.other_username])

    def test_feed_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_update_failure_new_unregistered_owner(self):
        put = json.dumps({"template": {"data": [{"name": "owners", "value": ["foouser"]}]}})
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=put,
                                   content_type=self.content_type)
        self.assertNotIn("foouser", response.data["owners"])

    def test_feed_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Feed.objects.count(), 0)

    def test_feed_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feed_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CommentListViewTests(ViewTests):
    """
    Test the comment-list view
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

    def test_comment_create_success_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Comment1")
        self.assertTrue(response.data["feed"].endswith(self.corresponding_feed_url))

    def test_comment_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_list_success_related_feed_owner(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Comment2")
        self.assertContains(response, "Comment3")

    def test_comment_list_success_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Comment2")
        self.assertContains(response, "Comment3")

    def test_comment_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CommentDetailViewTests(ViewTests):
    """
    Test the comment-detail view
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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_update_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertContains(response, "Updated")

    def test_comment_update_failure_unauthenticated(self):
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Comment.objects.count(), 0)

    def test_comment_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TagListViewTests(ViewTests):
    """
    Test the tag-list view
    """

    def setUp(self):
        super(TagListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.create_read_url = reverse("tag-list", kwargs={"pk": feed.id})
        self.post = json.dumps(
            {"template": {"data": [{"name": "name", "value": "Tag1"},
                                   {"name": "color", "value": "Black"}]}})

        # create two tags
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag2", color="blue", owner=user)
        tag.feed = [feed]
        tag.save()
        (tag, tf) = Tag.objects.get_or_create(name="Tag3", color="red", owner=user)
        tag.feed = [feed]
        tag.save()

    def test_tag_create_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Tag1")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_tag_create_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_create_failure_unauthenticated(self):
        response = self.client.post(self.create_read_url, data=self.post,
                                    content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Tag2")
        self.assertContains(response, "Tag3")

    def test_tag_list_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
    def test_tag_list_from_other_feed_owners_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        feed = Feed.objects.get(name=self.feedname)
        owner = User.objects.get(username=self.username)
        new_owner = User.objects.get(username=self.other_username)
        # make new_owner an owner of the feed together with the feed's current owner
        feed.owner = [owner, new_owner]
        feed.save()
        response = self.client.get(self.create_read_url)
        self.assertNotContains(response, "Tag2")
        self.assertNotContains(response, "Tag3")
      

class TagDetailViewTests(ViewTests):
    """
    Test the tag-detail view
    """

    def setUp(self):
        super(TagDetailViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})

        # create a tag
        user = User.objects.get(username=self.username)
        (tag, tf) = Tag.objects.get_or_create(name="Tag1", color="blue", owner=user)
        tag.feed = [feed]
        tag.save()

        self.read_update_delete_url = reverse("tag-detail", kwargs={"pk": tag.id})       
        self.put = json.dumps({
            "template": {"data": [{"name": "name", "value": "Updated"},
                                  {"name": "color", "value": "black"}]}})
          
    def test_tag_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "Tag1")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_tag_detail_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_detail_failure_not_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        feed = Feed.objects.get(name=self.feedname)
        owner = User.objects.get(username=self.username)
        new_owner = User.objects.get(username=self.other_username)
        # make new_owner an owner of the feed together with the feed's current owner
        feed.owner = [owner, new_owner]
        feed.save()
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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_update_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.put(self.read_update_delete_url, data=self.put,
                                   content_type=self.content_type)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Tag.objects.count(), 0)

    def test_tag_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tag_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedFileListViewTests(ViewTests):
    """
    Test the feedfile-list view
    """

    def setUp(self):
        super(FeedFileListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.create_read_url = reverse("feedfile-list", kwargs={"pk": feed.id})

        # create a test file to be uploaded
        test_file_path = os.path.join(settings.MEDIA_ROOT, 'test')
        if not os.path.isdir(test_file_path):
            os.mkdir(test_file_path)
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()

        # create two files in the DB "already uploaded" to the server
        plugin = Plugin.objects.get(name="pacspull")
        file = open(self.test_file, "r")
        django_file = File(file)
        feedfile = FeedFile(plugin=plugin)
        feedfile.fname.save("file2.txt", django_file, save=True)
        feedfile.feed = [feed]
        feedfile.save()
        feedfile = FeedFile(plugin=plugin)
        feedfile.fname.save("file3.txt", django_file, save=True)
        feedfile.feed = [feed]
        feedfile.save()
        file.close()

    def tearDown(self):
        #remove files created in the filesystem after each test
        os.remove(self.test_file)
        for f in os.listdir(settings.MEDIA_ROOT):
            if f in ["file1.txt", "file2.txt", "file3.txt"]:
                file = os.path.join(settings.MEDIA_ROOT, f)
                os.remove(file) 
    
    def test_feedfile_create_success(self):
        self.client.login(username=self.username, password=self.password)
        plugin = Plugin.objects.get(name="pacspull")
        # POST request using multipart/form-data to be able to upload file         
        with open(self.test_file) as f:
            post = {"fname": f, "plugin": plugin.id}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["fname"], "./file1.txt")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_feedfile_create_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        plugin = Plugin.objects.get(name="pacspull")
        # POST request using multipart/form-data to be able to upload file         
        with open(self.test_file) as f:
            post = {"fname": f, "plugin": plugin.id}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_create_failure_unauthenticated(self):
        plugin = Plugin.objects.get(name="pacspull")
        # POST request using multipart/form-data to be able to upload file         
        with open(self.test_file) as f:
            post = {"fname": f, "plugin": plugin.id}
            response = self.client.post(self.create_read_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "file2.txt")
        self.assertContains(response, "file3.txt")

    def test_feedfile_list_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class FeedFileDetailViewTests(ViewTests):
    """
    Test the feedfile-detail view
    """

    def setUp(self):
        super(FeedFileDetailViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})

        # create a test file 
        test_file_path = os.path.join(settings.MEDIA_ROOT, 'test')
        if not os.path.isdir(test_file_path):
            os.mkdir(test_file_path)
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()

        # create a file in the DB "already uploaded" to the server
        plugin = Plugin.objects.get(name="pacspull")
        file = open(self.test_file, "r")
        django_file = File(file)
        feedfile = FeedFile(plugin=plugin)
        feedfile.fname.save("file1.txt", django_file, save=True)
        feedfile.feed = [feed]
        feedfile.save()
        file.close()

        self.read_update_delete_url = reverse("feedfile-detail", kwargs={"pk": feedfile.id})

    def tearDown(self):
        #remove files created in the filesystem after each test
        os.remove(self.test_file)
        os.remove(settings.MEDIA_ROOT + '/file1.txt')
          
    def test_feedfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_feedfile_detail_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(FeedFile.objects.count(), 0)

    def test_feedfile_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class FileResourceViewTests(ViewTests):
    """
    Test the tag-detail view
    """

    def setUp(self):
        super(FileResourceViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)

        # create a test file 
        test_file_path = os.path.join(settings.MEDIA_ROOT, 'test')
        if not os.path.isdir(test_file_path):
            os.mkdir(test_file_path)
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()
            
        # create a file in the DB "already uploaded" to the server
        plugin = Plugin.objects.get(name="pacspull")
        file = open(self.test_file, "r")
        django_file = File(file)
        feedfile = FeedFile(plugin=plugin)
        feedfile.fname.save("file1.txt", django_file, save=True)
        feedfile.feed = [feed]
        feedfile.save()
        file.close()

        self.download_url = reverse("file-resource",
                                    kwargs={"pk": feedfile.id}) + 'file1.txt'

    def tearDown(self):
        #remove files created in the filesystem after each test
        os.remove(self.test_file)
        os.remove(settings.MEDIA_ROOT + '/file1.txt')
          
    def test_fileresource_download_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.download_url)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(str(response.content,'utf-8'), "test file")

    def test_fileresource_download_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fileresource_download_failure_unauthenticated(self):
        response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
