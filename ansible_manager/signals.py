from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import (
    AnsiblePlaybook, AnsibleInventory, AnsibleVault, AnsibleRole,
    AnsibleExecution, AnsibleSchedule, AnsibleTemplate
)
from .utils import AnsibleScheduler
import logging
import os

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AnsiblePlaybook)
def playbook_post_save(sender, instance, created, **kwargs):
    """Handle playbook creation and updates"""
    if created:
        logger.info(f"New playbook created: {instance.name} by {instance.created_by}")
        
        # Validate playbook content
        from .utils import AnsibleValidator
        is_valid, error = AnsibleValidator.validate_playbook(instance.content)
        if not is_valid:
            instance.status = 'invalid'
            instance.save(update_fields=['status'])
            logger.warning(f"Playbook {instance.name} marked as invalid: {error}")
        else:
            instance.status = 'active'
            instance.save(update_fields=['status'])
    else:
        # Increment version on update
        if not kwargs.get('update_fields') or 'version' not in kwargs.get('update_fields', []):
            instance.version += 1
            instance.save(update_fields=['version'])
        
        logger.info(f"Playbook updated: {instance.name} (version {instance.version})")
    
    # Clear related caches
    cache_keys = [
        f"playbook_{instance.id}",
        f"user_playbooks_{instance.created_by.id}",
        "ansible_dashboard_stats"
    ]
    cache.delete_many(cache_keys)


@receiver(post_save, sender=AnsibleInventory)
def inventory_post_save(sender, instance, created, **kwargs):
    """Handle inventory creation and updates"""
    if created:
        logger.info(f"New inventory created: {instance.name} by {instance.created_by}")
        
        # Validate inventory content
        from .utils import AnsibleValidator
        is_valid, error = AnsibleValidator.validate_inventory(instance.content, instance.inventory_type)
        if not is_valid:
            logger.warning(f"Inventory {instance.name} validation failed: {error}")
    else:
        logger.info(f"Inventory updated: {instance.name}")
    
    # Clear inventory cache
    cache_key = f"inventory_{instance.id}"
    cache.delete(cache_key)
    
    # If this is a ServerHub inventory, trigger sync
    if instance.inventory_type == 'serverhub' and created:
        try:
            from .utils import InventoryManager
            inventory_manager = InventoryManager(instance)
            inventory_manager.sync_inventory()
            logger.info(f"ServerHub inventory {instance.name} synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync ServerHub inventory {instance.name}: {str(e)}")


@receiver(post_save, sender=AnsibleVault)
def vault_post_save(sender, instance, created, **kwargs):
    """Handle vault creation and updates"""
    if created:
        logger.info(f"New vault created: {instance.name} by {instance.created_by}")
        
        # Encrypt vault password if not already encrypted
        if instance.vault_password and not instance.vault_password.startswith('$ANSIBLE_VAULT'):
            from .utils import VaultManager
            vault_manager = VaultManager()
            encrypted_password = vault_manager.encrypt_vault_password(instance.vault_password)
            instance.vault_password = encrypted_password
            instance.save(update_fields=['vault_password'])
    else:
        logger.info(f"Vault updated: {instance.name}")


@receiver(post_save, sender=AnsibleRole)
def role_post_save(sender, instance, created, **kwargs):
    """Handle role creation and updates"""
    if created:
        logger.info(f"New role created: {instance.name} by {instance.created_by}")
        
        # Validate role structure
        from .utils import AnsibleValidator
        if instance.tasks_content:
            is_valid, error = AnsibleValidator.validate_yaml(instance.tasks_content)
            if not is_valid:
                logger.warning(f"Role {instance.name} tasks validation failed: {error}")
        
        if instance.vars_content:
            is_valid, error = AnsibleValidator.validate_yaml(instance.vars_content)
            if not is_valid:
                logger.warning(f"Role {instance.name} vars validation failed: {error}")
    else:
        logger.info(f"Role updated: {instance.name}")


@receiver(post_save, sender=AnsibleExecution)
def execution_post_save(sender, instance, created, **kwargs):
    """Handle execution creation and updates"""
    if created:
        logger.info(f"New execution started: {instance.id} for playbook {instance.playbook.name}")
        
        # Send notification to user (if notification system exists)
        # This could integrate with your existing notification system
        pass
    else:
        # Log status changes
        if instance.status in ['success', 'failed', 'cancelled']:
            duration = None
            if instance.finished_at and instance.started_at:
                duration = (instance.finished_at - instance.started_at).total_seconds()
                instance.duration = duration
                instance.save(update_fields=['duration'])
            
            logger.info(
                f"Execution {instance.id} finished with status: {instance.status} "
                f"(duration: {duration}s)"
            )
            
            # Update playbook last execution time
            instance.playbook.last_execution = instance.finished_at
            instance.playbook.save(update_fields=['last_execution'])
    
    # Clear dashboard cache
    cache.delete("ansible_dashboard_stats")


@receiver(post_save, sender=AnsibleSchedule)
def schedule_post_save(sender, instance, created, **kwargs):
    """Handle schedule creation and updates"""
    if created:
        logger.info(f"New schedule created: {instance.name} by {instance.created_by}")
        
        # Calculate next run time
        instance.update_next_run()
        
        # Start scheduler if it's active
        if instance.is_active:
            # In a production environment, you'd integrate with Celery or similar
            # For now, we'll just log the scheduling
            logger.info(f"Schedule {instance.name} is active, next run: {instance.next_run}")
    else:
        logger.info(f"Schedule updated: {instance.name}")
        
        # Recalculate next run time if cron expression changed
        if 'cron_expression' in kwargs.get('update_fields', []):
            instance.update_next_run()


@receiver(post_save, sender=AnsibleTemplate)
def template_post_save(sender, instance, created, **kwargs):
    """Handle template creation and updates"""
    if created:
        logger.info(f"New template created: {instance.name} by {instance.created_by}")
        
        # Validate template content
        from .utils import AnsibleValidator
        is_valid, error = AnsibleValidator.validate_yaml(instance.playbook_template)
        if not is_valid:
            logger.warning(f"Template {instance.name} validation failed: {error}")
    else:
        logger.info(f"Template updated: {instance.name}")


@receiver(pre_delete, sender=AnsiblePlaybook)
def playbook_pre_delete(sender, instance, **kwargs):
    """Handle playbook deletion"""
    logger.info(f"Deleting playbook: {instance.name}")
    
    # Check for running executions
    running_executions = instance.executions.filter(status__in=['pending', 'running'])
    if running_executions.exists():
        logger.warning(f"Playbook {instance.name} has running executions, cancelling them")
        
        # Cancel running executions
        for execution in running_executions:
            from .utils import AnsibleRunner
            runner = AnsibleRunner(execution)
            runner.cancel()
            execution.status = 'cancelled'
            execution.finished_at = timezone.now()
            execution.save()


@receiver(pre_delete, sender=AnsibleInventory)
def inventory_pre_delete(sender, instance, **kwargs):
    """Handle inventory deletion"""
    logger.info(f"Deleting inventory: {instance.name}")
    
    # Check for running executions using this inventory
    running_executions = AnsibleExecution.objects.filter(
        inventory=instance,
        status__in=['pending', 'running']
    )
    
    if running_executions.exists():
        logger.warning(f"Inventory {instance.name} is being used by running executions")
        # You might want to prevent deletion or cancel executions


@receiver(pre_delete, sender=AnsibleVault)
def vault_pre_delete(sender, instance, **kwargs):
    """Handle vault deletion"""
    logger.info(f"Deleting vault: {instance.name}")
    
    # Check if vault is being used by playbooks
    using_playbooks = AnsiblePlaybook.objects.filter(vault=instance)
    if using_playbooks.exists():
        logger.warning(f"Vault {instance.name} is being used by {using_playbooks.count()} playbooks")


@receiver(post_delete, sender=AnsiblePlaybook)
def playbook_post_delete(sender, instance, **kwargs):
    """Clean up after playbook deletion"""
    logger.info(f"Playbook deleted: {instance.name}")
    
    # Clear caches
    cache_keys = [
        f"playbook_{instance.id}",
        f"user_playbooks_{instance.created_by.id}",
        "ansible_dashboard_stats"
    ]
    cache.delete_many(cache_keys)


@receiver(post_delete, sender=AnsibleInventory)
def inventory_post_delete(sender, instance, **kwargs):
    """Clean up after inventory deletion"""
    logger.info(f"Inventory deleted: {instance.name}")
    
    # Clear inventory cache
    cache_key = f"inventory_{instance.id}"
    cache.delete(cache_key)


@receiver(post_delete, sender=AnsibleExecution)
def execution_post_delete(sender, instance, **kwargs):
    """Clean up after execution deletion"""
    logger.info(f"Execution deleted: {instance.id}")
    
    # Clean up any temporary files if they exist
    # This would be handled by the AnsibleRunner cleanup method
    
    # Clear dashboard cache
    cache.delete("ansible_dashboard_stats")


# Custom signal for scheduled executions
from django.dispatch import Signal

schedule_triggered = Signal()


@receiver(schedule_triggered)
def handle_schedule_trigger(sender, schedule, **kwargs):
    """Handle triggered scheduled execution"""
    logger.info(f"Schedule triggered: {schedule.name}")
    
    try:
        # Create and start execution
        execution = AnsibleScheduler.schedule_execution(schedule)
        logger.info(f"Scheduled execution started: {execution.id}")
    except Exception as e:
        logger.error(f"Failed to start scheduled execution for {schedule.name}: {str(e)}")
        
        # Update schedule with error
        schedule.last_run = timezone.now()
        schedule.last_status = 'failed'
        schedule.error_message = str(e)
        schedule.save()


# Signal for inventory synchronization
inventory_sync_requested = Signal()


@receiver(inventory_sync_requested)
def handle_inventory_sync(sender, inventory, **kwargs):
    """Handle inventory synchronization request"""
    logger.info(f"Inventory sync requested: {inventory.name}")
    
    try:
        from .utils import InventoryManager
        inventory_manager = InventoryManager(inventory)
        inventory_manager.sync_inventory()
        logger.info(f"Inventory synced successfully: {inventory.name}")
    except Exception as e:
        logger.error(f"Failed to sync inventory {inventory.name}: {str(e)}")


# Signal for vault operations
vault_operation = Signal()


@receiver(vault_operation)
def handle_vault_operation(sender, vault, operation, **kwargs):
    """Handle vault operations (encrypt/decrypt)"""
    logger.info(f"Vault operation requested: {operation} for {vault.name}")
    
    try:
        from .utils import VaultManager
        vault_manager = VaultManager()
        
        if operation == 'encrypt':
            # Encrypt vault content
            if vault.content and not vault.content.startswith('$ANSIBLE_VAULT'):
                encrypted_content = vault_manager.encrypt_vault_content(
                    vault.content, 
                    vault_manager.decrypt_vault_password(vault.vault_password)
                )
                vault.content = encrypted_content
                vault.save(update_fields=['content'])
                logger.info(f"Vault content encrypted: {vault.name}")
        
        elif operation == 'decrypt':
            # Decrypt vault content for viewing
            if vault.content and vault.content.startswith('$ANSIBLE_VAULT'):
                decrypted_content = vault_manager.decrypt_vault_content(
                    vault.content,
                    vault_manager.decrypt_vault_password(vault.vault_password)
                )
                # Return decrypted content without saving
                return decrypted_content
    
    except Exception as e:
        logger.error(f"Vault operation failed for {vault.name}: {str(e)}")
        raise e