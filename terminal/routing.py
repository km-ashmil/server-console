from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/terminal/(?P<server_id>\d+)/$', consumers.TerminalConsumer.as_asgi()),
    re_path(r'ws/terminal/(?P<server_id>\d+)/(?P<session_id>[\w-]+)/$', consumers.TerminalConsumer.as_asgi()),
]