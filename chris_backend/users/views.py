
from django.contrib.auth.models import User
from rest_framework import generics, permissions
from rest_framework.response import Response

from collectionjson import services

from .serializers import UserSerializer
from .permissions import IsUserOrChrisOrReadOnly


class UserCreate(generics.ListCreateAPIView):
    http_method_names = ['get', 'post']
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json write template.
        """
        response = services.get_list_response(self, [])
        template_data = {"username": "", "password": "", "email": ""}
        return services.append_collection_template(response, template_data)


class UserDetail(generics.RetrieveUpdateAPIView):
    http_method_names = ['get', 'put']
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsUserOrChrisOrReadOnly)

    def retrieve(self, request, *args, **kwargs):
        """
        Overriden to append a collection+json template.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data)
        template_data = {"password": "", "email": ""}
        return services.append_collection_template(response, template_data)

    def update(self, request, *args, **kwargs):
        """
        Overriden to add required username before serializer validation.
        """
        user = self.get_object()
        request.data['username'] = user.username
        return super(UserDetail, self).update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Overriden to update user's password and email when requested by a PUT request.
        """
        serializer.save(email=serializer.validated_data.get("email"))
        user = self.get_object()
        password = serializer.validated_data.get("password")
        user.set_password(password)
        user.save()
