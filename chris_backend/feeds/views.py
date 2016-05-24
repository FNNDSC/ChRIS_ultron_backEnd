from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User

from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import Note, Tag, Feed, Comment
from .serializers import UserSerializer
from .serializers import NoteSerializer, TagSerializer, FeedSerializer, CommentSerializer
from .permissions import IsOwnerOrChris, IsOwnerOrChrisOrReadOnly
from .permissions import IsRelatedFeedOwnerOrChris 


class NoteDetail(generics.RetrieveUpdateAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = (permissions.IsAuthenticated, IsRelatedFeedOwnerOrChris)
    

class TagList(generics.ListCreateAPIView):
    queryset = Feed.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, feed=[self.get_object()])

    def list(self, request, *args, **kwargs):
        """
        This view should return a list of the tags for the queried
        feed that are owned by the currently authenticated user.
        """
        feed = self.get_object()
        tags = [tag for tag in feed.tags.all() if tag.owner==request.user]
        queryset = self.filter_queryset(tags)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris)


class FeedList(generics.ListCreateAPIView):
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def perform_create(self, serializer):
        # set a list of owners when creating a new feed
        serializer.save(owner=[self.request.user])

    def get_queryset(self):
        """
        This view should return a list of all the feeds
        for the currently authenticated user.
        """
        user = self.request.user
        if (user.username == 'chris'):
            return Feed.objects.all()
        return Feed.objects.filter(owner=user)


class FeedDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Feed.objects.all()
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)

    def perform_update(self, serializer):
        # check system registered owners when updating feed's owners
        feed = self.get_object()
        currentOwners = feed.owner.values('username')
        newOwners = []
        if 'owners' in self.request.data: 
            usernames = self.request.data.pop('owners')
            for usern in usernames:
                if {'username': usern} not in currentOwners:
                    try:
                        owner = User.objects.get(username=usern)
                    except ObjectDoesNotExist:
                        pass
                    else:
                        newOwners.append(owner)
        if newOwners:
            currentOwners = [owner for owner in feed.owner.all()]
            serializer.save(owner=currentOwners+newOwners)


class CommentList(generics.ListCreateAPIView):
    queryset = Feed.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, feed=self.get_object())

    def list(self, request, *args, **kwargs):
        """
        This view should return a list of the comments for the queried feed.
        """
        feed = self.get_object()
        queryset = self.filter_queryset(feed.comments.all())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CommentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChrisOrReadOnly,)


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

