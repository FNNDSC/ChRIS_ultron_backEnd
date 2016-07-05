
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


def append_collection_links(request, response, link_dict):
    """
    Convenience method to append to a response object document-level links.
    """
    data = response.data
    if not 'collection_links' in data:
        data['collection_links'] = {}
        
    for (link_relation_name, url) in link_dict.items():
        data['collection_links'][link_relation_name] = url
    return response


def append_collection_template(response, template_data):
    """
    Convenience method to append to a response a collection+json template.
    """
    data = []
    for (k, v) in template_data.items():
        data.append({"name": k, "value": v})
    response.data["template"] = {"data": data}
    return response


class NoteDetail(generics.RetrieveUpdateAPIView):
    """
    A note view.
    """
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(NoteDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"title": "", "content": ""} 
        return append_collection_template(response, template_data)
    

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
        A collection+json template is also added to the response.
        """
        queryset = self.get_tags_queryset(request.user)
        response = get_list_response(self, queryset)
        template_data = {"name": "", "color": ""} 
        return append_collection_template(response, template_data)

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

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(TagDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "color": ""}
        return append_collection_template(response, template_data)


class FeedList(generics.ListCreateAPIView):
    """
    A view for the collection of feeds.
    """
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated,)

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
        Overriden to append document-level link relations and a collection+json
        template to the response.
        """
        response = super(FeedList, self).list(request, *args, **kwargs)
        links = {'plugins': reverse('plugin-list', request=request)}    
        response = append_collection_links(request, response, links)
        template_data = {"name": "", "plugin": 0} 
        return append_collection_template(response, template_data)


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
        if 'owner' in self.request.data:
            self.update_owners(serializer)          
        super(FeedDetail, self).perform_update(serializer)
        
    def update_owners(self, serializer):
        """
        Custom method to update the feed's owners. Checks whether the new owner
        is a system-registered user.
        """
        feed = self.get_object() 
        owners = feed.owner.values('username')
        username = self.request.data.pop('owner')
        if {'username': username} not in owners:
            try:
                # check if user is a system-registered user
                owner = User.objects.get(username=username)
            except ObjectDoesNotExist:
                pass
            else:
                owners = [o for o in feed.owner.all()]
                owners.append(owner)
                serializer.save(owner=owners)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FeedDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "owner": ""} 
        return append_collection_template(response, template_data)


class CommentList(generics.ListCreateAPIView):
    """
    A view for the collection of comments.
    """
    queryset = Feed.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner and feed with the comment
        before first saving to the DB.
        """
        serializer.save(owner=self.request.user, feed=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the comments for the queried feed.
        A collection+json template is also added to the response.
        """
        queryset = self.get_comments_queryset()
        response = get_list_response(self, queryset)
        template_data = {"title": "", "content": ""} 
        return append_collection_template(response, template_data)

    def get_comments_queryset(self):
        """
        Custom method to get the actual comments' queryset.
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

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(CommentDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"title": "", "content": ""} 
        return append_collection_template(response, template_data)


class FeedFileList(generics.ListCreateAPIView):
    """
    A view for the collection of feeds' files.
    """
    queryset = Feed.objects.all()
    serializer_class = FeedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def perform_create(self, serializer):
        # set the file's feed and creator plugin when creating a new file
        plugin_id = serializer.context['request'].data['plugin']
        serializer.save(feed=[self.get_object()], plugin=Plugin.objects.get(pk=plugin_id))

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files for the queried feed and
        append document-level link relations and a collection+json
        template to the response.
        """
        queryset = self.get_feedfiles_queryset()
        response = get_list_response(self, queryset)
        links = {'plugins': reverse('plugin-list', request=request)}    
        response = append_collection_links(request, response, links)
        template_data = {"fname": "", "plugin": 0} 
        return append_collection_template(response, template_data)

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

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FeedFileDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"fname": ""}
        return append_collection_template(response, template_data)


class FileResource(generics.GenericAPIView):
    """
    A view to enable downloading of a file resource .
    """
    queryset = FeedFile.objects.all()
    renderer_classes = (BinaryFileRenderer,)
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)

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

