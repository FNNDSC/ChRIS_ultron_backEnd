import json
from typing import Optional, Self
from django.http import HttpRequest, StreamingHttpResponse
import rest_framework.permissions
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from rest_framework import permissions
# from django.views import View
from rest_framework.views import View
from rest_framework import generics
from rest_framework.request import Request

import asyncio

import nats
from nats.aio.client import Client
from pacsfiles.lonk import (
    LonkClient,
    LonkDone,
    LonkError,
    LonkProgress,
    validate_subscription,
    LonkWsSubscription,
    Lonk,
    validate_unsubscription,
    subject_of,
    _serialize_to_lonkws,
)
from pacsfiles.permissions import IsChrisOrIsPACSUserReadOnly

_SLEEP_TIME_SECOND = 0.1


class PACSFileProgressSSE(View):
    '''
    permission_classes = (
        permissions.IsAuthenticated,
        IsChrisOrIsPACSUserReadOnly,
    )
    '''

    async def get(self: Self, request: Request, *args, **kwargs):
        return StreamingHttpResponse(self.pacs_file_progress_sse(request, *args, **kwargs), content_type="text/event-stream")

    async def post(self: Self, request: Request, *args, **kwargs):
        return StreamingHttpResponse(self.pacs_file_progress_sse(request, *args, **kwargs), content_type="text/event-stream")

    async def pacs_file_progress_sse(self: Self, request: Request, *args: list, **kwargs: dict):
        pacs_name, series_instance_uids = self._get_info(request)

        queue = asyncio.Queue()
        the_progress = {each: 0 for each in series_instance_uids}

        # 1. client
        client, err = await self._get_client()
        if err is not None:
            yield self._event_response(self._err_msg(f'unable to connect nats: e: {err}'))
            return

        # 2. subscribe
        err = await self._subscribe(client, pacs_name, series_instance_uids, queue)
        if err is not None:
            errmsg = f'unable to subscribe: e: {err}'
            print(f'[ERROR] consumer.pacs_file_progress_sse: pacs_name: {pacs_name} e: {err}')  # noqa
            yield self._event_response(self._err_msg(await self._safe_close_client(client, errmsg)))
            return

        # 3. loop for queue.
        is_last_iteration_processed = False
        err = None
        while True:
            if is_last_iteration_processed and self._is_all_end(the_progress):
                break

            msg, err = await self._get_msg(queue)
            if err:
                break

            if not msg:
                await asyncio.sleep(_SLEEP_TIME_SECOND)
                is_last_iteration_processed = False
                continue

            self._process_msg(msg, the_progress)
            is_last_iteration_processed = True
            yield self._event_response(msg)

        # 4. close client
        errmsg = '' if not err else f'unable to get msg: e: {err}'
        err = await self._safe_close_client(client, errmsg)

        # 5. final yield.
        yield self._event_response(self._all_done() if not err else self._err_msg(err))

    async def _get_client(self: Self) -> tuple[Optional[LonkClient], Optional[Exception]]:
        client: Optional[LonkClient] = None
        try:
            client = await LonkClient.connect(
                settings.NATS_ADDRESS
            )
        except Exception as e:
            return None, e

        if client is None:
            return None, Exception('(unknown)')

        return client, None

    async def _subscribe(self: Self, client: LonkClient, pacs_name: str, series_instance_uids: list[str], queue: asyncio.Queue) -> Optional[Exception]:
        try:
            for each_series_uid in series_instance_uids:
                await client.subscribe(pacs_name, each_series_uid, lambda msg: queue.put(msg))
        except Exception as e:
            return e

        return None

    async def _get_msg(self: Self, queue: asyncio.Queue) -> tuple[Optional[Lonk], Optional[Exception]]:
        try:
            msg: Lonk = queue.get_nowait()
            if not msg:
                return None, None
            return msg, None
        except asyncio.QueueEmpty as e:
            return None, None
        except Exception as e:
            return None, e

    def _event_response(self: Self, data: dict):
        return f'event: message\ndata: {json.dumps(data)}\n\n'

    def _all_done(self: Self):
        return {'pacs_name': '', 'SeriesInstanceUID': '', 'message': {'done': True}}

    def _err_msg(self: Self, errmsg: str):
        return {'pacs_name': '', 'SeriesInstanceUID': '', 'message': {'error': errmsg}}

    def _is_all_end(self: Self, the_progress: dict):
        for val in the_progress.values():
            if val not in ['done', 'error']:
                return False

        return True

    def _process_msg(self: Self, msg: Lonk, the_progress: dict):
        series_uid = msg['SeriesInstanceUID']
        message = msg['message']
        if 'done' in message:  # done
            the_progress[series_uid] = 'done'
        elif 'error' in message:  # error
            the_progress[series_uid] = 'error'
        elif 'ndicom' in message:
            the_progress[series_uid] = message['ndicom']

    async def _safe_close_client(self: Self, client: Optional[LonkClient], err: Optional[Exception]) -> Optional[Exception]:
        if client is None:
            return err

        try:
            await client.close()
            return err
        except Exception as e:
            return Exception(f'unable to close nats: e: {e} err: {err}')

    def _get_info(self: Self, request: Request) -> tuple[str, list[str]]:
        pacs_names = request.GET.get('pacs_name', [])
        if not pacs_names:
            return '', []

        pacs_name = pacs_names

        series_instance_uids_strs = request.GET.get('series_uids', [])
        if not series_instance_uids_strs:
            return pacs_name, []

        series_instance_uids_str = series_instance_uids_strs

        series_instance_uids = series_instance_uids_str.split(',')

        return pacs_name, series_instance_uids

    def _msg_to_response(self: Self, msg: LonkProgress | LonkError | LonkDone | LonkWsSubscription, the_progress: dict) -> tuple[dict, dict]:
        ret = {}
        if isinstance(msg, LonkProgress):
            n_dicom = msg.ndicom

            pass
        elif isinstance(msg, LonkError):
            pass
        elif isinstance(msg, LonkDone):
            pass
        elif isinstance(msg, LonkWsSubscription):
            pass
        pass


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
        if validate_unsubscription(content):
            await self._unsubscribe_all()
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
                message=LonkWsSubscription(subscribed=True),
            )
            await self.send_json(response)
        except Exception as e:
            response = Lonk(
                pacs_name=pacs_name,
                SeriesInstanceUID=series_instance_uid,
                message=LonkWsSubscription(subscribed=False),
            )
            await self.send_json(response)
            await self.close(code=500)
            raise e

    async def _unsubscribe_all(self):
        """
        Unsubscribe from *all* series notifications.
        """
        try:
            await self.client.unsubscribe_all()
            await self.send_json({'message': {'subscribed': False}})
        except Exception as e:
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
