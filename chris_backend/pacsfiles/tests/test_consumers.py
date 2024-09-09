import jwt
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import User, Group

# note: use TransactionTestCase instead of TestCase for async tests that speak to DB.
# See https://stackoverflow.com/a/71763849
from django.test import TransactionTestCase

from channels.testing import WebsocketCommunicator
from django.utils import timezone

from core.models import FileDownloadToken
from core.websockets.auth import TokenQsAuthMiddleware

from pacsfiles.consumers import PACSFileProgress


class PACSFileProgressTests(TransactionTestCase):

    def setUp(self):
        self.username = 'PintoGideon'
        self.password = 'gideon1234'
        self.email = 'gideon@example.org'
        self.user = User.objects.create_user(username=self.username,
                                             email=self.email,
                                             password=self.password)
        pacs_grp, _ = Group.objects.get_or_create(name='pacs_users')
        self.user.groups.set([pacs_grp])
        self.user.save()

    async def test_my_consumer(self):
        token = await self._get_download_token()
        app = TokenQsAuthMiddleware(PACSFileProgress.as_asgi())
        communicator = WebsocketCommunicator(app, f'v1/pacs/ws/?token={token.token}')
        connected, subprotocol = await communicator.connect()
        assert connected

    async def test_unauthenticated_not_connected(self):
        app = TokenQsAuthMiddleware(PACSFileProgress.as_asgi())
        communicator = WebsocketCommunicator(app, 'v1/pacs/ws/')  # no token
        connected, subprotocol = await communicator.connect()
        assert not connected

    @database_sync_to_async
    def _get_download_token(self) -> FileDownloadToken:
        """
        Copy-pasted from
        https://github.com/FNNDSC/ChRIS_ultron_backEnd/blob/7bcccc2031386955875ef4e9758025577f5ee067/chris_backend/userfiles/tests/test_views.py#L210-L213
        """
        dt = timezone.now() + timezone.timedelta(minutes=10)
        token = jwt.encode({'user': self.user.username, 'exp': dt}, settings.SECRET_KEY,
                           algorithm='HS256')
        return FileDownloadToken.objects.create(token=token, owner=self.user)