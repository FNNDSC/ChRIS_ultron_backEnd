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
    

class TagList(generics.GenericAPIView):
    queryset = Feed.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        feed = self.get_object()
        serializer = TagSerializer(feed.tags, context={'request': request}, many=True)
        return Response(serializer.data)


class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated,)


class FeedList(generics.ListCreateAPIView):
    serializer_class = FeedSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

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


class CommentList(generics.GenericAPIView):
    queryset = Feed.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        feed = self.get_object()
        serializer = CommentSerializer(feed.comments, context={'request': request}, many=True)
        return Response(serializer.data)


class CommentDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

