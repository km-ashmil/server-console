from django.contrib import admin
from .models import Server, ServerGroup, ServerConnection, ServerLog

@admin.register(ServerGroup)
class ServerGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'created_at']
    list_filter = ['created_at', 'created_by']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']

@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'hostname', 'port', 'username', 'status', 'group', 'created_by', 'last_checked']
    list_filter = ['status', 'auth_method', 'group', 'created_at', 'last_checked']
    search_fields = ['name', 'hostname', 'username', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_checked', 'encrypted_password', 'encrypted_private_key', 'encrypted_key_password']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'hostname', 'port', 'username', 'description', 'group', 'tags')
        }),
        ('Authentication', {
            'fields': ('auth_method',),
            'description': 'Encrypted credentials are stored securely and not displayed here.'
        }),
        ('Settings', {
            'fields': ('timeout', 'keep_alive')
        }),
        ('Status', {
            'fields': ('status', 'last_checked', 'last_error')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(ServerConnection)
class ServerConnectionAdmin(admin.ModelAdmin):
    list_display = ['server', 'user', 'session_id', 'connected_at', 'last_activity', 'is_active']
    list_filter = ['is_active', 'connected_at', 'last_activity']
    search_fields = ['server__name', 'user__username', 'session_id']
    readonly_fields = ['connected_at', 'last_activity']

@admin.register(ServerLog)
class ServerLogAdmin(admin.ModelAdmin):
    list_display = ['server', 'user', 'log_type', 'timestamp', 'session_id']
    list_filter = ['log_type', 'timestamp', 'server']
    search_fields = ['server__name', 'user__username', 'message']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically