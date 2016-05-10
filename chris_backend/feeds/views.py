from django.contrib.auth.models import User

from rest_framework import generics, permissions

from .models import Feed
from .serializers import FeedSerializer, UserSerializer
from .permissions import IsOwnerOrChris


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


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

