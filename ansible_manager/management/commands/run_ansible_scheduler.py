from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from ansible_manager.models import AnsibleSchedule
from ansible_manager.utils import AnsibleScheduler
from ansible_manager.signals import schedule_triggered
import time
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run Ansible scheduler to execute scheduled playbooks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Check interval in seconds (default: 60)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit (default: run continuously)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be executed without actually running'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Ansible scheduler (interval: {interval}s, once: {run_once}, dry-run: {dry_run})"
            )
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No executions will be started"))
        
        try:
            while True:
                self.check_and_run_schedules(dry_run)
                
                if run_once:
                    break
                
                self.stdout.write(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Scheduler stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Scheduler error: {str(e)}"))
            logger.error(f"Ansible scheduler error: {str(e)}", exc_info=True)
    
    def check_and_run_schedules(self, dry_run=False):
        """Check for schedules that need to run and execute them"""
        now = timezone.now()
        
        # Get schedules that are due to run
        due_schedules = AnsibleSchedule.objects.filter(
            is_active=True,
            next_run__lte=now
        ).select_related('playbook', 'inventory', 'created_by')
        
        if not due_schedules.exists():
            self.stdout.write("No schedules due to run")
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {due_schedules.count()} schedule(s) due to run")
        )
        
        for schedule in due_schedules:
            try:
                with transaction.atomic():
                    # Double-check the schedule is still due (avoid race conditions)
                    schedule.refresh_from_db()
                    if not schedule.is_active or schedule.next_run > now:
                        continue
                    
                    self.stdout.write(
                        f"Processing schedule: {schedule.name} (playbook: {schedule.playbook.name})"
                    )
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(f"DRY RUN: Would execute {schedule.name}")
                        )
                        # Still update next run time in dry run mode
                        schedule.update_next_run()
                        continue
                    
                    # Check if playbook and inventory are still valid
                    if schedule.playbook.status != 'active':
                        self.stdout.write(
                            self.style.ERROR(
                                f"Skipping schedule {schedule.name}: playbook is not active"
                            )
                        )
                        schedule.last_run = now
                        schedule.last_status = 'failed'
                        schedule.error_message = 'Playbook is not active'
                        schedule.save()
                        continue
                    
                    # Send signal to trigger execution
                    schedule_triggered.send(
                        sender=self.__class__,
                        schedule=schedule
                    )
                    
                    # Update schedule status
                    schedule.last_run = now
                    schedule.last_status = 'started'
                    schedule.error_message = ''
                    schedule.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"Started execution for schedule: {schedule.name}")
                    )
            
            except Exception as e:
                error_msg = f"Failed to process schedule {schedule.name}: {str(e)}"
                self.stdout.write(self.style.ERROR(error_msg))
                logger.error(error_msg, exc_info=True)
                
                # Update schedule with error
                try:
                    schedule.last_run = now
                    schedule.last_status = 'failed'
                    schedule.error_message = str(e)
                    schedule.save()
                except Exception as save_error:
                    logger.error(f"Failed to save schedule error: {str(save_error)}")
    
    def cleanup_old_schedules(self):
        """Clean up old schedule records"""
        # Disable schedules that haven't run in a long time and have errors
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_failed_schedules = AnsibleSchedule.objects.filter(
            is_active=True,
            last_run__lt=cutoff_date,
            last_status='failed'
        )
        
        if old_failed_schedules.exists():
            count = old_failed_schedules.count()
            old_failed_schedules.update(is_active=False)
            self.stdout.write(
                self.style.WARNING(f"Disabled {count} old failed schedules")
            )
            logger.info(f"Disabled {count} old failed schedules")