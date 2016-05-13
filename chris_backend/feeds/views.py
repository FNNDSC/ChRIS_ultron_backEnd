from django.contrib.auth.models import User

from rest_framework import generics, permissions

from .models import Note, Tag, Feed, Comment
from .serializers import UserSerializer
from .serializers import NoteSerializer, TagSerializer, FeedSerializer, CommentSerializer 
from .permissions import IsOwnerOrChris


class NoteDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Note.objects.all()
    serializer_class = NoteSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)


class TagList(generics.ListCreateAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated,)


class TagDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwnerOrChris,)


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


class CommentList(generics.ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


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

