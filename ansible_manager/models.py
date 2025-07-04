from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator
from servers.models import Server, ServerGroup
import json
import uuid


class AnsiblePlaybook(models.Model):
    """Ansible Playbook model for storing and managing playbooks"""
    
    CATEGORY_CHOICES = [
        ('deployment', 'Deployment'),
        ('configuration', 'Configuration'),
        ('maintenance', 'Maintenance'),
        ('security', 'Security'),
        ('monitoring', 'Monitoring'),
        ('backup', 'Backup'),
        ('custom', 'Custom'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, validators=[
        RegexValidator(r'^[a-zA-Z0-9_-]+$', 'Only alphanumeric characters, hyphens, and underscores allowed.')
    ])
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='custom')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Playbook content
    content = models.TextField(help_text='YAML content of the playbook')
    variables = models.JSONField(default=dict, blank=True, help_text='Default variables for the playbook')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_playbooks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)
    
    # Execution settings
    timeout = models.PositiveIntegerField(default=3600, help_text='Timeout in seconds')
    max_parallel = models.PositiveIntegerField(default=5, help_text='Maximum parallel executions')
    
    # Tags and organization
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        db_table = 'ansible_playbooks'
        indexes = [
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['name', 'created_by']
    
    def __str__(self):
        return f"{self.display_name} (v{self.version})"
    
    def get_execution_count(self):
        return self.executions.count()
    
    def get_last_execution(self):
        return self.executions.order_by('-started_at').first()


class AnsibleInventory(models.Model):
    """Ansible Inventory management"""
    
    TYPE_CHOICES = [
        ('static', 'Static'),
        ('dynamic', 'Dynamic'),
        ('hybrid', 'Hybrid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    inventory_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='dynamic')
    
    # Inventory content
    content = models.TextField(blank=True, help_text='Static inventory content in INI or YAML format')
    
    # Dynamic inventory settings
    sync_with_servers = models.BooleanField(default=True, help_text='Automatically sync with ServerHub servers')
    server_groups = models.ManyToManyField(ServerGroup, blank=True, related_name='ansible_inventories')
    
    # Variables
    group_vars = models.JSONField(default=dict, blank=True)
    host_vars = models.JSONField(default=dict, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_inventories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'ansible_inventories'
        indexes = [
            models.Index(fields=['created_by', 'inventory_type']),
            models.Index(fields=['last_sync']),
        ]
        verbose_name_plural = 'Ansible Inventories'
    
    def __str__(self):
        return self.name
    
    def sync_inventory(self):
        """Sync inventory with ServerHub servers"""
        if self.sync_with_servers:
            # Implementation for syncing with servers
            self.last_sync = timezone.now()
            self.save()


class AnsibleVault(models.Model):
    """Ansible Vault for secure storage of sensitive data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Encrypted content
    encrypted_content = models.TextField(help_text='Ansible vault encrypted content')
    vault_id = models.CharField(max_length=100, blank=True, help_text='Vault ID for multiple vault files')
    
    # Access control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_vaults')
    allowed_users = models.ManyToManyField(User, blank=True, related_name='accessible_vaults')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ansible_vaults'
        indexes = [
            models.Index(fields=['created_by']),
            models.Index(fields=['vault_id']),
        ]
    
    def __str__(self):
        return self.name


class AnsibleRole(models.Model):
    """Ansible Role management"""
    
    SOURCE_CHOICES = [
        ('local', 'Local'),
        ('galaxy', 'Ansible Galaxy'),
        ('git', 'Git Repository'),
        ('custom', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    namespace = models.CharField(max_length=100, blank=True)
    version = models.CharField(max_length=50, default='latest')
    description = models.TextField(blank=True)
    
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='local')
    source_url = models.URLField(blank=True, help_text='URL for Galaxy or Git roles')
    
    # Role content (for local roles)
    tasks_content = models.TextField(blank=True)
    handlers_content = models.TextField(blank=True)
    vars_content = models.TextField(blank=True)
    defaults_content = models.TextField(blank=True)
    meta_content = models.TextField(blank=True)
    
    # Dependencies
    dependencies = models.JSONField(default=list, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_roles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Installation status
    is_installed = models.BooleanField(default=False)
    installation_path = models.CharField(max_length=500, blank=True)
    
    class Meta:
        db_table = 'ansible_roles'
        indexes = [
            models.Index(fields=['created_by', 'source']),
            models.Index(fields=['namespace', 'name']),
        ]
        unique_together = ['namespace', 'name', 'created_by']
    
    def __str__(self):
        if self.namespace:
            return f"{self.namespace}.{self.name}"
        return self.name


class AnsibleExecution(models.Model):
    """Track Ansible playbook executions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('timeout', 'Timeout'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    playbook = models.ForeignKey(AnsiblePlaybook, on_delete=models.CASCADE, related_name='executions')
    inventory = models.ForeignKey(AnsibleInventory, on_delete=models.CASCADE, related_name='executions')
    
    # Execution details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_executions')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Execution parameters
    extra_vars = models.JSONField(default=dict, blank=True)
    limit = models.CharField(max_length=500, blank=True, help_text='Limit execution to specific hosts')
    tags = models.CharField(max_length=500, blank=True, help_text='Run only tasks with these tags')
    skip_tags = models.CharField(max_length=500, blank=True, help_text='Skip tasks with these tags')
    
    # Results
    output = models.TextField(blank=True)
    error_output = models.TextField(blank=True)
    return_code = models.IntegerField(null=True, blank=True)
    
    # Statistics
    hosts_count = models.PositiveIntegerField(default=0)
    tasks_count = models.PositiveIntegerField(default=0)
    changed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    
    # Process information
    process_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'ansible_executions'
        indexes = [
            models.Index(fields=['playbook', 'status']),
            models.Index(fields=['started_by', 'started_at']),
            models.Index(fields=['status', 'started_at']),
        ]
    
    def __str__(self):
        return f"{self.playbook.name} - {self.status} ({self.started_at})"
    
    @property
    def duration(self):
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return None
    
    def is_running(self):
        return self.status in ['pending', 'running']


class AnsibleSchedule(models.Model):
    """Schedule Ansible playbook executions"""
    
    FREQUENCY_CHOICES = [
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('cron', 'Cron Expression'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    playbook = models.ForeignKey(AnsiblePlaybook, on_delete=models.CASCADE, related_name='schedules')
    inventory = models.ForeignKey(AnsibleInventory, on_delete=models.CASCADE, related_name='schedules')
    
    # Schedule settings
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    cron_expression = models.CharField(max_length=100, blank=True, help_text='Cron expression for custom scheduling')
    next_run = models.DateTimeField()
    
    # Execution parameters
    extra_vars = models.JSONField(default=dict, blank=True)
    limit = models.CharField(max_length=500, blank=True)
    tags = models.CharField(max_length=500, blank=True)
    skip_tags = models.CharField(max_length=500, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_schedules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ansible_schedules'
        indexes = [
            models.Index(fields=['is_active', 'next_run']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.frequency}"


class AnsibleTemplate(models.Model):
    """Predefined Ansible playbook templates"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=AnsiblePlaybook.CATEGORY_CHOICES)
    
    # Template content
    playbook_template = models.TextField(help_text='Jinja2 template for playbook content')
    variables_schema = models.JSONField(default=dict, help_text='JSON schema for template variables')
    
    # Metadata
    is_public = models.BooleanField(default=False, help_text='Available to all users')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ansible_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Usage statistics
    usage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'ansible_templates'
        indexes = [
            models.Index(fields=['category', 'is_public']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return self.name