import rest_framework.permissions
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from rest_framework import permissions

from pacsfiles.lonk import (
    LonkClient,
    validate_subscription,
    LonkWsSubscription,
    Lonk,
)
from pacsfiles.permissions import IsChrisOrIsPACSUserReadOnly


class PACSFileProgress(AsyncJsonWebsocketConsumer):
    """
    A WebSockets endpoint which relays progress messages from NATS sent by *oxidicom* to a client.
    """

    permission_classes = (
        permissions.IsAuthenticated,
        IsChrisOrIsPACSUserReadOnly,
    )

    async def connect(self):
        if not await self._has_permission():
            return await self.close()
        self.client: LonkClient = await LonkClient.connect(
            settings.NATS_ADDRESS
        )
        await self.accept()

    async def receive_json(self, content, **kwargs):
        if validate_subscription(content):
            await self._subscribe(
                content['pacs_name'], content['SeriesInstanceUID']
            )
            return
        await self.close(code=400, reason='Invalid subscription')

    async def _subscribe(self, pacs_name: str, series_instance_uid: str):
        """
        Subscribe to progress notifications about the reception of a DICOM series.
        """
        try:
            await self.client.subscribe(
                pacs_name, series_instance_uid, lambda msg: self.send_json(msg)
            )
            response = Lonk(
                pacs_name=pacs_name,
                SeriesInstanceUID=series_instance_uid,
                message=LonkWsSubscription(subscription='subscribed'),
            )
            await self.send_json(response)
        except Exception as e:
            response = Lonk(
                pacs_name=pacs_name,
                SeriesInstanceUID=series_instance_uid,
                message=LonkWsSubscription(subscription='error'),
            )
            await self.send_json(response)
            await self.close(code=500)
            raise e

    async def disconnect(self, code):
        await super().disconnect(code)
        await self.client.close()

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
