"""
Async routes.
"""

from django.urls import re_path
from pacsfiles import consumers

websocket_urlpatterns = [
    re_path(r'v1/pacs/progress/',
            consumers.PACSFileProgress.as_asgi()),
]