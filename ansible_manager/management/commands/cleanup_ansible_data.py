from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from ansible_manager.models import AnsibleExecution, AnsiblePlaybook, AnsibleInventory
from datetime import timedelta
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old Ansible execution data and temporary files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete executions older than this many days (default: 30)'
        )
        parser.add_argument(
            '--keep-successful',
            action='store_true',
            help='Keep successful executions, only delete failed ones'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--cleanup-temp',
            action='store_true',
            help='Clean up temporary Ansible files'
        )
        parser.add_argument(
            '--cleanup-logs',
            action='store_true',
            help='Clean up old execution logs'
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Perform database vacuum operations'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        keep_successful = options['keep_successful']
        dry_run = options['dry_run']
        cleanup_temp = options['cleanup_temp']
        cleanup_logs = options['cleanup_logs']
        vacuum = options['vacuum']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Ansible data cleanup (days: {days}, dry-run: {dry_run})"
            )
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be deleted"))
        
        # Clean up old executions
        self.cleanup_old_executions(days, keep_successful, dry_run)
        
        # Clean up temporary files
        if cleanup_temp:
            self.cleanup_temp_files(dry_run)
        
        # Clean up old logs
        if cleanup_logs:
            self.cleanup_old_logs(days, dry_run)
        
        # Vacuum database
        if vacuum:
            self.vacuum_database(dry_run)
        
        # Update statistics
        self.update_statistics(dry_run)
        
        self.stdout.write(self.style.SUCCESS("Cleanup completed"))
    
    def cleanup_old_executions(self, days, keep_successful, dry_run):
        """Clean up old execution records"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Build queryset
        queryset = AnsibleExecution.objects.filter(
            started_at__lt=cutoff_date
        )
        
        if keep_successful:
            queryset = queryset.exclude(status='success')
        
        # Get count before deletion
        count = queryset.count()
        
        if count == 0:
            self.stdout.write("No old executions to clean up")
            return
        
        self.stdout.write(f"Found {count} old execution(s) to delete")
        
        if not dry_run:
            # Delete in batches to avoid memory issues
            batch_size = 100
            deleted_total = 0
            
            while True:
                batch_ids = list(queryset.values_list('id', flat=True)[:batch_size])
                if not batch_ids:
                    break
                
                batch_queryset = AnsibleExecution.objects.filter(id__in=batch_ids)
                deleted_count = batch_queryset.count()
                batch_queryset.delete()
                
                deleted_total += deleted_count
                self.stdout.write(f"Deleted {deleted_total}/{count} executions")
            
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted_total} old execution records")
            )
            logger.info(f"Cleaned up {deleted_total} old Ansible execution records")
        else:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would delete {count} execution records")
            )
    
    def cleanup_temp_files(self, dry_run):
        """Clean up temporary Ansible files"""
        temp_dir = '/tmp' if os.name != 'nt' else os.environ.get('TEMP', 'C:\\temp')
        ansible_temp_pattern = 'ansible_exec_'
        
        if not os.path.exists(temp_dir):
            self.stdout.write(f"Temp directory {temp_dir} does not exist")
            return
        
        cleaned_count = 0
        cleaned_size = 0
        
        try:
            for item in os.listdir(temp_dir):
                if item.startswith(ansible_temp_pattern):
                    item_path = os.path.join(temp_dir, item)
                    
                    if os.path.isdir(item_path):
                        # Check if directory is old (more than 1 day)
                        try:
                            stat = os.stat(item_path)
                            age = timezone.now().timestamp() - stat.st_mtime
                            
                            if age > 86400:  # 1 day in seconds
                                # Calculate size before deletion
                                size = self.get_directory_size(item_path)
                                
                                if not dry_run:
                                    shutil.rmtree(item_path)
                                    cleaned_size += size
                                
                                cleaned_count += 1
                                self.stdout.write(f"Cleaned temp directory: {item}")
                        
                        except (OSError, IOError) as e:
                            self.stdout.write(
                                self.style.WARNING(f"Could not clean {item}: {str(e)}")
                            )
        
        except (OSError, IOError) as e:
            self.stdout.write(
                self.style.ERROR(f"Error accessing temp directory: {str(e)}")
            )
            return
        
        if cleaned_count > 0:
            size_mb = cleaned_size / (1024 * 1024)
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cleaned {cleaned_count} temp directories ({size_mb:.2f} MB)"
                    )
                )
                logger.info(f"Cleaned up {cleaned_count} Ansible temp directories")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN: Would clean {cleaned_count} temp directories ({size_mb:.2f} MB)"
                    )
                )
        else:
            self.stdout.write("No temp directories to clean")
    
    def cleanup_old_logs(self, days, dry_run):
        """Clean up old execution logs"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clear output from old executions to save space
        old_executions = AnsibleExecution.objects.filter(
            started_at__lt=cutoff_date,
            output__isnull=False
        ).exclude(output='')
        
        count = old_executions.count()
        
        if count == 0:
            self.stdout.write("No old logs to clean up")
            return
        
        if not dry_run:
            # Calculate total size before clearing
            total_size = sum(
                len(execution.output.encode('utf-8')) 
                for execution in old_executions.iterator()
                if execution.output
            )
            
            # Clear the output field
            old_executions.update(output='')
            
            size_mb = total_size / (1024 * 1024)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleared logs from {count} executions ({size_mb:.2f} MB)"
                )
            )
            logger.info(f"Cleared logs from {count} old Ansible executions")
        else:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would clear logs from {count} executions")
            )
    
    def vacuum_database(self, dry_run):
        """Perform database vacuum operations"""
        from django.db import connection
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: Would perform database vacuum")
            )
            return
        
        try:
            with connection.cursor() as cursor:
                # This is database-specific - adjust for your database
                if connection.vendor == 'postgresql':
                    cursor.execute("VACUUM ANALYZE;")
                elif connection.vendor == 'sqlite':
                    cursor.execute("VACUUM;")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Vacuum not supported for {connection.vendor}"
                        )
                    )
                    return
            
            self.stdout.write(self.style.SUCCESS("Database vacuum completed"))
            logger.info("Performed database vacuum for Ansible data")
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Database vacuum failed: {str(e)}")
            )
            logger.error(f"Database vacuum failed: {str(e)}")
    
    def update_statistics(self, dry_run):
        """Update various statistics after cleanup"""
        if dry_run:
            return
        
        # Update playbook statistics
        playbooks = AnsiblePlaybook.objects.all()
        for playbook in playbooks:
            execution_count = playbook.executions.count()
            last_execution = playbook.executions.order_by('-started_at').first()
            
            update_fields = []
            if last_execution:
                playbook.last_execution = last_execution.started_at
                update_fields.append('last_execution')
            
            if update_fields:
                playbook.save(update_fields=update_fields)
        
        self.stdout.write("Updated playbook statistics")
    
    def get_directory_size(self, path):
        """Calculate total size of directory"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, IOError):
                        pass
        except (OSError, IOError):
            pass
        return total_size