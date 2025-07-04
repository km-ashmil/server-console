import os
import json
import yaml
import subprocess
import tempfile
import shutil
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from cryptography.fernet import Fernet
import logging
import threading
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class AnsibleRunner:
    """Handles Ansible playbook execution"""
    
    def __init__(self, execution):
        self.execution = execution
        self.process = None
        self.temp_dir = None
        self.playbook_file = None
        self.inventory_file = None
        self.vault_file = None
        
    def run(self):
        """Execute the Ansible playbook"""
        try:
            self.execution.status = 'running'
            self.execution.started_at = timezone.now()
            self.execution.save()
            
            # Create temporary directory for execution
            self.temp_dir = tempfile.mkdtemp(prefix='ansible_exec_')
            
            # Prepare playbook file
            self._prepare_playbook()
            
            # Prepare inventory file
            self._prepare_inventory()
            
            # Prepare vault file if needed
            self._prepare_vault()
            
            # Build ansible-playbook command
            cmd = self._build_command()
            
            # Execute the command
            self._execute_command(cmd)
            
        except Exception as e:
            logger.error(f"Ansible execution failed: {str(e)}")
            self.execution.status = 'failed'
            self.execution.error_message = str(e)
            self.execution.finished_at = timezone.now()
            self.execution.save()
        finally:
            # Cleanup temporary files
            self._cleanup()
    
    def _prepare_playbook(self):
        """Write playbook content to temporary file"""
        self.playbook_file = os.path.join(self.temp_dir, 'playbook.yml')
        with open(self.playbook_file, 'w') as f:
            f.write(self.execution.playbook.content)
    
    def _prepare_inventory(self):
        """Generate and write inventory file"""
        inventory_manager = InventoryManager(self.execution.inventory)
        inventory_content = inventory_manager.generate_inventory()
        
        self.inventory_file = os.path.join(self.temp_dir, 'inventory')
        with open(self.inventory_file, 'w') as f:
            f.write(inventory_content)
    
    def _prepare_vault(self):
        """Prepare vault password file if needed"""
        if hasattr(self.execution.playbook, 'vault') and self.execution.playbook.vault:
            vault_manager = VaultManager()
            vault_password = vault_manager.decrypt_vault_password(self.execution.playbook.vault)
            
            self.vault_file = os.path.join(self.temp_dir, 'vault_pass')
            with open(self.vault_file, 'w') as f:
                f.write(vault_password)
            os.chmod(self.vault_file, 0o600)
    
    def _build_command(self):
        """Build the ansible-playbook command"""
        cmd = [
            'ansible-playbook',
            '-i', self.inventory_file,
            self.playbook_file,
            '--timeout', '30',
            '-v'  # Verbose output
        ]
        
        # Add vault password file if available
        if self.vault_file:
            cmd.extend(['--vault-password-file', self.vault_file])
        
        # Add extra variables
        if self.execution.extra_vars:
            cmd.extend(['--extra-vars', json.dumps(self.execution.extra_vars)])
        
        # Add limit if specified
        if self.execution.limit:
            cmd.extend(['--limit', self.execution.limit])
        
        # Add tags if specified
        if self.execution.tags:
            cmd.extend(['--tags', self.execution.tags])
        
        # Add skip tags if specified
        if self.execution.skip_tags:
            cmd.extend(['--skip-tags', self.execution.skip_tags])
        
        return cmd
    
    def _execute_command(self, cmd):
        """Execute the ansible-playbook command"""
        try:
            # Start the process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=self.temp_dir,
                env=self._get_ansible_env()
            )
            
            # Stream output
            output_lines = []
            for line in iter(self.process.stdout.readline, ''):
                output_lines.append(line)
                
                # Update execution output in real-time
                self.execution.output = ''.join(output_lines)
                self.execution.save(update_fields=['output'])
                
                # Parse Ansible statistics from output
                self._parse_ansible_stats(line)
            
            # Wait for process to complete
            self.process.wait()
            
            # Update final status
            if self.process.returncode == 0:
                self.execution.status = 'success'
            else:
                self.execution.status = 'failed'
            
            self.execution.return_code = self.process.returncode
            self.execution.finished_at = timezone.now()
            self.execution.save()
            
        except subprocess.TimeoutExpired:
            self.execution.status = 'timeout'
            self.execution.finished_at = timezone.now()
            self.execution.save()
            if self.process:
                self.process.kill()
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            self.execution.status = 'failed'
            self.execution.error_message = str(e)
            self.execution.finished_at = timezone.now()
            self.execution.save()
    
    def _parse_ansible_stats(self, line):
        """Parse Ansible statistics from output line"""
        # Parse play recap for statistics
        if 'PLAY RECAP' in line:
            # This is a simplified parser - in production, you'd want more robust parsing
            pass
        
        # Count hosts, tasks, etc. from output
        if 'TASK [' in line:
            self.execution.tasks_count = (self.execution.tasks_count or 0) + 1
        elif 'changed:' in line:
            self.execution.changed_count = (self.execution.changed_count or 0) + 1
        elif 'failed:' in line:
            self.execution.failed_count = (self.execution.failed_count or 0) + 1
        
        self.execution.save(update_fields=['tasks_count', 'changed_count', 'failed_count'])
    
    def _get_ansible_env(self):
        """Get environment variables for Ansible execution"""
        env = os.environ.copy()
        env.update({
            'ANSIBLE_HOST_KEY_CHECKING': 'False',
            'ANSIBLE_STDOUT_CALLBACK': 'json',
            'ANSIBLE_LOAD_CALLBACK_PLUGINS': 'True',
            'ANSIBLE_FORCE_COLOR': 'False',
        })
        return env
    
    def cancel(self):
        """Cancel the running execution"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            # Give it a moment to terminate gracefully
            time.sleep(2)
            if self.process.poll() is None:
                self.process.kill()
    
    def _cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {str(e)}")


class InventoryManager:
    """Manages Ansible inventory generation and synchronization"""
    
    def __init__(self, inventory):
        self.inventory = inventory
    
    def generate_inventory(self):
        """Generate Ansible inventory content"""
        if self.inventory.inventory_type == 'static':
            return self._generate_static_inventory()
        elif self.inventory.inventory_type == 'dynamic':
            return self._generate_dynamic_inventory()
        elif self.inventory.inventory_type == 'serverhub':
            return self._generate_serverhub_inventory()
        else:
            raise ValueError(f"Unsupported inventory type: {self.inventory.inventory_type}")
    
    def _generate_static_inventory(self):
        """Generate static inventory from content"""
        return self.inventory.content
    
    def _generate_dynamic_inventory(self):
        """Generate dynamic inventory from script"""
        # Execute dynamic inventory script
        try:
            result = subprocess.run(
                ['python', '-c', self.inventory.content],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            else:
                raise Exception(f"Dynamic inventory script failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Dynamic inventory script timed out")
    
    def _generate_serverhub_inventory(self):
        """Generate inventory from ServerHub servers"""
        from servers.models import Server  # Import here to avoid circular imports
        
        inventory_data = {
            'all': {
                'hosts': {},
                'children': {}
            }
        }
        
        # Get servers from selected groups
        servers = Server.objects.filter(
            server_group__in=self.inventory.server_groups.all(),
            status='active'
        ).select_related('server_group')
        
        # Group servers by server group
        groups = {}
        for server in servers:
            group_name = server.server_group.name.replace(' ', '_').lower()
            if group_name not in groups:
                groups[group_name] = []
            
            # Add server to group
            host_vars = {
                'ansible_host': server.ip_address,
                'ansible_user': server.username or 'root',
                'server_id': str(server.id),
                'server_name': server.name,
                'server_type': server.server_type,
                'os_type': server.os_type,
            }
            
            # Add SSH key if available
            if server.ssh_key:
                host_vars['ansible_ssh_private_key_file'] = server.ssh_key.key_file.path
            
            groups[group_name].append({
                'name': server.name,
                'vars': host_vars
            })
        
        # Build inventory structure
        for group_name, hosts in groups.items():
            inventory_data['all']['children'][group_name] = {
                'hosts': {}
            }
            
            for host in hosts:
                inventory_data['all']['children'][group_name]['hosts'][host['name']] = host['vars']
        
        # Convert to INI format
        return self._convert_to_ini(inventory_data)
    
    def _convert_to_ini(self, inventory_data):
        """Convert inventory data to INI format"""
        lines = []
        
        # Process groups
        for group_name, group_data in inventory_data['all']['children'].items():
            lines.append(f"[{group_name}]")
            
            # Add hosts
            for host_name, host_vars in group_data['hosts'].items():
                host_line = host_name
                for var_name, var_value in host_vars.items():
                    host_line += f" {var_name}={var_value}"
                lines.append(host_line)
            
            lines.append("")  # Empty line between groups
        
        return "\n".join(lines)
    
    def sync_inventory(self):
        """Synchronize inventory with ServerHub servers"""
        if self.inventory.inventory_type == 'serverhub':
            # Update the inventory content
            new_content = self._generate_serverhub_inventory()
            self.inventory.content = new_content
            self.inventory.last_sync = timezone.now()
            self.inventory.save()
            
            # Clear cache
            cache_key = f"inventory_{self.inventory.id}"
            cache.delete(cache_key)


class VaultManager:
    """Manages Ansible Vault operations"""
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _get_encryption_key(self):
        """Get or generate encryption key for vault passwords"""
        key_file = os.path.join(settings.BASE_DIR, '.vault_key')
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            return key
    
    def encrypt_vault_password(self, password):
        """Encrypt vault password"""
        return self.cipher.encrypt(password.encode()).decode()
    
    def decrypt_vault_password(self, encrypted_password):
        """Decrypt vault password"""
        return self.cipher.decrypt(encrypted_password.encode()).decode()
    
    def encrypt_vault_content(self, content, password):
        """Encrypt content using Ansible Vault format"""
        # This is a simplified implementation
        # In production, you'd use ansible-vault command or python-ansible-vault library
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as vault_pass_file:
                vault_pass_file.write(password)
                vault_pass_path = vault_pass_file.name
            
            # Use ansible-vault to encrypt
            result = subprocess.run([
                'ansible-vault', 'encrypt',
                '--vault-password-file', vault_pass_path,
                temp_file_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                with open(temp_file_path, 'r') as f:
                    encrypted_content = f.read()
                return encrypted_content
            else:
                raise Exception(f"Vault encryption failed: {result.stderr}")
        
        finally:
            # Cleanup
            for path in [temp_file_path, vault_pass_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def decrypt_vault_content(self, encrypted_content, password):
        """Decrypt Ansible Vault content"""
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yml') as temp_file:
                temp_file.write(encrypted_content)
                temp_file_path = temp_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as vault_pass_file:
                vault_pass_file.write(password)
                vault_pass_path = vault_pass_file.name
            
            # Use ansible-vault to decrypt
            result = subprocess.run([
                'ansible-vault', 'decrypt',
                '--vault-password-file', vault_pass_path,
                temp_file_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                with open(temp_file_path, 'r') as f:
                    decrypted_content = f.read()
                return decrypted_content
            else:
                raise Exception(f"Vault decryption failed: {result.stderr}")
        
        finally:
            # Cleanup
            for path in [temp_file_path, vault_pass_path]:
                if os.path.exists(path):
                    os.unlink(path)


class AnsibleValidator:
    """Validates Ansible content (playbooks, inventories, etc.)"""
    
    @staticmethod
    def validate_yaml(content):
        """Validate YAML syntax"""
        try:
            yaml.safe_load(content)
            return True, None
        except yaml.YAMLError as e:
            return False, str(e)
    
    @staticmethod
    def validate_json(content):
        """Validate JSON syntax"""
        try:
            json.loads(content)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)
    
    @staticmethod
    def validate_playbook(content):
        """Validate Ansible playbook structure"""
        is_valid, error = AnsibleValidator.validate_yaml(content)
        if not is_valid:
            return False, error
        
        try:
            data = yaml.safe_load(content)
            
            # Check if it's a list (playbook format)
            if not isinstance(data, list):
                return False, "Playbook must be a list of plays"
            
            # Check each play
            for i, play in enumerate(data):
                if not isinstance(play, dict):
                    return False, f"Play {i+1} must be a dictionary"
                
                # Check required fields
                if 'hosts' not in play:
                    return False, f"Play {i+1} must have 'hosts' field"
                
                if 'tasks' not in play and 'roles' not in play:
                    return False, f"Play {i+1} must have either 'tasks' or 'roles' field"
            
            return True, None
        
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def validate_inventory(content, inventory_type='static'):
        """Validate Ansible inventory"""
        if inventory_type == 'static':
            # Basic INI format validation
            lines = content.strip().split('\n')
            current_group = None
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Group header
                if line.startswith('[') and line.endswith(']'):
                    current_group = line[1:-1]
                    continue
                
                # Host entry
                if current_group:
                    # Basic validation - should contain hostname
                    if not line.split()[0]:
                        return False, f"Invalid host entry at line {line_num}"
            
            return True, None
        
        elif inventory_type == 'dynamic':
            # Validate Python script
            try:
                compile(content, '<string>', 'exec')
                return True, None
            except SyntaxError as e:
                return False, f"Python syntax error: {str(e)}"
        
        return True, None


class AnsibleScheduler:
    """Handles scheduled Ansible executions"""
    
    @staticmethod
    def schedule_execution(schedule):
        """Schedule an Ansible execution"""
        from .models import AnsibleExecution
        
        # Create execution record
        execution = AnsibleExecution.objects.create(
            playbook=schedule.playbook,
            inventory=schedule.inventory,
            started_by=schedule.created_by,
            extra_vars=schedule.extra_vars,
            limit=schedule.limit,
            tags=schedule.tags,
            skip_tags=schedule.skip_tags,
            is_scheduled=True,
            schedule=schedule
        )
        
        # Start execution in background
        runner = AnsibleRunner(execution)
        thread = threading.Thread(target=runner.run)
        thread.daemon = True
        thread.start()
        
        # Update schedule's next run time
        schedule.update_next_run()
        
        return execution


class AnsibleMetrics:
    """Collects and manages Ansible execution metrics"""
    
    @staticmethod
    def get_execution_metrics(user=None, days=30):
        """Get execution metrics for dashboard"""
        from .models import AnsibleExecution
        from django.db.models import Count, Avg, Q
        from datetime import timedelta
        
        # Base queryset
        queryset = AnsibleExecution.objects.all()
        if user:
            queryset = queryset.filter(started_by=user)
        
        # Filter by date range
        since_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(started_at__gte=since_date)
        
        # Calculate metrics
        metrics = queryset.aggregate(
            total_executions=Count('id'),
            successful_executions=Count('id', filter=Q(status='success')),
            failed_executions=Count('id', filter=Q(status='failed')),
            avg_duration=Avg('duration'),
        )
        
        # Calculate success rate
        if metrics['total_executions'] > 0:
            metrics['success_rate'] = (metrics['successful_executions'] / metrics['total_executions']) * 100
        else:
            metrics['success_rate'] = 0
        
        return metrics
    
    @staticmethod
    def get_playbook_usage_stats(user=None):
        """Get playbook usage statistics"""
        from .models import AnsiblePlaybook, AnsibleExecution
        from django.db.models import Count
        
        # Base queryset
        queryset = AnsiblePlaybook.objects.all()
        if user:
            queryset = queryset.filter(created_by=user)
        
        # Get usage stats
        stats = queryset.annotate(
            execution_count=Count('executions')
        ).order_by('-execution_count')[:10]
        
        return stats