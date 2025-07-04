from django.apps import AppConfig


class AnsibleManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ansible_manager'
    verbose_name = 'Ansible Manager'
    
    def ready(self):
        """Initialize app when Django starts"""
        import ansible_manager.signals