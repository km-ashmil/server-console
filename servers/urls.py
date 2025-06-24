from django.urls import path
from . import views

app_name = 'servers'

urlpatterns = [
    # Server URLs
    path('', views.server_list, name='list'),
    path('add/', views.server_create, name='create'),
    path('<int:pk>/', views.server_detail, name='detail'),
    path('<int:pk>/edit/', views.server_edit, name='edit'),
    path('<int:pk>/delete/', views.server_delete, name='delete'),
    path('<int:pk>/test/', views.server_test, name='test'),
    path('<int:pk>/status/', views.server_check_status, name='check_status'),
    
    # Group URLs
    path('groups/', views.group_list, name='group_list'),
    path('groups/add/', views.group_create, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
]