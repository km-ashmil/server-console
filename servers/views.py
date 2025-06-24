from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import paramiko
import socket
import threading
import json
from .models import Server, ServerGroup, ServerLog
from .forms import ServerForm, ServerGroupForm, ServerTestForm, ServerSearchForm

@login_required
def server_list(request):
    """List all servers with search and filtering"""
    search_form = ServerSearchForm(request.GET, user=request.user)
    servers = Server.objects.filter(created_by=request.user)
    
    # Apply filters
    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        group = search_form.cleaned_data.get('group')
        status = search_form.cleaned_data.get('status')
        tags = search_form.cleaned_data.get('tags')
        
        if search_query:
            servers = servers.filter(
                Q(name__icontains=search_query) |
                Q(hostname__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if group:
            servers = servers.filter(group=group)
        
        if status:
            servers = servers.filter(status=status)
        
        if tags:
            servers = servers.filter(tags__icontains=tags)
    
    # Pagination
    paginator = Paginator(servers, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'total_servers': servers.count(),
    }
    return render(request, 'servers/list.html', context)

@login_required
def server_detail(request, pk):
    """Show server details"""
    server = get_object_or_404(Server, pk=pk, created_by=request.user)
    recent_logs = ServerLog.objects.filter(server=server)[:10]
    
    
    context = {
        'server': server,
        'recent_logs': recent_logs,
    }
    return render(request, 'servers/detail.html', context)

@login_required
def server_create(request):
    """Create a new server"""
    if request.method == 'POST':
        form = ServerForm(request.POST, user=request.user)
        if form.is_valid():
            server = form.save()
            messages.success(request, f'Server "{server.name}" created successfully!')
            return redirect('servers:detail', pk=server.pk)
    else:
        form = ServerForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Add New Server',
        'submit_text': 'Create Server'
    }
    return render(request, 'servers/add.html', context)

@login_required
def server_edit(request, pk):
    """Edit an existing server"""
    server = get_object_or_404(Server, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        form = ServerForm(request.POST, instance=server, user=request.user)
        if form.is_valid():
            server = form.save()
            messages.success(request, f'Server "{server.name}" updated successfully!')
            return redirect('servers:detail', pk=server.pk)
    else:
        form = ServerForm(instance=server, user=request.user)
    
    context = {
        'form': form,
        'server': server,
        'title': f'Edit {server.name}',
        'submit_text': 'Update Server'
    }
    return render(request, 'servers/edit.html', context)

@login_required
def server_delete(request, pk):
    """Delete a server"""
    server = get_object_or_404(Server, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        server_name = server.name
        server.delete()
        messages.success(request, f'Server "{server_name}" deleted successfully!')
        return redirect('servers:list')
    
    context = {'server': server}
    return render(request, 'servers/server_confirm_delete.html', context)

@login_required
def server_test(request, pk):
    """Test server connection"""
    server = get_object_or_404(Server, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        # Check if this is a direct test from the edit page
        if 'hostname' in request.POST:
            # Create a temporary server object with the provided parameters
            temp_server = Server(
                hostname=request.POST.get('hostname'),
                port=int(request.POST.get('port', 22)),
                username=request.POST.get('username'),
                auth_method=request.POST.get('auth_method', 'password'),
                timeout=int(request.POST.get('timeout', 30)),
                created_by=request.user
            )
            
            # Set authentication credentials
            if temp_server.auth_method == 'password':
                temp_server.set_password(request.POST.get('password', ''))
            elif temp_server.auth_method in ['key', 'key_password']:
                temp_server.set_private_key(request.POST.get('private_key', ''))
                if temp_server.auth_method == 'key_password':
                    temp_server.set_key_password(request.POST.get('key_password', ''))
            
            # Test connection
            result = test_server_connection(temp_server)
            
            # Log the test
            ServerLog.objects.create(
                server=server,
                user=request.user,
                log_type='connection',
                message=f'Connection test from edit page: {result["status"]}'
            )
            
            return JsonResponse({
                'success': result['status'] == 'success',
                'message': result['message'],
                'output': result.get('output', ''),
                'error': result.get('error', '')
            })
        else:
            # Regular form submission from the test page
            form = ServerTestForm(request.POST)
            if form.is_valid():
                test_command = form.cleaned_data['test_command']
                result = test_server_connection(server, test_command)
                
                # Log the test
                ServerLog.objects.create(
                    server=server,
                    user=request.user,
                    log_type='connection',
                    message=f'Connection test: {result["status"]}'
                )
                
                return JsonResponse(result)
    else:
        form = ServerTestForm()
    
    context = {
        'server': server,
        'form': form
    }
    return render(request, 'servers/server_test.html', context)

def test_server_connection(server, command='whoami'):
    """Test SSH connection to server"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Prepare connection parameters
        connect_params = {
            'hostname': server.hostname,
            'port': server.port,
            'username': server.username,
            'timeout': server.timeout,
        }
        
        # Add authentication
        if server.auth_method == 'password':
            password = server.get_password()
            if not password:
                return {
                    'status': 'error',
                    'message': 'Password is missing. Please edit the server and add a password.'
                }
            connect_params['password'] = password
        elif server.auth_method in ['key', 'key_password']:
            from io import StringIO
            private_key_str = server.get_private_key()
            
            if not private_key_str:
                return {
                    'status': 'error',
                    'message': 'SSH key is missing. Please edit the server and add a private key.'
                }
                
            private_key_file = StringIO(private_key_str)
            
            try:
                if server.auth_method == 'key_password':
                    key_password = server.get_key_password()
                    if not key_password:
                        return {
                            'status': 'error',
                            'message': 'Key password is required but missing. Please edit the server and add the key password.'
                        }
                    private_key = paramiko.RSAKey.from_private_key(private_key_file, password=key_password)
                else:
                    private_key = paramiko.RSAKey.from_private_key(private_key_file)
                connect_params['pkey'] = private_key
            except Exception as e:
                try:
                    private_key_file.seek(0)
                    if server.auth_method == 'key_password':
                        key_password = server.get_key_password()
                        if not key_password:
                            return {
                                'status': 'error',
                                'message': 'Key password is required but missing. Please edit the server and add the key password.'
                            }
                        private_key = paramiko.Ed25519Key.from_private_key(private_key_file, password=key_password)
                    else:
                        private_key = paramiko.Ed25519Key.from_private_key(private_key_file)
                    connect_params['pkey'] = private_key
                except Exception as e2:
                    return {
                        'status': 'error',
                        'message': f'Invalid SSH key format: {str(e2)}'
                    }
        
        # Connect and execute command
        client.connect(**connect_params)
        stdin, stdout, stderr = client.exec_command(command)
        
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        client.close()
        
        # Update server status
        server.status = 'online'
        server.last_checked = timezone.now()
        server.last_error = ''
        server.save()
        
        return {
            'status': 'success',
            'message': 'Connection successful!',
            'output': output,
            'error': error if error else None
        }
        
    except paramiko.AuthenticationException:
        error_msg = 'Authentication failed'
        server.status = 'error'
        server.last_error = error_msg
        server.last_checked = timezone.now()
        server.save()
        return {'status': 'error', 'message': error_msg}
        
    except socket.timeout:
        error_msg = 'Connection timeout'
        server.status = 'offline'
        server.last_error = error_msg
        server.last_checked = timezone.now()
        server.save()
        return {'status': 'error', 'message': error_msg}
        
    except Exception as e:
        error_msg = f'Connection failed: {str(e)}'
        server.status = 'error'
        server.last_error = error_msg
        server.last_checked = timezone.now()
        server.save()
        return {'status': 'error', 'message': error_msg}

@login_required
@require_http_methods(["POST"])
def server_check_status(request, pk):
    """Check server status via AJAX"""
    server = get_object_or_404(Server, pk=pk, created_by=request.user)
    
    def check_status():
        result = test_server_connection(server, 'echo "status_check"')
        return result
    
    # Run status check in background
    result = check_status()
    
    return JsonResponse({
        'status': server.status,
        'last_checked': server.last_checked.isoformat() if server.last_checked else None,
        'result': result
    })

# Server Group Views
@login_required
def group_list(request):
    """List server groups"""
    groups = ServerGroup.objects.filter(created_by=request.user)
    context = {'groups': groups}
    return render(request, 'servers/group_list.html', context)

@login_required
def group_create(request):
    """Create a new server group"""
    if request.method == 'POST':
        form = ServerGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, f'Group "{group.name}" created successfully!')
            return redirect('servers:group_list')
    else:
        form = ServerGroupForm()
    
    context = {
        'form': form,
        'title': 'Create Server Group'
    }
    return render(request, 'servers/group_form.html', context)

@login_required
def group_edit(request, pk):
    """Edit a server group"""
    group = get_object_or_404(ServerGroup, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        form = ServerGroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save()
            messages.success(request, f'Group "{group.name}" updated successfully!')
            return redirect('servers:group_list')
    else:
        form = ServerGroupForm(instance=group)
    
    context = {
        'form': form,
        'group': group,
        'title': f'Edit {group.name}'
    }
    return render(request, 'servers/group_form.html', context)

@login_required
def group_delete(request, pk):
    """Delete a server group"""
    group = get_object_or_404(ServerGroup, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        group_name = group.name
        group.delete()
        messages.success(request, f'Group "{group_name}" deleted successfully!')
        return redirect('servers:group_list')
    
    context = {'group': group}
    return render(request, 'servers/group_confirm_delete.html', context)