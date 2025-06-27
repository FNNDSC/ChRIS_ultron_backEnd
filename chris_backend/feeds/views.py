
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.reverse import reverse
from drf_spectacular.utils import extend_schema, extend_schema_view

from collectionjson import services
from plugininstances.serializers import PluginInstanceSerializer

from .models import (Feed, FeedFilter, FeedGroupPermission, FeedGroupPermissionFilter,
                     FeedUserPermission, FeedUserPermissionFilter, Tag, TagFilter,
                     Comment, CommentFilter, Note, Tagging)
from .serializers import (FeedSerializer, FeedGroupPermissionSerializer,
                          FeedUserPermissionSerializer, NoteSerializer,
                          TagSerializer, TaggingSerializer, CommentSerializer)
from .permissions import (
    IsChrisOrFeedOwnerOrHasFeedPermissionOrPublicFeedReadOnly, IsOwnerOrChrisOrReadOnly,
    IsOwnerOrChrisOrHasPermissionOrPublicReadOnly, IsOwnerOrChrisOrHasPermissionReadOnly,
    IsChrisOrFeedOwnerOrHasFeedPermissionReadOnly,
    IsOwnerOrChrisOrFeedOwnerOrHasFeedPermissionReadOnlyOrPublicFeedReadOnly)


class NoteDetail(generics.RetrieveUpdateAPIView):
    """
    A note view.
    """
    http_method_names = ['get', 'put']
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsChrisOrFeedOwnerOrHasFeedPermissionOrPublicFeedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(NoteDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"title": "", "content": ""}
        return services.append_collection_template(response, template_data)


@extend_schema_view(
    get=extend_schema(operation_id="tags_list")
)
class TagList(generics.ListCreateAPIView):
    """
    A view for the collection of tags.
    """
    http_method_names = ['get', 'post']
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, )

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
        # append query list
        query_list = [reverse('tag-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)
        # append document-level link relations
        links = {'feeds': reverse('feed-list', request=request)}
        response = services.append_collection_links(response, links)
        # append write template
        template_data = {"name": "", "color": ""}
        return services.append_collection_template(response, template_data)


class TagListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of tags resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    filterset_class = TagFilter


class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A tag view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsOwnerOrChrisOrReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(TagDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "color": ""}
        return services.append_collection_template(response, template_data)


@extend_schema_view(
    get=extend_schema(operation_id="feed_tags_list")
)
class FeedTagList(generics.ListAPIView):
    """
    A view for a feed-specific collection of user-specific tags.
    """
    http_method_names = ['get']
    queryset = Feed.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly)

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
        return feed.tags.all()


class TagFeedList(generics.ListAPIView):
    """
    A view for the tag-specific collection of feeds.
    """
    http_method_names = ['get']
    queryset = Tag.objects.all()
    serializer_class = FeedSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the feeds for the queried tag.
        Document-level link relations are also added to the response.
        """
        queryset = self.get_feeds_queryset(request.user)
        response = services.get_list_response(self, queryset)
        tag = self.get_object()
        links = {'tag': reverse('tag-detail', request=request,
                                   kwargs={"pk": tag.id})}
        return services.append_collection_links(response, links)

    def get_feeds_queryset(self, user):
        """
        Custom method to get the actual feeds queryset for the tag and user.
        """
        tag = self.get_object()

        if not user.is_authenticated:
            return Feed.add_jobs_status_count(tag.feeds.filter(public=True))

        lookup = Q(owner=user) | Q(public=True) | Q(shared_users=user) | Q(
            shared_groups__in=user.groups.all())
        return Feed.add_jobs_status_count(tag.feeds.filter(lookup).distinct())


class FeedTaggingList(generics.ListCreateAPIView):
    """
    A view for the feed-specific collection of taggings.
    """
    http_method_names = ['get', 'post']
    queryset = Feed.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly)

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
        return Tagging.objects.filter(feed=feed)


class TagTaggingList(generics.ListCreateAPIView):
    """
    A view for the collection of tag-specific taggings.
    """
    http_method_names = ['get', 'post']
    queryset = Tag.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)

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
        queryset = self.get_taggings_queryset(request.user)
        response = services.get_list_response(self, queryset)
        tag = self.get_object()
        links = {'tag': reverse('tag-detail', request=request,
                                   kwargs={"pk": tag.id})}
        response = services.append_collection_links(response, links)
        template_data = {"feed_id": ""}
        return services.append_collection_template(response, template_data)

    def get_taggings_queryset(self, user):
        """
        Custom method to get the actual taggings queryset for the tag.
        """
        tag = self.get_object()

        if not user.is_authenticated:
            return Tagging.objects.filter(tag=tag).filter(feed__public=True)

        lookup = Q(feed__owner=user) | (Q(feed__public=True) | Q(
            feed__shared_users=user) | Q(feed__shared_groups__in=user.groups.all()))
        return Tagging.objects.filter(tag=tag).filter(lookup).distinct()


class TaggingDetail(generics.RetrieveDestroyAPIView):
    """
    A tagging view.
    """
    http_method_names = ['get', 'delete']
    queryset = Tagging.objects.all()
    serializer_class = TaggingSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsChrisOrFeedOwnerOrHasFeedPermissionOrPublicFeedReadOnly)


class FeedList(generics.ListAPIView):
    """
    A view for the collection of feeds. This is also the API's "homepage".
    """
    http_method_names = ['get']
    serializer_class = FeedSerializer

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feeds 
        owned by the currently authenticated user and those that have been shared with
        the user.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Feed.objects.none()

        # if the user is chris then return all the non-public feeds in the system
        if user.username == 'chris':
            return Feed.add_jobs_status_count(Feed.objects.exclude(public=True))

        lookup = Q(owner=user) | Q(shared_users=user) | Q(
            shared_groups__in=user.groups.all())
        return Feed.add_jobs_status_count(Feed.objects.filter(lookup))

    def list(self, request, *args, **kwargs):
        """
        Overriden to append document-level link relations and a query list to the
        response.
        """
        response = super(FeedList, self).list(request, *args, **kwargs)

        # append query list
        query_list = [reverse('feed-list-query-search', request=request)]
        response = services.append_collection_querylist(response, query_list)

        # append document-level link relations
        links = {'chrisinstance': reverse('chrisinstance-detail', request=request,
                                          kwargs={"pk": 1}),
                 'public_feeds': reverse('publicfeed-list', request=request),
                 'compute_resources': reverse('computeresource-list', request=request),
                 'plugin_metas': reverse('pluginmeta-list', request=request),
                 'plugins': reverse('plugin-list', request=request),
                 'plugin_instances': reverse('allplugininstance-list', request=request),
                 'pipelines': reverse('pipeline-list', request=request),
                 'workflows': reverse('allworkflow-list', request=request),
                 'tags': reverse('tag-list', request=request),
                 'pipelinesourcefiles': reverse('pipelinesourcefile-list',
                                                request=request),
                 'userfiles': reverse('userfile-list', request=request),
                 'pacs': reverse('pacs-list', request=request),
                 'pacsqueries': reverse('allpacsquery-list', request=request),
                 'pacsfiles': reverse('pacsfile-list', request=request),
                 'pacsseries': reverse('pacsseries-list', request=request),
                 'filebrowser': reverse('chrisfolder-list', request=request)}

        user = self.request.user

        if user.is_authenticated:
            links['download_tokens'] = reverse('filedownloadtoken-list', request=request)
            links['groups'] = reverse('group-list', request=request)
            links['user'] = reverse('user-detail', request=request, kwargs={"pk": user.id})

            if user.is_staff:
                links['admin'] = reverse('admin-plugin-list', request=request)
        return services.append_collection_links(response, links)


class FeedListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of feeds resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = FeedSerializer
    filterset_class = FeedFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feeds 
        owned by the currently authenticated user and those that have been shared with
        the user.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Feed.objects.none()

        # if the user is chris then return all the non-public feeds in the system
        if user.username == 'chris':
            return Feed.add_jobs_status_count(Feed.objects.exclude(public=True))

        lookup = Q(owner=user) | Q(shared_users=user) | Q(
            shared_groups__in=user.groups.all())
        return Feed.add_jobs_status_count(Feed.objects.filter(lookup))


class FeedDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A feed view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = Feed.add_jobs_status_count(Feed.objects.all())
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(FeedDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"name": "", "public": ""}
        return services.append_collection_template(response, template_data)


class PublicFeedList(generics.ListAPIView):
    """
    A view for the collection of public feeds.
    """
    http_method_names = ['get']
    serializer_class = FeedSerializer

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feeds
        that are public.
        """
        return Feed.add_jobs_status_count(Feed.objects.filter(public=True))

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a query list to the response.
        """
        response = super(PublicFeedList, self).list(request, *args, **kwargs)

        # append query list
        query_list = [reverse('publicfeed-list-query-search', request=request)]
        return services.append_collection_querylist(response, query_list)


class PublicFeedListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of public feeds resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = FeedSerializer
    filterset_class = FeedFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is only comprised by the feeds
        that are public.
        """
        return Feed.add_jobs_status_count(Feed.objects.filter(public=True))


class FeedGroupPermissionList(generics.ListCreateAPIView):
    """
    A view for a feed's collection of group permissions.
    """
    http_method_names = ['get', 'post']
    queryset = Feed.objects.all()
    serializer_class = FeedGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a group and feed before first saving to the DB.
        """
        group = serializer.validated_data.pop('grp_name')
        feed = self.get_object()
        serializer.save(group=group, feed=feed)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the group permissions for the queried feed.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_group_permissions_queryset()
        response = services.get_list_response(self, queryset)
        feed = self.get_object()

        query_list = [reverse('feedgrouppermission-list-query-search',
                              request=request, kwargs={"pk": feed.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        response = services.append_collection_links(response, links)

        template_data = {"grp_name": ""}
        return services.append_collection_template(response, template_data)

    def get_group_permissions_queryset(self):
        """
        Custom method to get the actual group permissions queryset for the feed.
        """
        feed = self.get_object()
        return FeedGroupPermission.objects.filter(feed=feed)


class FeedGroupPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of feed-specific group permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FeedGroupPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasPermissionReadOnly)
    filterset_class = FeedGroupPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the feed-specific
        group permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FeedGroupPermission.objects.none()
        feed = get_object_or_404(Feed, pk=self.kwargs['pk'])
        return FeedGroupPermission.objects.filter(feed=feed)


class FeedGroupPermissionDetail(generics.RetrieveDestroyAPIView):
    """
    A view for a feed's group permission.
    """
    http_method_names = ['get', 'delete']
    serializer_class = FeedGroupPermissionSerializer
    queryset = FeedGroupPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChrisOrFeedOwnerOrHasFeedPermissionReadOnly)

    def perform_destroy(self, instance):
        """
        Overriden to remove the group permission for the link file in the SHARED folder
        pointing to the feed's folder. The link file itself is removed if all
        its permissions have been removed.
        """
        feed = instance.feed
        group = instance.group

        lf = feed.folder.get_shared_link()
        if lf is not None:
            lf.remove_group_permission(group, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                feed.folder.remove_shared_link()
        super(FeedGroupPermissionDetail, self).perform_destroy(instance)


class FeedUserPermissionList(generics.ListCreateAPIView):
    """
    A view for a feed's collection of user permissions.
    """
    http_method_names = ['get', 'post']
    queryset = Feed.objects.all()
    serializer_class = FeedUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasPermissionReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to provide a user and feed before first saving to the DB.
        """
        user = serializer.validated_data.pop('username')
        feed = self.get_object()
        serializer.save(user=user, feed=feed)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the user permissions for the queried feed.
        A query list, document-level link relations and a collection+json template are
        also added to the response.
        """
        queryset = self.get_user_permissions_queryset()
        response = services.get_list_response(self, queryset)
        feed = self.get_object()

        query_list = [reverse('feeduserpermission-list-query-search',
                              request=request, kwargs={"pk": feed.id})]
        response = services.append_collection_querylist(response, query_list)

        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        response = services.append_collection_links(response, links)

        template_data = {"username": ""}
        return services.append_collection_template(response, template_data)

    def get_user_permissions_queryset(self):
        """
        Custom method to get the actual user permissions queryset for the feed.
        """
        feed = self.get_object()
        return FeedUserPermission.objects.filter(feed=feed)


class FeedUserPermissionListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of feed-specific user permissions resulting from a query
    search.
    """
    http_method_names = ['get']
    serializer_class = FeedUserPermissionSerializer
    permission_classes = (permissions.IsAuthenticated,
                          IsOwnerOrChrisOrHasPermissionReadOnly)
    filterset_class = FeedUserPermissionFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the feed-specific
        user permissions.
        """
        if getattr(self, "swagger_fake_view", False):
            return FeedUserPermission.objects.none()
        feed = get_object_or_404(Feed, pk=self.kwargs['pk'])
        return FeedUserPermission.objects.filter(feed=feed)


class FeedUserPermissionDetail(generics.RetrieveDestroyAPIView):
    """
    A view for a feed's user permission.
    """
    http_method_names = ['get', 'delete']
    serializer_class = FeedUserPermissionSerializer
    queryset = FeedUserPermission.objects.all()
    permission_classes = (permissions.IsAuthenticated,
                          IsChrisOrFeedOwnerOrHasFeedPermissionReadOnly)

    def perform_destroy(self, instance):
        """
        Overriden to remove the group permission for the link file in the SHARED folder
        pointing to the feed's folder. The link file itself is removed if all
        its permissions have been removed.
        """
        feed = instance.feed
        user = instance.user

        lf = feed.folder.get_shared_link()
        if lf is not None:
            lf.remove_user_permission(user, 'r')

            if not lf.shared_groups.all().exists() and not lf.shared_users.all().exists():
                feed.folder.remove_shared_link()
        super(FeedUserPermissionDetail, self).perform_destroy(instance)


class CommentList(generics.ListCreateAPIView):
    """
    A view for the collection of comments.
    """
    http_method_names = ['get', 'post']
    queryset = Feed.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly)

    def perform_create(self, serializer):
        """
        Overriden to associate an owner and feed with the comment
        before first saving to the DB.
        """
        serializer.save(owner=self.request.user, feed=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the comments for the queried feed.
        A query list, collection+json write template and document-level link relation
        are also added to the response.
        """
        queryset = self.get_comments_queryset()
        response = services.get_list_response(self, queryset)
        feed = self.get_object()

        # append query list
        query_list = [reverse('comment-list-query-search', request=request,
                              kwargs={"pk": feed.id})]
        response = services.append_collection_querylist(response, query_list)

        # append document-level link relations
        links = {'feed': reverse('feed-detail', request=request,
                                   kwargs={"pk": feed.id})}
        response = services.append_collection_links(response, links)

        # append write template
        template_data = {"title": "", "content": ""}
        return services.append_collection_template(response, template_data)

    def get_comments_queryset(self):
        """
        Custom method to get the actual comments' queryset.
        """
        feed = self.get_object()
        return self.filter_queryset(feed.comments.all())


class CommentListQuerySearch(generics.ListAPIView):
    """
    A view for the collection of feed-specific comments resulting from a query search.
    """
    http_method_names = ['get']
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly)
    filterset_class = CommentFilter

    def get_queryset(self):
        """
        Overriden to return a custom queryset that is comprised by the feed-specific
        comments.
        """
        if getattr(self, 'swagger_fake_view', False):
            return Feed.comments.field.model.objects.none()
        feed = get_object_or_404(Feed, pk=self.kwargs['pk'])
        return feed.comments.all()


class CommentDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    A comment view.
    """
    http_method_names = ['get', 'put', 'delete']
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (
        permissions.IsAuthenticatedOrReadOnly,
        IsOwnerOrChrisOrFeedOwnerOrHasFeedPermissionReadOnlyOrPublicFeedReadOnly,)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        response = super(CommentDetail, self).retrieve(request, *args, **kwargs)
        template_data = {"title": "", "content": ""}
        return services.append_collection_template(response, template_data)


# @extend_schema_view(
#     get=extend_schema(operation_id='feed_plugins_instances_list')
# )
class FeedPluginInstanceList(generics.ListAPIView):
    """
    A view for the collection of feed-specific plugin instances.
    """
    http_method_names = ['get']
    queryset = Feed.objects.all()
    serializer_class = PluginInstanceSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrChrisOrHasPermissionOrPublicReadOnly)

    def list(self, request, *args, **kwargs):
        """
        Overriden to return a list of the plugin instances for the queried feed.
        """
        queryset = self.get_plugin_instances_queryset()
        response = services.get_list_response(self, queryset)
        feed = self.get_object()
        links = {'feed': reverse('feed-detail', request=request, kwargs={"pk": feed.id})}
        return services.append_collection_links(response, links)

    def get_plugin_instances_queryset(self):
        """
        Custom method to get the actual plugin instances queryset.
        """
        feed = self.get_object()
        return self.filter_queryset(feed.plugin_instances.all())
