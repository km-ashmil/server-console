from django.urls import path
from . import views

app_name = 'ansible_manager'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Playbook URLs
    path('playbooks/', views.playbook_list, name='playbook_list'),
    path('playbooks/create/', views.playbook_create, name='playbook_create'),
    path('playbooks/<uuid:playbook_id>/', views.playbook_detail, name='playbook_detail'),
    path('playbooks/<uuid:playbook_id>/edit/', views.playbook_edit, name='playbook_edit'),
    path('playbooks/<uuid:playbook_id>/delete/', views.playbook_delete, name='playbook_delete'),
    
    # Inventory URLs
    path('inventories/', views.inventory_list, name='inventory_list'),
    path('inventories/create/', views.inventory_create, name='inventory_create'),
    path('inventories/<uuid:inventory_id>/', views.inventory_detail, name='inventory_detail'),
    path('inventories/<uuid:inventory_id>/edit/', views.inventory_edit, name='inventory_edit'),
    path('inventories/<uuid:inventory_id>/sync/', views.inventory_sync, name='inventory_sync'),
    
    # Execution URLs
    path('executions/', views.execution_list, name='execution_list'),
    path('executions/create/', views.execution_create, name='execution_create'),
    path('executions/<uuid:execution_id>/', views.execution_detail, name='execution_detail'),
    path('executions/<uuid:execution_id>/cancel/', views.execution_cancel, name='execution_cancel'),
    path('executions/<uuid:execution_id>/stream/', views.execution_output_stream, name='execution_output_stream'),
    
    # Template URLs
    path('templates/', views.template_list, name='template_list'),
    path('templates/<uuid:template_id>/', views.template_detail, name='template_detail'),
    path('templates/<uuid:template_id>/create-playbook/', views.playbook_from_template, name='playbook_from_template'),
    
    # API URLs
    path('api/playbooks/', views.api_playbooks, name='api_playbooks'),
    path('api/inventories/', views.api_inventories, name='api_inventories'),
    path('api/executions/<uuid:execution_id>/status/', views.api_execution_status, name='api_execution_status'),
    path('api/inventories/<uuid:inventory_id>/sync/', views.api_inventory_sync, name='api_inventory_sync'),
]