
from django.contrib.auth.models import User

from rest_framework import generics

from .serializers import UserSerializer


class UserCreate(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        """
        Overriden to associate an owner, a plugin and a previous plugin instance with
        the newly created plugin instance before first saving to the DB. All the plugin
        instace's parameters in the resquest are also properly saved to the DB. Finally
        the plugin's app is run with the provided plugin instance's parameters.

        plugin = self.get_object()
        request_data = serializer.context['request'].data
        # get previous plugin instance
        previous_id = ""
        if 'previous_id' in request_data:
            previous_id = request_data['previous_id']
        previous = serializer.validate_previous(previous_id, plugin)
        # create plugin instance with corresponding owner, plugin and previous instances
        plugin_inst = serializer.save(owner=self.request.user, plugin=plugin,
                                      previous=previous)
        """

class UserDetail(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer