
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.reverse import reverse

from collectionjson import services
from core.renderers import BinaryFileRenderer

from .models import Note, Tag, Tagging, Feed, FeedFilter, Comment, FeedFile
from .serializers import FeedSerializer, FeedFileSerializer, NoteSerializer
from .serializers import TagSerializer, TaggingSerializer, CommentSerializer
from .permissions import IsOwnerOrChris, IsOwnerOrChrisOrReadOnly
from .permissions import IsRelatedFeedOwnerOrChris, IsRelatedTagOwnerOrChris


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
        return services.append_collection_template(response, template_data)


class TagList(generics.ListCreateAPIView):
    """
    A view for the collection of user-specific tags.
    """
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, )

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the tags 
        owned by the currently authenticated user.
        """
        user = self.request.user
        # if the user is chris then return all the tags in the system
        if (user.username == 'chris'):
            return Tag.objects.all()
        return Tag.objects.filter(owner=user)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner with the tag before first saving to the DB.
        """
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a collection+json template.
        """
        response = super(TagList, self).list(request, *args, **kwargs)
        links = {'feeds': reverse('feed-list', request=request)}
        response = services.append_collection_links(response, links)
        template_data = {"name": "", "color": ""}
        return services.append_collection_template(response, template_data)


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
        return services.append_collection_template(response, template_data)


class FeedTagList(generics.ListAPIView):
    """
    A view for a feed-specific collection of user-specific tags.
    """
    queryset = Feed.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the tags for the queried feed that are
        owned by the currently authenticated user. Document-level link relations are
        also added to the response.
        """
        queryset = self.get_tags_queryset(request.user)
        response = services.get_list_response(self, queryset)
        feed = self.get_object()
        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        return services.append_collection_links(response, links)

    def get_tags_queryset(self, user):
        """
        Custom method to get the actual tags queryset for the feed and user.
        """
        feed = self.get_object()
        return feed.tags.filter(owner=user)


class TagFeedList(generics.ListAPIView):
    """
    A view for a tag-specific collection of feeds.
    """
    queryset = Tag.objects.all()
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the feeds for the queried tag.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_feeds_queryset()
        response = services.get_list_response(self, queryset)
        tag = self.get_object()
        links = {'tag': reverse('tag-detail', request=request,
                                   kwargs={"pk": tag.id})}
        return services.append_collection_links(response, links)

    def get_feeds_queryset(self):
        """
        Custom method to get the actual feeds queryset for the tag.
        """
        tag = self.get_object()
        return tag.feeds.all()


class FeedTaggingList(generics.ListCreateAPIView):
    """
    A view for the collection of feed-specific taggings.
    """
    queryset = Feed.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def perform_create(self, serializer):
        """
        Overriden to associate a tag and feed with the tagging before first
        saving to the DB.
        """
        request_data = serializer.context['request'].data
        tag_id = ""
        if 'tag_id' in request_data:
            tag_id = request_data['tag_id']
        tag = serializer.validate_tag(tag_id)
        serializer.save(tag=tag, feed=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the taggings for the queried feed.
        Document-level link relations and a collection+json template are also
        added to the response.
        """
        queryset = self.get_taggings_queryset(request.user)
        response = services.get_list_response(self, queryset)
        feed = self.get_object()
        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        response = services.append_collection_links(response, links)
        template_data = {"tag_id": ""}
        return services.append_collection_template(response, template_data)

    def get_taggings_queryset(self, user):
        """
        Custom method to get the actual taggings queryset for the feed.
        """
        feed = self.get_object()
        return Tagging.objects.filter(feed=feed, tag__owner=user)


class TagTaggingList(generics.ListCreateAPIView):
    """
    A view for the collection of tag-specific taggings.
    """
    queryset = Tag.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def perform_create(self, serializer):
        """
        Overriden to associate a tag and feed with the tagging before first
        saving to the DB.
        """
        request_data = serializer.context['request'].data
        feed_id = ""
        if 'feed_id' in request_data:
            feed_id = request_data['feed_id']
        feed = serializer.validate_feed(feed_id)
        serializer.save(tag=self.get_object(), feed=feed)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the taggings for the queried tag.
        Document-level link relations and a collection+json template are also
        added to the response.
        """
        queryset = self.get_taggings_queryset()
        response = services.get_list_response(self, queryset)
        tag = self.get_object()
        links = {'tag': reverse('tag-detail', request=request,
                                   kwargs={"pk": tag.id})}
        response = services.append_collection_links(response, links)
        template_data = {"feed_id": ""}
        return services.append_collection_template(response, template_data)

    def get_taggings_queryset(self,):
        """
        Custom method to get the actual taggings queryset for the tag.
        """
        tag = self.get_object()
        return Tagging.objects.filter(tag=tag)


class TaggingDetail(generics.RetrieveDestroyAPIView):
    """
    A tagging view.
    """
    queryset = Tagging.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedTagOwnerOrChris)


class FeedList(generics.ListAPIView):
    """
    A view for the collection of feeds.
    """
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated,)

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
        Overriden to append document-level link relations.
        """
        response = super(FeedList, self).list(request, *args, **kwargs)
        # append query list
        query_list = [reverse('feed-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        user = self.request.user
        links = {'plugins': reverse('plugin-list', request=request),
                 'tags': reverse('tag-list', request=request),
                 'uploadedfiles': reverse('uploadedfile-list', request=request),
                 'user': reverse('user-detail', request=request, kwargs={"pk": user.id})}
        return services.append_collection_links(response, links)


class FeedListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of feeds resulting from a query search.
    """
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated,)
    filterset_class = FeedFilter

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
        Custom method to update the feed's owners.
        """
        feed = self.get_object()
        owners = feed.owner.values('username')
        username = self.request.data.pop('owner')
        if {'username': username} not in owners:
            new_owner = serializer.validate_new_owner(username)
            owners = [o for o in feed.owner.all()]
            owners.append(new_owner)
            serializer.save(owner=owners)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FeedDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "owner": ""}
        return services.append_collection_template(response, template_data)


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
        response = services.get_list_response(self, queryset)
        feed = self.get_object()
        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        response = services.append_collection_links(response, links)
        template_data = {"title": "", "content": ""}
        return services.append_collection_template(response, template_data)

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
        return services.append_collection_template(response, template_data)


class FeedFileList(generics.ListAPIView):
    """
    A view for the collection of a feed's files.
    """
    queryset = Feed.objects.all()
    serializer_class = FeedFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the files for the queried feed and
        append document-level link relations.
        """
        queryset = self.get_feedfiles_queryset()
        response = services.get_list_response(self, queryset)
        feed = self.get_object()
        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        return services.append_collection_links(response, links)

    def get_feedfiles_queryset(self):
        """
        Custom method to get the actual feedfiles' queryset
        """
        feed = self.get_object()
        return self.filter_queryset(feed.files.all())


class FeedFileDetail(generics.RetrieveAPIView):
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
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)

    def get(self, request, *args, **kwargs):
        """
        Overriden to be able to make a GET request to an actual file resource.
        """
        feed_file = self.get_object()
        return Response(feed_file.fname)