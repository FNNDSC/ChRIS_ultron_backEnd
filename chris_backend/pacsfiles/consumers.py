import json

import channels.exceptions
from channels.generic.websocket import WebsocketConsumer
from rest_framework import permissions

from pacsfiles.permissions import IsChrisOrIsPACSUserReadOnly


class PACSFileProgress(WebsocketConsumer):

    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly,)

    def connect(self):
        if not self._has_permission():
            raise channels.exceptions.DenyConnection()
        self.accept()

    def _has_permission(self) -> bool:
        """
        Manual permissions check.

        django-channels is going to handle authentication for us,
        but we need to implement permissions ourselves.
        """
        self.user = self.scope.get('user', None)
        if self.user is None:
            return False
        return all(
            permission().has_permission(self, self.__class__)
            for permission in self.permission_classes
        )

    def disconnect(self, close_code):
        pass

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        self.send(text_data=json.dumps({"message": message}))