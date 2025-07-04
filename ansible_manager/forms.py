from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import (
    AnsiblePlaybook, AnsibleInventory, AnsibleVault, AnsibleRole,
    AnsibleExecution, AnsibleSchedule, AnsibleTemplate
)
from servers.models import ServerGroup
import yaml
import json
import re


class AnsiblePlaybookForm(forms.ModelForm):
    """Form for creating and editing Ansible playbooks"""
    
    class Meta:
        model = AnsiblePlaybook
        fields = [
            'name', 'display_name', 'description', 'category', 'status',
            'content', 'variables', 'timeout', 'max_parallel', 'tags'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 20, 'class': 'yaml-editor'}),
            'variables': forms.Textarea(attrs={'rows': 5, 'placeholder': 'JSON format: {"key": "value"}'}),
            'tags': forms.TextInput(attrs={'placeholder': 'Comma-separated tags'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data['name']
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            raise ValidationError('Name can only contain alphanumeric characters, hyphens, and underscores.')
        return name
    
    def clean_content(self):
        content = self.cleaned_data['content']
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValidationError(f'Invalid YAML syntax: {e}')
        return content
    
    def clean_variables(self):
        variables = self.cleaned_data['variables']
        if isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except json.JSONDecodeError:
                raise ValidationError('Variables must be valid JSON format.')
        return variables
    
    def clean_tags(self):
        tags = self.cleaned_data['tags']
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
        return tags


class AnsibleInventoryForm(forms.ModelForm):
    """Form for creating and editing Ansible inventories"""
    
    class Meta:
        model = AnsibleInventory
        fields = [
            'name', 'description', 'inventory_type', 'content',
            'sync_with_servers', 'server_groups', 'group_vars', 'host_vars'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 15, 'class': 'inventory-editor'}),
            'server_groups': forms.CheckboxSelectMultiple(),
            'group_vars': forms.Textarea(attrs={'rows': 5, 'placeholder': 'JSON format'}),
            'host_vars': forms.Textarea(attrs={'rows': 5, 'placeholder': 'JSON format'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['server_groups'].queryset = ServerGroup.objects.filter(created_by=user)
    
    def clean_content(self):
        content = self.cleaned_data['content']
        inventory_type = self.cleaned_data.get('inventory_type')
        
        if inventory_type == 'static' and content:
            # Basic validation for INI or YAML format
            try:
                # Try YAML first
                yaml.safe_load(content)
            except yaml.YAMLError:
                # If not YAML, check if it's valid INI format
                if not self._is_valid_ini(content):
                    raise ValidationError('Content must be valid YAML or INI format.')
        return content
    
    def _is_valid_ini(self, content):
        """Basic INI format validation"""
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                continue
            if '=' in line or re.match(r'^[a-zA-Z0-9._-]+$', line):
                continue
            return False
        return True
    
    def clean_group_vars(self):
        return self._clean_json_field('group_vars')
    
    def clean_host_vars(self):
        return self._clean_json_field('host_vars')
    
    def _clean_json_field(self, field_name):
        value = self.cleaned_data[field_name]
        if isinstance(value, str) and value.strip():
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError(f'{field_name.replace("_", " ").title()} must be valid JSON format.')
        return value


class AnsibleVaultForm(forms.ModelForm):
    """Form for creating and editing Ansible vaults"""
    
    vault_password = forms.CharField(
        widget=forms.PasswordInput(),
        help_text='Password for encrypting/decrypting the vault'
    )
    plain_content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10}),
        help_text='Plain text content to be encrypted',
        required=False
    )
    
    class Meta:
        model = AnsibleVault
        fields = ['name', 'description', 'vault_id', 'allowed_users']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'allowed_users': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['allowed_users'].queryset = User.objects.exclude(id=user.id)
    
    def clean(self):
        cleaned_data = super().clean()
        plain_content = cleaned_data.get('plain_content')
        vault_password = cleaned_data.get('vault_password')
        
        if plain_content and not vault_password:
            raise ValidationError('Vault password is required when providing content.')
        
        return cleaned_data


class AnsibleRoleForm(forms.ModelForm):
    """Form for creating and editing Ansible roles"""
    
    class Meta:
        model = AnsibleRole
        fields = [
            'name', 'namespace', 'version', 'description', 'source', 'source_url',
            'tasks_content', 'handlers_content', 'vars_content', 'defaults_content',
            'meta_content', 'dependencies'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tasks_content': forms.Textarea(attrs={'rows': 10, 'class': 'yaml-editor'}),
            'handlers_content': forms.Textarea(attrs={'rows': 5, 'class': 'yaml-editor'}),
            'vars_content': forms.Textarea(attrs={'rows': 5, 'class': 'yaml-editor'}),
            'defaults_content': forms.Textarea(attrs={'rows': 5, 'class': 'yaml-editor'}),
            'meta_content': forms.Textarea(attrs={'rows': 5, 'class': 'yaml-editor'}),
            'dependencies': forms.Textarea(attrs={'rows': 3, 'placeholder': 'JSON array format'}),
        }
    
    def clean_dependencies(self):
        dependencies = self.cleaned_data['dependencies']
        if isinstance(dependencies, str) and dependencies.strip():
            try:
                dependencies = json.loads(dependencies)
                if not isinstance(dependencies, list):
                    raise ValidationError('Dependencies must be a JSON array.')
            except json.JSONDecodeError:
                raise ValidationError('Dependencies must be valid JSON array format.')
        return dependencies
    
    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source')
        source_url = cleaned_data.get('source_url')
        
        if source in ['galaxy', 'git'] and not source_url:
            raise ValidationError('Source URL is required for Galaxy and Git roles.')
        
        # Validate YAML content fields
        yaml_fields = ['tasks_content', 'handlers_content', 'vars_content', 'defaults_content', 'meta_content']
        for field in yaml_fields:
            content = cleaned_data.get(field)
            if content:
                try:
                    yaml.safe_load(content)
                except yaml.YAMLError as e:
                    raise ValidationError(f'Invalid YAML in {field.replace("_", " ")}: {e}')
        
        return cleaned_data


class AnsibleExecutionForm(forms.Form):
    """Form for executing Ansible playbooks"""
    
    playbook = forms.ModelChoiceField(
        queryset=AnsiblePlaybook.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    inventory = forms.ModelChoiceField(
        queryset=AnsibleInventory.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    extra_vars = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'JSON format: {"key": "value"}'}),
        help_text='Additional variables in JSON format'
    )
    limit = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'host1,host2 or group1'}),
        help_text='Limit execution to specific hosts or groups'
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'tag1,tag2'}),
        help_text='Run only tasks with these tags'
    )
    skip_tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'tag1,tag2'}),
        help_text='Skip tasks with these tags'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['playbook'].queryset = AnsiblePlaybook.objects.filter(
                created_by=user, status='active'
            )
            self.fields['inventory'].queryset = AnsibleInventory.objects.filter(
                created_by=user
            )
    
    def clean_extra_vars(self):
        extra_vars = self.cleaned_data['extra_vars']
        if extra_vars:
            try:
                json.loads(extra_vars)
            except json.JSONDecodeError:
                raise ValidationError('Extra variables must be valid JSON format.')
        return extra_vars


class AnsibleScheduleForm(forms.ModelForm):
    """Form for scheduling Ansible playbook executions"""
    
    class Meta:
        model = AnsibleSchedule
        fields = [
            'name', 'description', 'playbook', 'inventory', 'frequency',
            'cron_expression', 'next_run', 'extra_vars', 'limit', 'tags',
            'skip_tags', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'next_run': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'extra_vars': forms.Textarea(attrs={'rows': 3, 'placeholder': 'JSON format'}),
            'cron_expression': forms.TextInput(attrs={'placeholder': '0 2 * * *'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['playbook'].queryset = AnsiblePlaybook.objects.filter(
                created_by=user, status='active'
            )
            self.fields['inventory'].queryset = AnsibleInventory.objects.filter(
                created_by=user
            )
    
    def clean_cron_expression(self):
        frequency = self.cleaned_data.get('frequency')
        cron_expression = self.cleaned_data['cron_expression']
        
        if frequency == 'cron' and not cron_expression:
            raise ValidationError('Cron expression is required when frequency is set to "cron".')
        
        if cron_expression:
            # Basic cron validation (5 fields)
            parts = cron_expression.split()
            if len(parts) != 5:
                raise ValidationError('Cron expression must have 5 fields: minute hour day month weekday')
        
        return cron_expression
    
    def clean_extra_vars(self):
        extra_vars = self.cleaned_data['extra_vars']
        if isinstance(extra_vars, str) and extra_vars.strip():
            try:
                extra_vars = json.loads(extra_vars)
            except json.JSONDecodeError:
                raise ValidationError('Extra variables must be valid JSON format.')
        return extra_vars


class AnsibleTemplateForm(forms.ModelForm):
    """Form for creating and editing Ansible templates"""
    
    class Meta:
        model = AnsibleTemplate
        fields = [
            'name', 'description', 'category', 'is_public',
            'playbook_template', 'variables_schema'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'playbook_template': forms.Textarea(attrs={'rows': 15, 'class': 'template-editor'}),
            'variables_schema': forms.Textarea(attrs={'rows': 10, 'placeholder': 'JSON Schema format'}),
        }
    
    def clean_variables_schema(self):
        schema = self.cleaned_data['variables_schema']
        if isinstance(schema, str) and schema.strip():
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError:
                raise ValidationError('Variables schema must be valid JSON format.')
        return schema


class PlaybookFromTemplateForm(forms.Form):
    """Form for creating playbooks from templates"""
    
    template = forms.ModelChoiceField(
        queryset=AnsibleTemplate.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    name = forms.CharField(
        max_length=200,
        validators=[forms.RegexField(r'^[a-zA-Z0-9_-]+$')],
        help_text='Playbook name (alphanumeric, hyphens, underscores only)'
    )
    display_name = forms.CharField(max_length=200)
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    template_variables = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'JSON format'}),
        help_text='Variables to substitute in the template'
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['template'].queryset = AnsibleTemplate.objects.filter(
                models.Q(created_by=user) | models.Q(is_public=True)
            )
    
    def clean_template_variables(self):
        variables = self.cleaned_data['template_variables']
        if variables:
            try:
                json.loads(variables)
            except json.JSONDecodeError:
                raise ValidationError('Template variables must be valid JSON format.')
        return variables