
import os, json, shutil

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core.files import File
from django.contrib.auth.models import User
from django.conf import settings

from rest_framework import status

from plugins.models import Plugin, PluginInstance
from feeds.models import Note, Tag, Feed, Comment, FeedFile
from feeds import views


class ViewTests(TestCase):
    
    def setUp(self):
        self.content_type='application/vnd.collection+json'
        
        self.chris_username = 'chris'
        self.chris_password = 'chris12'
        self.username = 'foo'
        self.password = 'bar'
        self.other_username = 'boo'
        self.other_password = 'far'
             
        self.plugin_name = "pacspull"
        self.plugin_type = "fs"
        self.plugin_parameters = {'mrn': {'type': 'string', 'optional': False},
                                  'img_type': {'type': 'string', 'optional': True}}

        self.feedname = "Feed1"
        
        # create basic models
        
        # create the chris user and two other users
        User.objects.create_user(username=self.chris_username,
                                 password=self.chris_password)
        User.objects.create_user(username=self.other_username,
                                 password=self.other_password)
        user = User.objects.create_user(username=self.username,
                                        password=self.password)
        
        # create two plugins of different types
        Plugin.objects.get_or_create(name="mri_convert", type="ds")
        (plugin, tf) = Plugin.objects.get_or_create(name="pacspull", type="fs")
        
        # create a feed by creating a "fs" plugin instance
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
        pl_inst.feed.name = self.feedname
        pl_inst.feed.save()
        

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
    Test the feed-list view
    """

    def setUp(self):
        super(FeedListViewTests, self).setUp()     
              
        self.list_url = reverse("feed-list")

        # create an additional feed using a "fs" plugin instance
        plugin = Plugin.objects.get(name="pacspull")
        user = User.objects.get(username=self.username)
        pl_inst = PluginInstance.objects.create(plugin=plugin, owner=user)
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

    def test_feed_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feed_list_from_other_users_not_listed(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "Feed1")
        self.assertNotContains(response, "Feed2")
        

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
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Feed.objects.count(), 0)

    def test_feed_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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

    def test_comment_list_success_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.create_read_url)
        self.assertContains(response, "Comment2")
        self.assertContains(response, "Comment3")

    def test_comment_list_failure_unauthenticated(self):
        response = self.client.get(self.create_read_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        

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
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(Comment.objects.count(), 0)

    def test_comment_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        

class FeedFileViewTests(ViewTests):
    """
    Generric feedfile view tests' setup and tearDown
    """

    def setUp(self):
        super(FeedFileViewTests, self).setUp()
        # create test directory where files are created
        self.test_dir = settings.MEDIA_ROOT + '/test'
        settings.MEDIA_ROOT = self.test_dir
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

    def tearDown(self):
        #remove test directory
        shutil.rmtree(self.test_dir)
        settings.MEDIA_ROOT = os.path.dirname(self.test_dir)

        
class FeedFileListViewTests(FeedFileViewTests):
    """
    Test the feedfile-list view
    """

    def setUp(self):
        super(FeedFileListViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})
        self.list_url = reverse("feedfile-list", kwargs={"pk": feed.id})

        # create a test file 
        test_file_path = self.test_dir
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file1")
        file.close()
        file = open(test_file_path + '/file2.txt', "w")
        file.write("test file2")
        file.close()

        # create two files in the DB "already uploaded" to the server)
        pl_inst = PluginInstance.objects.all()[0]
        #file = open(self.test_file, "r")
        #django_file = File(file)
        #feedfile = FeedFile(plugin_inst=pl_inst)
        #feedfile.fname.save("file2.txt", django_file, save=True)
        #feedfile.feed = [feed]
        #feedfile.save()
        #feedfile = FeedFile(plugin_inst=pl_inst)
        #feedfile.fname.save("file3.txt", django_file, save=True)
        #feedfile.feed = [feed]
        #feedfile.save()
        #file.close()
        feedfile = FeedFile(plugin_inst=pl_inst)
        feedfile.fname.name = 'file1.txt'
        feedfile.save()
        feedfile.feed = [feed]
        feedfile.save()
        feedfile = FeedFile(plugin_inst=pl_inst)
        feedfile.fname.name = 'file2.txt'
        feedfile.save()
        feedfile.feed = [feed]
        feedfile.save()

    def test_feedfile_create_failure_post_not_allowed(self):
        self.client.login(username=self.username, password=self.password)
        # try to create a new feed file with a POST request to the list
        #  POST request using multipart/form-data to be able to upload file  
        with open(self.test_file) as f:
            post = {"fname": f}
            response = self.client.post(self.list_url, data=post)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_feedfile_list_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.list_url)
        self.assertContains(response, "file1.txt")
        self.assertContains(response, "file2.txt")

    def test_feedfile_list_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_list_failure_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        

class FeedFileDetailViewTests(FeedFileViewTests):
    """
    Test the feedfile-detail view
    """

    def setUp(self):
        super(FeedFileDetailViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)
        self.corresponding_feed_url = reverse("feed-detail", kwargs={"pk": feed.id})

        # create a test file 
        test_file_path = self.test_dir
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()

        # create a file in the DB "already uploaded" to the server
        pl_inst = PluginInstance.objects.all()[0]
        feedfile = FeedFile(plugin_inst=pl_inst)
        feedfile.fname.name = 'file1.txt'
        feedfile.save()
        feedfile.feed = [feed]
        feedfile.save()

        self.read_update_delete_url = reverse("feedfile-detail", kwargs={"pk": feedfile.id})
          
    def test_feedfile_detail_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_feedfile_detail_success_user_chris(self):
        self.client.login(username=self.chris_username, password=self.chris_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertContains(response, "file1.txt")
        self.assertTrue(response.data["feed"][0].endswith(self.corresponding_feed_url))

    def test_feedfile_detail_failure_not_related_feed_owner(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedfile_detail_failure_unauthenticated(self):
        response = self.client.get(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feedfile_delete_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEquals(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEquals(FeedFile.objects.count(), 0)

    def test_feedfile_delete_failure_unauthenticated(self):
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feedfile_delete_failure_access_denied(self):
        self.client.login(username=self.other_username, password=self.other_password)
        response = self.client.delete(self.read_update_delete_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FileResourceViewTests(FeedFileViewTests):
    """
    Test the tag-detail view
    """

    def setUp(self):
        super(FileResourceViewTests, self).setUp()
        feed = Feed.objects.get(name=self.feedname)

        # create a test file 
        test_file_path = self.test_dir
        self.test_file = test_file_path + '/file1.txt'
        file = open(self.test_file, "w")
        file.write("test file")
        file.close()
            
        # create a file in the DB "already uploaded" to the server
        pl_inst = PluginInstance.objects.all()[0]
        feedfile = FeedFile(plugin_inst=pl_inst)
        feedfile.fname.name = 'file1.txt'
        feedfile.save()
        feedfile.feed = [feed]
        feedfile.save()
        self.download_url = reverse("file-resource",
                                    kwargs={"pk": feedfile.id}) + 'file1.txt'

          
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
