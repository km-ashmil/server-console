from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from .models import (
    AnsiblePlaybook, AnsibleInventory, AnsibleVault, AnsibleRole,
    AnsibleExecution, AnsibleSchedule, AnsibleTemplate
)
from .forms import (
    AnsiblePlaybookForm, AnsibleInventoryForm, AnsibleVaultForm, AnsibleRoleForm,
    AnsibleExecutionForm, AnsibleScheduleForm, AnsibleTemplateForm, PlaybookFromTemplateForm
)
from .utils import AnsibleRunner, InventoryManager, VaultManager
import json
import uuid
import threading
import time


@login_required
def dashboard(request):
    """Ansible dashboard with overview statistics"""
    user = request.user
    
    # Get statistics
    playbooks_count = AnsiblePlaybook.objects.filter(created_by=user).count()
    inventories_count = AnsibleInventory.objects.filter(created_by=user).count()
    roles_count = AnsibleRole.objects.filter(created_by=user).count()
    vaults_count = AnsibleVault.objects.filter(created_by=user).count()
    
    # Recent executions
    recent_executions = AnsibleExecution.objects.filter(
        started_by=user
    ).select_related('playbook', 'inventory').order_by('-started_at')[:10]
    
    # Running executions
    running_executions = AnsibleExecution.objects.filter(
        started_by=user,
        status__in=['pending', 'running']
    ).select_related('playbook', 'inventory')
    
    # Execution statistics
    execution_stats = AnsibleExecution.objects.filter(started_by=user).aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(status='success')),
        failed=Count('id', filter=Q(status='failed')),
        running=Count('id', filter=Q(status__in=['pending', 'running']))
    )
    
    # Scheduled executions
    upcoming_schedules = AnsibleSchedule.objects.filter(
        created_by=user,
        is_active=True,
        next_run__gte=timezone.now()
    ).select_related('playbook', 'inventory').order_by('next_run')[:5]
    
    context = {
        'playbooks_count': playbooks_count,
        'inventories_count': inventories_count,
        'roles_count': roles_count,
        'vaults_count': vaults_count,
        'recent_executions': recent_executions,
        'running_executions': running_executions,
        'execution_stats': execution_stats,
        'upcoming_schedules': upcoming_schedules,
    }
    
    return render(request, 'ansible_manager/dashboard.html', context)


# Playbook Views
@login_required
def playbook_list(request):
    """List all playbooks for the current user"""
    playbooks = AnsiblePlaybook.objects.filter(created_by=request.user)
    
    # Filtering
    category = request.GET.get('category')
    status = request.GET.get('status')
    search = request.GET.get('search')
    
    if category:
        playbooks = playbooks.filter(category=category)
    if status:
        playbooks = playbooks.filter(status=status)
    if search:
        playbooks = playbooks.filter(
            Q(name__icontains=search) | Q(display_name__icontains=search) | Q(description__icontains=search)
        )
    
    playbooks = playbooks.order_by('-updated_at')
    
    # Pagination
    paginator = Paginator(playbooks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': AnsiblePlaybook.CATEGORY_CHOICES,
        'statuses': AnsiblePlaybook.STATUS_CHOICES,
        'current_category': category,
        'current_status': status,
        'search_query': search,
    }
    
    return render(request, 'ansible_manager/playbook_list.html', context)


@login_required
def playbook_detail(request, playbook_id):
    """View playbook details"""
    playbook = get_object_or_404(AnsiblePlaybook, id=playbook_id, created_by=request.user)
    
    # Recent executions for this playbook
    recent_executions = playbook.executions.select_related('inventory').order_by('-started_at')[:10]
    
    # Execution statistics
    execution_stats = playbook.executions.aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(status='success')),
        failed=Count('id', filter=Q(status='failed')),
        running=Count('id', filter=Q(status__in=['pending', 'running']))
    )
    
    context = {
        'playbook': playbook,
        'recent_executions': recent_executions,
        'execution_stats': execution_stats,
    }
    
    return render(request, 'ansible_manager/playbook_detail.html', context)


@login_required
def playbook_create(request):
    """Create a new playbook"""
    if request.method == 'POST':
        form = AnsiblePlaybookForm(request.POST)
        if form.is_valid():
            playbook = form.save(commit=False)
            playbook.created_by = request.user
            playbook.save()
            messages.success(request, f'Playbook "{playbook.display_name}" created successfully.')
            return redirect('ansible_manager:playbook_detail', playbook_id=playbook.id)
    else:
        form = AnsiblePlaybookForm()
    
    return render(request, 'ansible_manager/playbook_form.html', {'form': form, 'title': 'Create Playbook'})


@login_required
def playbook_edit(request, playbook_id):
    """Edit an existing playbook"""
    playbook = get_object_or_404(AnsiblePlaybook, id=playbook_id, created_by=request.user)
    
    if request.method == 'POST':
        form = AnsiblePlaybookForm(request.POST, instance=playbook)
        if form.is_valid():
            playbook = form.save(commit=False)
            playbook.version += 1
            playbook.save()
            messages.success(request, f'Playbook "{playbook.display_name}" updated successfully.')
            return redirect('ansible_manager:playbook_detail', playbook_id=playbook.id)
    else:
        form = AnsiblePlaybookForm(instance=playbook)
    
    return render(request, 'ansible_manager/playbook_form.html', {
        'form': form, 'playbook': playbook, 'title': 'Edit Playbook'
    })


@login_required
def playbook_delete(request, playbook_id):
    """Delete a playbook"""
    playbook = get_object_or_404(AnsiblePlaybook, id=playbook_id, created_by=request.user)
    
    if request.method == 'POST':
        playbook_name = playbook.display_name
        playbook.delete()
        messages.success(request, f'Playbook "{playbook_name}" deleted successfully.')
        return redirect('ansible_manager:playbook_list')
    
    return render(request, 'ansible_manager/playbook_confirm_delete.html', {'playbook': playbook})


# Inventory Views
@login_required
def inventory_list(request):
    """List all inventories for the current user"""
    inventories = AnsibleInventory.objects.filter(created_by=request.user).order_by('-updated_at')
    
    # Filtering
    inventory_type = request.GET.get('type')
    search = request.GET.get('search')
    
    if inventory_type:
        inventories = inventories.filter(inventory_type=inventory_type)
    if search:
        inventories = inventories.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(inventories, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'types': AnsibleInventory.TYPE_CHOICES,
        'current_type': inventory_type,
        'search_query': search,
    }
    
    return render(request, 'ansible_manager/inventory_list.html', context)


@login_required
def inventory_detail(request, inventory_id):
    """View inventory details"""
    inventory = get_object_or_404(AnsibleInventory, id=inventory_id, created_by=request.user)
    
    # Generate inventory content for display
    inventory_manager = InventoryManager(inventory)
    inventory_content = inventory_manager.generate_inventory()
    
    context = {
        'inventory': inventory,
        'inventory_content': inventory_content,
    }
    
    return render(request, 'ansible_manager/inventory_detail.html', context)


@login_required
def inventory_create(request):
    """Create a new inventory"""
    if request.method == 'POST':
        form = AnsibleInventoryForm(request.POST, user=request.user)
        if form.is_valid():
            inventory = form.save(commit=False)
            inventory.created_by = request.user
            inventory.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, f'Inventory "{inventory.name}" created successfully.')
            return redirect('ansible_manager:inventory_detail', inventory_id=inventory.id)
    else:
        form = AnsibleInventoryForm(user=request.user)
    
    return render(request, 'ansible_manager/inventory_form.html', {'form': form, 'title': 'Create Inventory'})


@login_required
def inventory_edit(request, inventory_id):
    """Edit an existing inventory"""
    inventory = get_object_or_404(AnsibleInventory, id=inventory_id, created_by=request.user)
    
    if request.method == 'POST':
        form = AnsibleInventoryForm(request.POST, instance=inventory, user=request.user)
        if form.is_valid():
            inventory = form.save()
            messages.success(request, f'Inventory "{inventory.name}" updated successfully.')
            return redirect('ansible_manager:inventory_detail', inventory_id=inventory.id)
    else:
        form = AnsibleInventoryForm(instance=inventory, user=request.user)
    
    return render(request, 'ansible_manager/inventory_form.html', {
        'form': form, 'inventory': inventory, 'title': 'Edit Inventory'
    })


@login_required
def inventory_sync(request, inventory_id):
    """Sync inventory with ServerHub servers"""
    inventory = get_object_or_404(AnsibleInventory, id=inventory_id, created_by=request.user)
    
    if request.method == 'POST':
        inventory.sync_inventory()
        messages.success(request, f'Inventory "{inventory.name}" synced successfully.')
    
    return redirect('ansible_manager:inventory_detail', inventory_id=inventory.id)


# Execution Views
@login_required
def execution_list(request):
    """List all executions for the current user"""
    executions = AnsibleExecution.objects.filter(started_by=request.user)
    
    # Filtering
    status = request.GET.get('status')
    playbook_id = request.GET.get('playbook')
    
    if status:
        executions = executions.filter(status=status)
    if playbook_id:
        executions = executions.filter(playbook_id=playbook_id)
    
    executions = executions.select_related('playbook', 'inventory').order_by('-started_at')
    
    # Pagination
    paginator = Paginator(executions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get playbooks for filter
    playbooks = AnsiblePlaybook.objects.filter(created_by=request.user).values('id', 'display_name')
    
    context = {
        'page_obj': page_obj,
        'statuses': AnsibleExecution.STATUS_CHOICES,
        'playbooks': playbooks,
        'current_status': status,
        'current_playbook': playbook_id,
    }
    
    return render(request, 'ansible_manager/execution_list.html', context)


@login_required
def execution_detail(request, execution_id):
    """View execution details"""
    execution = get_object_or_404(AnsibleExecution, id=execution_id, started_by=request.user)
    
    context = {
        'execution': execution,
    }
    
    return render(request, 'ansible_manager/execution_detail.html', context)


@login_required
def execution_create(request):
    """Create and start a new execution"""
    if request.method == 'POST':
        form = AnsibleExecutionForm(request.POST, user=request.user)
        if form.is_valid():
            # Create execution record
            execution = AnsibleExecution.objects.create(
                playbook=form.cleaned_data['playbook'],
                inventory=form.cleaned_data['inventory'],
                started_by=request.user,
                extra_vars=json.loads(form.cleaned_data['extra_vars'] or '{}'),
                limit=form.cleaned_data['limit'],
                tags=form.cleaned_data['tags'],
                skip_tags=form.cleaned_data['skip_tags']
            )
            
            # Start execution in background
            runner = AnsibleRunner(execution)
            thread = threading.Thread(target=runner.run)
            thread.daemon = True
            thread.start()
            
            messages.success(request, 'Playbook execution started successfully.')
            return redirect('ansible_manager:execution_detail', execution_id=execution.id)
    else:
        form = AnsibleExecutionForm(user=request.user)
    
    return render(request, 'ansible_manager/execution_form.html', {'form': form, 'title': 'Execute Playbook'})


@login_required
def execution_cancel(request, execution_id):
    """Cancel a running execution"""
    execution = get_object_or_404(AnsibleExecution, id=execution_id, started_by=request.user)
    
    if execution.is_running():
        # Cancel the execution
        runner = AnsibleRunner(execution)
        runner.cancel()
        execution.status = 'cancelled'
        execution.finished_at = timezone.now()
        execution.save()
        messages.success(request, 'Execution cancelled successfully.')
    else:
        messages.warning(request, 'Execution is not running and cannot be cancelled.')
    
    return redirect('ansible_manager:execution_detail', execution_id=execution.id)


@login_required
def execution_output_stream(request, execution_id):
    """Stream execution output in real-time"""
    execution = get_object_or_404(AnsibleExecution, id=execution_id, started_by=request.user)
    
    def event_stream():
        """Generator for server-sent events"""
        last_output_length = 0
        
        while execution.is_running():
            # Refresh execution from database
            execution.refresh_from_db()
            
            # Send new output if available
            current_output = execution.output or ''
            if len(current_output) > last_output_length:
                new_output = current_output[last_output_length:]
                yield f"data: {json.dumps({'output': new_output})}\n\n"
                last_output_length = len(current_output)
            
            # Send status updates
            yield f"data: {json.dumps({'status': execution.status})}\n\n"
            
            time.sleep(1)
        
        # Send final status
        yield f"data: {json.dumps({'status': execution.status, 'finished': True})}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response


# Template Views
@login_required
def template_list(request):
    """List all templates available to the user"""
    templates = AnsibleTemplate.objects.filter(
        Q(created_by=request.user) | Q(is_public=True)
    ).order_by('-created_at')
    
    # Filtering
    category = request.GET.get('category')
    search = request.GET.get('search')
    
    if category:
        templates = templates.filter(category=category)
    if search:
        templates = templates.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(templates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': AnsiblePlaybook.CATEGORY_CHOICES,
        'current_category': category,
        'search_query': search,
    }
    
    return render(request, 'ansible_manager/template_list.html', context)


@login_required
def template_detail(request, template_id):
    """View template details"""
    template = get_object_or_404(AnsibleTemplate, id=template_id)
    
    # Check access permissions
    if not template.is_public and template.created_by != request.user:
        messages.error(request, 'You do not have permission to view this template.')
        return redirect('ansible_manager:template_list')
    
    context = {
        'template': template,
    }
    
    return render(request, 'ansible_manager/template_detail.html', context)


@login_required
def playbook_from_template(request, template_id):
    """Create a playbook from a template"""
    template = get_object_or_404(AnsibleTemplate, id=template_id)
    
    # Check access permissions
    if not template.is_public and template.created_by != request.user:
        messages.error(request, 'You do not have permission to use this template.')
        return redirect('ansible_manager:template_list')
    
    if request.method == 'POST':
        form = PlaybookFromTemplateForm(request.POST, user=request.user)
        if form.is_valid():
            # Create playbook from template
            from jinja2 import Template
            
            template_vars = json.loads(form.cleaned_data['template_variables'] or '{}')
            jinja_template = Template(template.playbook_template)
            playbook_content = jinja_template.render(**template_vars)
            
            playbook = AnsiblePlaybook.objects.create(
                name=form.cleaned_data['name'],
                display_name=form.cleaned_data['display_name'],
                description=form.cleaned_data['description'],
                category=template.category,
                content=playbook_content,
                created_by=request.user
            )
            
            # Update template usage count
            template.usage_count += 1
            template.save()
            
            messages.success(request, f'Playbook "{playbook.display_name}" created from template successfully.')
            return redirect('ansible_manager:playbook_detail', playbook_id=playbook.id)
    else:
        form = PlaybookFromTemplateForm(user=request.user, initial={'template': template})
    
    context = {
        'form': form,
        'template': template,
        'title': f'Create Playbook from "{template.name}"'
    }
    
    return render(request, 'ansible_manager/playbook_from_template.html', context)


# API Views
@login_required
@require_http_methods(["GET"])
def api_playbooks(request):
    """API endpoint for playbooks"""
    playbooks = AnsiblePlaybook.objects.filter(created_by=request.user).values(
        'id', 'name', 'display_name', 'category', 'status', 'created_at'
    )
    return JsonResponse(list(playbooks), safe=False)


@login_required
@require_http_methods(["GET"])
def api_inventories(request):
    """API endpoint for inventories"""
    inventories = AnsibleInventory.objects.filter(created_by=request.user).values(
        'id', 'name', 'inventory_type', 'created_at'
    )
    return JsonResponse(list(inventories), safe=False)


@login_required
@require_http_methods(["GET"])
def api_execution_status(request, execution_id):
    """API endpoint for execution status"""
    execution = get_object_or_404(AnsibleExecution, id=execution_id, started_by=request.user)
    
    data = {
        'id': str(execution.id),
        'status': execution.status,
        'started_at': execution.started_at.isoformat(),
        'finished_at': execution.finished_at.isoformat() if execution.finished_at else None,
        'hosts_count': execution.hosts_count,
        'tasks_count': execution.tasks_count,
        'changed_count': execution.changed_count,
        'failed_count': execution.failed_count,
        'return_code': execution.return_code,
    }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def api_inventory_sync(request, inventory_id):
    """API endpoint for inventory synchronization"""
    inventory = get_object_or_404(AnsibleInventory, id=inventory_id, created_by=request.user)
    
    try:
        inventory.sync_inventory()
        return JsonResponse({'success': True, 'message': 'Inventory synced successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)