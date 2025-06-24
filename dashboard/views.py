from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from servers.models import Server, ServerGroup, ServerConnection, ServerLog

@login_required
def dashboard_home(request):
    """Main dashboard view"""
    user = request.user
    
    # Server statistics
    servers = Server.objects.filter(created_by=user)
    total_servers = servers.count()
    online_servers = servers.filter(status='online').count()
    offline_servers = servers.filter(status='offline').count()
    error_servers = servers.filter(status='error').count()
    unknown_servers = servers.filter(status='unknown').count()
    
    # Recent servers (last 5)
    recent_servers = servers.order_by('-created_at')[:5]
    
    # Server groups
    groups = ServerGroup.objects.filter(created_by=user)
    total_groups = groups.count()
    
    # Active connections
    active_connections = ServerConnection.objects.filter(
        user=user,
        is_active=True
    ).select_related('server')
    
    # Recent activity (last 24 hours)
    yesterday = timezone.now() - timedelta(days=1)
    recent_logs = ServerLog.objects.filter(
        server__created_by=user,
        timestamp__gte=yesterday
    ).select_related('server').order_by('-timestamp')[:10]
    
    # Activity statistics
    today = timezone.now().date()
    connections_today = ServerLog.objects.filter(
        server__created_by=user,
        log_type='connection',
        timestamp__date=today
    ).count()
    
    commands_today = ServerLog.objects.filter(
        server__created_by=user,
        log_type='command',
        timestamp__date=today
    ).count()
    
    # Server status distribution for chart
    status_data = {
        'online': online_servers,
        'offline': offline_servers,
        'error': error_servers,
        'unknown': unknown_servers
    }
    
    # Weekly activity data
    week_ago = timezone.now() - timedelta(days=7)
    weekly_activity = []
    for i in range(7):
        day = timezone.now() - timedelta(days=i)
        day_connections = ServerLog.objects.filter(
            server__created_by=user,
            log_type='connection',
            timestamp__date=day.date()
        ).count()
        weekly_activity.append({
            'date': day.strftime('%Y-%m-%d'),
            'connections': day_connections
        })
    weekly_activity.reverse()
    
    context = {
        'total_servers': total_servers,
        'online_servers': online_servers,
        'offline_servers': offline_servers,
        'error_servers': error_servers,
        'unknown_servers': unknown_servers,
        'total_groups': total_groups,
        'recent_servers': recent_servers,
        'active_connections': active_connections,
        'recent_logs': recent_logs,
        'connections_today': connections_today,
        'commands_today': commands_today,
        'status_data': status_data,
        'weekly_activity': weekly_activity,
    }
    
    return render(request, 'dashboard/home.html', context)

@login_required
def server_overview(request):
    """Server overview with detailed statistics"""
    user = request.user
    servers = Server.objects.filter(created_by=user).select_related('group')
    
    # Group servers by status
    servers_by_status = {
        'online': servers.filter(status='online'),
        'offline': servers.filter(status='offline'),
        'error': servers.filter(status='error'),
        'unknown': servers.filter(status='unknown'),
    }
    
    # Group servers by group
    servers_by_group = {}
    for group in ServerGroup.objects.filter(created_by=user):
        servers_by_group[group.name] = servers.filter(group=group)
    
    # Ungrouped servers
    ungrouped_servers = servers.filter(group__isnull=True)
    if ungrouped_servers.exists():
        servers_by_group['Ungrouped'] = ungrouped_servers
    
    context = {
        'servers_by_status': servers_by_status,
        'servers_by_group': servers_by_group,
        'total_servers': servers.count(),
    }
    
    return render(request, 'dashboard/server_overview.html', context)

@login_required
def activity_logs(request):
    """Activity logs view"""
    user = request.user
    
    # Get all logs for user's servers
    logs = ServerLog.objects.filter(
        server__created_by=user
    ).select_related('server', 'user').order_by('-timestamp')
    
    # Filter by log type if specified
    log_type = request.GET.get('type')
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # Filter by server if specified
    server_id = request.GET.get('server')
    if server_id:
        logs = logs.filter(server_id=server_id)
    
    # Filter by date range if specified
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get servers for filter dropdown
    servers = Server.objects.filter(created_by=user).order_by('name')
    
    context = {
        'page_obj': page_obj,
        'log_types': ServerLog.LOG_TYPES,
        'servers': servers,
        'current_type': log_type,
        'current_server': server_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dashboard/activity_logs.html', context)