from django.urls import path
from . import views

app_name = 'terminal'

urlpatterns = [
    path('<int:server_id>/', views.terminal_view, name='connect'),
    path('sessions/', views.terminal_sessions, name='sessions'),
    path('<int:server_id>/logs/', views.terminal_logs, name='logs'),
    path('close/<str:session_id>/', views.close_session, name='close_session'),
]