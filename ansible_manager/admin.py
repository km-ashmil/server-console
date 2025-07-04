from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    AnsiblePlaybook, AnsibleInventory, AnsibleVault, AnsibleRole,
    AnsibleExecution, AnsibleSchedule, AnsibleTemplate
)


@admin.register(AnsiblePlaybook)
class AnsiblePlaybookAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'category', 'status', 'version', 'created_by', 'created_at', 'execution_count']
    list_filter = ['category', 'status', 'created_at', 'created_by']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'version']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'display_name', 'description', 'category', 'status']
        }),
        ('Content', {
            'fields': ['content', 'variables'],
            'classes': ['collapse']
        }),
        ('Execution Settings', {
            'fields': ['timeout', 'max_parallel', 'tags']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at', 'version'],
            'classes': ['collapse']
        })
    ]
    
    def execution_count(self, obj):
        count = obj.get_execution_count()
        if count > 0:
            url = reverse('admin:ansible_manager_ansibleexecution_changelist')
            return format_html('<a href="{}?playbook__id__exact={}">{}</a>', url, obj.id, count)
        return count
    execution_count.short_description = 'Executions'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnsibleInventory)
class AnsibleInventoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'inventory_type', 'sync_with_servers', 'created_by', 'last_sync']
    list_filter = ['inventory_type', 'sync_with_servers', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_sync']
    filter_horizontal = ['server_groups']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'inventory_type']
        }),
        ('Content', {
            'fields': ['content'],
            'classes': ['collapse']
        }),
        ('Dynamic Settings', {
            'fields': ['sync_with_servers', 'server_groups']
        }),
        ('Variables', {
            'fields': ['group_vars', 'host_vars'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at', 'last_sync'],
            'classes': ['collapse']
        })
    ]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnsibleVault)
class AnsibleVaultAdmin(admin.ModelAdmin):
    list_display = ['name', 'vault_id', 'created_by', 'created_at']
    list_filter = ['created_at', 'vault_id']
    search_fields = ['name', 'description', 'vault_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['allowed_users']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'vault_id']
        }),
        ('Content', {
            'fields': ['encrypted_content'],
            'classes': ['collapse']
        }),
        ('Access Control', {
            'fields': ['allowed_users']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnsibleRole)
class AnsibleRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'namespace', 'version', 'source', 'is_installed', 'created_by']
    list_filter = ['source', 'is_installed', 'created_at']
    search_fields = ['name', 'namespace', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'is_installed', 'installation_path']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'namespace', 'version', 'description']
        }),
        ('Source', {
            'fields': ['source', 'source_url']
        }),
        ('Content', {
            'fields': ['tasks_content', 'handlers_content', 'vars_content', 'defaults_content', 'meta_content'],
            'classes': ['collapse']
        }),
        ('Dependencies', {
            'fields': ['dependencies']
        }),
        ('Installation', {
            'fields': ['is_installed', 'installation_path'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnsibleExecution)
class AnsibleExecutionAdmin(admin.ModelAdmin):
    list_display = ['playbook', 'status', 'started_by', 'started_at', 'duration_display', 'hosts_count', 'changed_count', 'failed_count']
    list_filter = ['status', 'started_at', 'playbook__category']
    search_fields = ['playbook__name', 'playbook__display_name', 'started_by__username']
    readonly_fields = ['id', 'started_at', 'finished_at', 'duration_display', 'output', 'error_output', 'return_code']
    
    fieldsets = [
        ('Execution Details', {
            'fields': ['playbook', 'inventory', 'status', 'started_by']
        }),
        ('Parameters', {
            'fields': ['extra_vars', 'limit', 'tags', 'skip_tags']
        }),
        ('Results', {
            'fields': ['return_code', 'hosts_count', 'tasks_count', 'changed_count', 'failed_count']
        }),
        ('Output', {
            'fields': ['output', 'error_output'],
            'classes': ['collapse']
        }),
        ('Timing', {
            'fields': ['started_at', 'finished_at', 'duration_display'],
            'classes': ['collapse']
        }),
        ('System', {
            'fields': ['id', 'process_id'],
            'classes': ['collapse']
        })
    ]
    
    def duration_display(self, obj):
        duration = obj.duration
        if duration:
            return str(duration)
        return '-'
    duration_display.short_description = 'Duration'
    
    def has_add_permission(self, request):
        return False  # Executions are created programmatically


@admin.register(AnsibleSchedule)
class AnsibleScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'playbook', 'frequency', 'is_active', 'next_run', 'last_run', 'created_by']
    list_filter = ['frequency', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'playbook__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_run']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'is_active']
        }),
        ('Execution', {
            'fields': ['playbook', 'inventory']
        }),
        ('Schedule', {
            'fields': ['frequency', 'cron_expression', 'next_run', 'last_run']
        }),
        ('Parameters', {
            'fields': ['extra_vars', 'limit', 'tags', 'skip_tags'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnsibleTemplate)
class AnsibleTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_public', 'usage_count', 'created_by', 'created_at']
    list_filter = ['category', 'is_public', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'usage_count']
    
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'category', 'is_public']
        }),
        ('Template', {
            'fields': ['playbook_template', 'variables_schema']
        }),
        ('Statistics', {
            'fields': ['usage_count']
        }),
        ('Metadata', {
            'fields': ['id', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)