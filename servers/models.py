from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os

class ServerGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Server(models.Model):
    AUTH_METHODS = [
        ('password', 'Password'),
        ('key', 'SSH Key'),
        ('key_password', 'SSH Key with Password'),
    ]
    
    STATUS_CHOICES = [
        ('unknown', 'Unknown'),
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ]

    name = models.CharField(max_length=100)
    hostname = models.CharField(max_length=255)
    port = models.PositiveIntegerField(
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    username = models.CharField(max_length=100)
    auth_method = models.CharField(max_length=20, choices=AUTH_METHODS, default='password')
    
    # Encrypted fields
    encrypted_password = models.TextField(blank=True)
    encrypted_private_key = models.TextField(blank=True)
    encrypted_key_password = models.TextField(blank=True)
    
    # Server details
    description = models.TextField(blank=True)
    group = models.ForeignKey(ServerGroup, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text='Comma-separated tags')
    
    # Status and monitoring
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    last_checked = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Connection settings
    timeout = models.PositiveIntegerField(default=30, help_text='Connection timeout in seconds')
    keep_alive = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['hostname', 'port', 'username']

    def __str__(self):
        return f"{self.name} ({self.hostname}:{self.port})"

    def get_encryption_key(self):
        """Get or create encryption key for this server"""
        key_file = os.path.join(settings.BASE_DIR, '.server_key')
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key

    def encrypt_data(self, data):
        """Encrypt sensitive data"""
        if not data:
            return ''
        key = self.get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()

    def decrypt_data(self, encrypted_data):
        """Decrypt sensitive data"""
        if not encrypted_data:
            return ''
        try:
            key = self.get_encryption_key()
            f = Fernet(key)
            decoded_data = base64.b64decode(encrypted_data.encode())
            return f.decrypt(decoded_data).decode()
        except Exception:
            return ''

    def set_password(self, password):
        """Set encrypted password"""
        self.encrypted_password = self.encrypt_data(password)

    def get_password(self):
        """Get decrypted password"""
        return self.decrypt_data(self.encrypted_password)

    def set_private_key(self, private_key):
        """Set encrypted private key"""
        self.encrypted_private_key = self.encrypt_data(private_key)

    def get_private_key(self):
        """Get decrypted private key"""
        return self.decrypt_data(self.encrypted_private_key)

    def set_key_password(self, key_password):
        """Set encrypted key password"""
        self.encrypted_key_password = self.encrypt_data(key_password)

    def get_key_password(self):
        """Get decrypted key password"""
        return self.decrypt_data(self.encrypted_key_password)

    def get_tags_list(self):
        """Get tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def set_tags_list(self, tags_list):
        """Set tags from a list"""
        self.tags = ', '.join(tags_list)

class ServerConnection(models.Model):
    """Track active connections to servers"""
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100, unique=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-connected_at']

    def __str__(self):
        return f"{self.user.username} -> {self.server.name} ({self.session_id})"

class ServerLog(models.Model):
    """Log server activities and commands"""
    LOG_TYPES = [
        ('connection', 'Connection'),
        ('command', 'Command'),
        ('error', 'Error'),
        ('status', 'Status Change'),
    ]
    
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['server', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.server.name} - {self.log_type} - {self.timestamp}"