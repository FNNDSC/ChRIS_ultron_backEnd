
from django.contrib.auth.models import User

from rest_framework import generics, permissions
from rest_framework.response import Response

from collectionjson import services

from .serializers import UserSerializer
from .permissions import IsUserOrChris


class UserCreate(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserList(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        """
        Overriden to return a queryset comprised only by the currently authenticated user.
        """
        return [self.request.user]


class UserDetail(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsUserOrChris)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data)
        template_data = {"password": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to add required username to the request before serializer validation.
        """
        user = self.get_object()
        request.data['username'] = user.username
        return super(UserDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to update user's password when requested by a PUT request.
        """
        user = self.get_object()
        new_password = serializer.validated_data.get("password")
        user.set_password(new_password)
        user.save()