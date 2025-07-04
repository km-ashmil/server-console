from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from servers.models import Server, ServerConnection, ServerLog
from django.core.paginator import Paginator

@login_required
def terminal_view(request, server_id):
    """Main terminal view"""
    server = get_object_or_404(Server, id=server_id, created_by=request.user)
    
    # Check if a session_id was provided for reconnection
    session_id = request.GET.get('session_id')
    
    # Construct WebSocket URL
    websocket_url = f'ws/terminal/{server_id}/'
    if session_id:
        # If session_id is provided, append it to the WebSocket URL
        websocket_url = f'ws/terminal/{server_id}/{session_id}/'
    
    context = {
        'server': server,
        'websocket_url': websocket_url
    }
    return render(request, 'terminal/terminal.html', context)

@login_required
def terminal_sessions(request):
    """List active terminal sessions"""
    sessions = ServerConnection.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('server')
    
    # Calculate statistics
    total_sessions = sessions.count()
    active_sessions = sessions.filter(is_active=True).count()
    idle_sessions = 0  # Could implement idle detection based on last_activity
    unique_servers = sessions.values('server').distinct().count()
    
    context = {
        'sessions': sessions,
        'total_sessions': total_sessions,
        'active_sessions': active_sessions,
        'idle_sessions': idle_sessions,
        'unique_servers': unique_servers
    }
    
    # Handle AJAX requests for auto-refresh
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'terminal/sessions_table.html', context)
    
    return render(request, 'terminal/sessions.html', context)

@login_required
def terminal_logs(request, server_id):
    """View terminal logs for a server"""
    server = get_object_or_404(Server, id=server_id, created_by=request.user)
    
    logs = ServerLog.objects.filter(
        server=server,
        user=request.user
    ).order_by('-timestamp')
    
    # Filter by log type if specified
    log_type = request.GET.get('type')
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'server': server,
        'page_obj': page_obj,
        'log_types': ServerLog.LOG_TYPES,
        'current_type': log_type
    }
    return render(request, 'terminal/logs.html', context)

@login_required
def close_session(request, session_id):
    """Close a terminal session"""
    if request.method == 'POST':
        try:
            connection = ServerConnection.objects.get(
                session_id=session_id,
                user=request.user,
                is_active=True
            )
            connection.is_active = False
            connection.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Session closed successfully'
            })
        except ServerConnection.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Session not found'
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })