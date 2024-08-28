"""
Websockets authentication.

Notes
-----

``channels.auth.AuthMiddlewareStack`` depends on HTTP headers, however HTTP headers
cannot be set for websockets in the web browser. https://stackoverflow.com/a/4361358

A common pattern is to put a token in the query string. We will re-use the file "downloadtokens"
for this purpose.
"""

import urllib.parse
from typing import AnyStr

from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed

from core.views import authenticate_token


class TokenQsAuthMiddleware:
    """
    Authenticate the request using :class:`TokenAuthSupportQueryString`.

    Based on
    https://channels.readthedocs.io/en/3.x/topics/authentication.html#custom-authentication
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope['user'] = await self._authenticate(scope)
        return await self.app(scope, receive, send)

    @database_sync_to_async
    def _authenticate(self, scope) -> User | None:
        params = _parse_qs_last_string(scope.get('query_string', b''))
        if token := params.get('token', None):
            try:
                return authenticate_token(token)
            except AuthenticationFailed:
                return None
        return None


def _parse_qs_last_string(qs: AnyStr, encoding='utf-8') -> dict[str, str]:
    if isinstance(qs, bytes):
        qs = qs.decode(encoding=encoding)
    return {k: v[-1] for k, v in urllib.parse.parse_qs(qs).items()}
