
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.exceptions import ParseError

from core.renderers import BinaryFileRenderer
from plugins.models import Plugin
from .models import Note, Tag, Feed, Comment, FeedFile
from .serializers import UserSerializer, FeedSerializer, FeedFileSerializer
from .serializers import NoteSerializer, TagSerializer, CommentSerializer
from .permissions import IsOwnerOrChris, IsOwnerOrChrisOrReadOnly
from .permissions import IsRelatedFeedOwnerOrChris 


def get_list_response(list_view_instance, queryset):
    """
    Convenience method to get an HTTP response with a list of objects
    from a list view instance and a queryset
    """
    page = list_view_instance.paginate_queryset(queryset)
    if page is not None:
        serializer = list_view_instance.get_serializer(page, many=True)
        return list_view_instance.get_paginated_response(serializer.data)

    serializer = list_view_instance.get_serializer(queryset, many=True)
    return Response(serializer.data)


def append_plugins_link(request, response):
    """
    Convenience method to append to a response object a link to the plugin list 
    """
    response.data['links'] = {'plugins': reverse('plugin-list', request=request)}
    return response


class NoteDetail(generics.RetrieveUpdateAPIView):
    """
    A note view.
    """
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)
    

class TagList(generics.ListCreateAPIView):
    """
    A view for the collection of tags.
    """
    queryset = Feed.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner and feed list with the tag
        before first saving to the DB.
        """
        serializer.save(owner=self.request.user, feed=[self.get_object()])

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the tags for the queried
        feed that are owned by the currently authenticated user.
        """
        queryset = self.get_tags_queryset(request.user)
        return get_list_response(self, queryset)

    def get_tags_queryset(self, user):
        """
        Custom method to get the actual tags' queryset for the feed and user
        """
        feed = self.get_object()
        tags = [tag for tag in feed.tags.all() if tag.owner==user]
        return self.filter_queryset(tags)
        

class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A tag view.
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)


class FeedList(generics.ListCreateAPIView):
    """
    A view for the collection of feeds.
    """
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner list and plugin with the feed
        before first saving to the DB.
        """
        # set a list of owners and creator plugin when creating a new feed
        plugin_id = serializer.context['request'].data['plugin']
        plugin = Plugin.objects.get(pk=plugin_id)
        if plugin.type == 'ds':
            detail = "Could not create feed. Plugin %s is of type 'ds'!" % plugin.name
            raise ParseError(detail=detail)
        serializer.save(owner=[self.request.user], plugin=plugin)

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feeds 
        owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the feeds in the system
        if (user.username == 'chris'):
            return Feed.objects.all()
        return Feed.objects.filter(owner=user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a link relation pointing to the list of plugins.
        """
        response = super(FeedList, self).list(request, *args, **kwargs)
        response = append_plugins_link(request, response)
        return response


class FeedDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A feed view.
    """
    queryset = Feed.objects.all()
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def perform_update(self, serializer):
        """
        Overriden to update feed's owners if requested by a PUT request.
        """
        if 'owners' in self.request.data:
            self.update_owners(serializer)          
        super(FeedDetail, self).perform_update(serializer)
        
    def update_owners(self, serializer):
        """
        Custom method to update the feed's owners. Checks whether new owners
        are system registered users
        """
        feed = self.get_object() 
        currentOwners = feed.owner.values('username')
        usernames = self.request.data.pop('owners')
        newOwners = []
        for usern in usernames:
            if {'username': usern} not in currentOwners:
                try:
                    # check if user is a system registered user
                    owner = User.objects.get(username=usern)
                except ObjectDoesNotExist:
                    pass
                else:
                    newOwners.append(owner)
        if newOwners:
            currentOwners = [owner for owner in feed.owner.all()]
            serializer.save(owner=currentOwners+newOwners)


class CommentList(generics.ListCreateAPIView):
    """
    A view for the collection of comments.
    """
    queryset = Feed.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner and feed with the comment
        before first saving to the DB.
        """
        serializer.save(owner=self.request.user, feed=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the comments for the queried feed.
        """
        queryset = self.get_comments_queryset()
        return get_list_response(self, queryset)

    def get_comments_queryset(self):
        """
        Custom method to get the actual comments' queryset
        """
        feed = self.get_object()
        return self.filter_queryset(feed.comments.all())


class CommentDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A comment view.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)


class FeedFileList(generics.ListCreateAPIView):
    """
    A view for the collection of feeds' files.
    """
    queryset = Feed.objects.all()
    serializer_class = FeedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def perform_create(self, serializer):
        # set the file's feed and creator plugin when creating a new file
        plugin_id = serializer.context['request'].data['plugin']
        serializer.save(feed=[self.get_object()], plugin=Plugin.objects.get(pk=plugin_id))

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files for the queried feed and
        append a link relation pointing to the list of plugins.
        """
        queryset = self.get_feedfiles_queryset()
        response = get_list_response(self, queryset)
        response = append_plugins_link(request, response)
        return response

    def get_feedfiles_queryset(self):
        """
        Custom method to get the actual feedfiles' queryset
        """
        feed = self.get_object()
        return self.filter_queryset(feed.files.all())


class FeedFileDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A feed's file view.
    """
    queryset = FeedFile.objects.all()
    serializer_class = FeedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)


class FileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    queryset = FeedFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        feed_file = self.get_object()
        return Response(feed_file.fname)


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

