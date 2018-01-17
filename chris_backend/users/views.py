
from django.contrib.auth.models import User

from rest_framework import generics, permissions

from .serializers import UserSerializer
from .permissions import IsUserOrChris


class UserCreate(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with
        the newly created plugin instance before first saving to the DB. All the plugin
        instace's parameters in the resquest are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.
        """
        if serializer.is_valid(raise_exception=True):
            serializer.save()


class UserDetail(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsUserOrChris)