from django import forms
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import Field, InlineRadios
from .models import Server, ServerGroup

class ServerGroupForm(forms.ModelForm):
    class Meta:
        model = ServerGroup
        fields = ['name', 'description', 'color']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-8 mb-0'),
                Column('color', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            'description',
            Submit('submit', 'Save Group', css_class='btn btn-primary')
        )

class ServerForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Leave blank to keep existing password'
    )
    private_key = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 8, 'class': 'form-control', 'placeholder': 'Paste your private key here...'}),
        required=False,
        help_text='SSH private key content'
    )
    key_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Password for encrypted private key (if any)'
    )
    tags_input = forms.CharField(
        required=False,
        help_text='Enter tags separated by commas',
        widget=forms.TextInput(attrs={'placeholder': 'web, production, database'})
    )

    class Meta:
        model = Server
        fields = [
            'name', 'hostname', 'port', 'username', 'auth_method',
            'description', 'group', 'timeout', 'keep_alive'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'port': forms.NumberInput(attrs={'min': 1, 'max': 65535}),
            'timeout': forms.NumberInput(attrs={'min': 5, 'max': 300}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial tags
        if self.instance.pk:
            self.fields['tags_input'].initial = ', '.join(self.instance.get_tags_list())
        
        # Filter groups by user
        if self.user:
            self.fields['group'].queryset = ServerGroup.objects.filter(created_by=self.user)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Basic Information',
                Row(
                    Column('name', css_class='form-group col-md-6 mb-0'),
                    Column('group', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
                'description',
                'tags_input'
            ),
            Fieldset(
                'Connection Details',
                Row(
                    Column('hostname', css_class='form-group col-md-8 mb-0'),
                    Column('port', css_class='form-group col-md-4 mb-0'),
                    css_class='form-row'
                ),
                Row(
                    Column('username', css_class='form-group col-md-6 mb-0'),
                    Column('auth_method', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
                Row(
                    Column('timeout', css_class='form-group col-md-6 mb-0'),
                    Column('keep_alive', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                )
            ),
            Fieldset(
                'Authentication',
                HTML('<div id="password-auth" style="display: none;">'),
                'password',
                HTML('</div>'),
                HTML('<div id="key-auth" style="display: none;">'),
                'private_key',
                'key_password',
                HTML('</div>'),
                css_id='auth-section'
            ),
            Submit('submit', 'Save Server', css_class='btn btn-primary')
        )

    def clean(self):
        cleaned_data = super().clean()
        auth_method = cleaned_data.get('auth_method')
        password = cleaned_data.get('password')
        private_key = cleaned_data.get('private_key')
        
        if auth_method == 'password':
            if not password and not self.instance.pk:
                raise forms.ValidationError('Password is required for password authentication.')
        elif auth_method in ['key', 'key_password']:
            if not private_key and not self.instance.pk:
                raise forms.ValidationError('Private key is required for key authentication.')
        
        return cleaned_data

    def save(self, commit=True):
        server = super().save(commit=False)
        
        if self.user:
            server.created_by = self.user
        
        # Handle authentication data
        password = self.cleaned_data.get('password')
        private_key = self.cleaned_data.get('private_key')
        key_password = self.cleaned_data.get('key_password')
        
        if password:
            server.set_password(password)
        if private_key:
            server.set_private_key(private_key)
        if key_password:
            server.set_key_password(key_password)
        
        # Handle tags
        tags_input = self.cleaned_data.get('tags_input', '')
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            server.set_tags_list(tags_list)
        
        if commit:
            server.save()
        
        return server

class ServerTestForm(forms.Form):
    """Form for testing server connection"""
    test_command = forms.CharField(
        initial='whoami && pwd',
        help_text='Command to test the connection',
        widget=forms.TextInput(attrs={'placeholder': 'whoami && pwd'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'test_command',
            Submit('test', 'Test Connection', css_class='btn btn-success')
        )

class ServerSearchForm(forms.Form):
    """Form for searching and filtering servers"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search servers...',
            'class': 'form-control'
        })
    )
    group = forms.ModelChoiceField(
        queryset=ServerGroup.objects.none(),
        required=False,
        empty_label='All Groups',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Server.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Filter by tags...',
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['group'].queryset = ServerGroup.objects.filter(created_by=user)