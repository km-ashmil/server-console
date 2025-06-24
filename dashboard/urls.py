from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('servers/', views.server_overview, name='server_overview'),
    path('activity/', views.activity_logs, name='activity_logs'),
]