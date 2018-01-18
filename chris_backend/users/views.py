
from django.contrib.auth.models import User

from rest_framework import generics, permissions

from .serializers import UserSerializer
from .permissions import IsUserOrChris


class UserCreate(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsUserOrChris)