import rest_framework.permissions
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework import permissions

from pacsfiles.permissions import IsChrisOrIsPACSUserReadOnly


class PACSFileProgress(AsyncJsonWebsocketConsumer):
    """
    A WebSockets endpoint which relays progress messages from NATS sent by *oxidicom* to a client.
    """

    permission_classes = (permissions.IsAuthenticated, IsChrisOrIsPACSUserReadOnly,)

    async def connect(self):
        if not await self._has_permission():
            await self.close()
        else:
            await self.accept()

    async def receive_json(self, content, **kwargs):
        ...

    async def disconnect(self, code):
        ...

    @database_sync_to_async
    def _has_permission(self) -> bool:
        """
        Manual permissions check.

        django-channels is going to handle authentication for us,
        but we need to implement permissions ourselves.
        """
        self.user = self.scope.get('user', None)
        if self.user is None:
            return False
        if getattr(self, 'method', None) is None:
            # make it work with ``IsChrisOrIsPACSUserReadOnly``
            self.method = rest_framework.permissions.SAFE_METHODS[0]

        return all(
            permission().has_permission(self, self.__class__)
            for permission in self.permission_classes
        )
