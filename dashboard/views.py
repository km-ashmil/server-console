from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from servers.models import Server, ServerGroup, ServerConnection, ServerLog

@login_required
def dashboard_home(request):
    """Main dashboard view with caching for expensive queries"""
    user = request.user
    cache_key_prefix = f'dashboard_home_{user.id}'
    cache_timeout = 300  # 5 minutes cache timeout
    
    # Server statistics - cached per user
    servers_stats_key = f'{cache_key_prefix}_servers_stats'
    servers_stats = cache.get(servers_stats_key)
    
    if servers_stats is None:
        servers = Server.objects.filter(created_by=user)
        total_servers = servers.count()
        online_servers = servers.filter(status='online').count()
        offline_servers = servers.filter(status='offline').count()
        error_servers = servers.filter(status='error').count()
        unknown_servers = servers.filter(status='unknown').count()
        
        status_data = {
            'online': online_servers,
            'offline': offline_servers,
            'error': error_servers,
            'unknown': unknown_servers
        }
        
        servers_stats = {
            'total_servers': total_servers,
            'online_servers': online_servers,
            'offline_servers': offline_servers,
            'error_servers': error_servers,
            'unknown_servers': unknown_servers,
            'status_data': status_data
        }
        
        cache.set(servers_stats_key, servers_stats, cache_timeout)
    else:
        total_servers = servers_stats['total_servers']
        online_servers = servers_stats['online_servers']
        offline_servers = servers_stats['offline_servers']
        error_servers = servers_stats['error_servers']
        unknown_servers = servers_stats['unknown_servers']
        status_data = servers_stats.get('status_data', {
            'online': online_servers,
            'offline': offline_servers,
            'error': error_servers,
            'unknown': unknown_servers
        })
    
    # Recent servers (last 5) - not cached as it's a simple query
    servers = Server.objects.filter(created_by=user)
    recent_servers = servers.order_by('-created_at')[:5]
    
    # Server groups - cached per user
    groups_key = f'{cache_key_prefix}_groups'
    groups_data = cache.get(groups_key)
    
    if groups_data is None:
        groups = ServerGroup.objects.filter(created_by=user)
        total_groups = groups.count()
        groups_data = {'total_groups': total_groups}
        cache.set(groups_key, groups_data, cache_timeout)
    else:
        total_groups = groups_data['total_groups']
    
    # Active connections - not cached as it's real-time data
    active_connections = ServerConnection.objects.filter(
        user=user,
        is_active=True
    ).select_related('server')
    
    # Recent activity (last 24 hours) - cached briefly
    recent_logs_key = f'{cache_key_prefix}_recent_logs'
    recent_logs = cache.get(recent_logs_key)
    
    if recent_logs is None:
        yesterday = timezone.now() - timedelta(days=1)
        recent_logs = list(ServerLog.objects.filter(
            server__created_by=user,
            timestamp__gte=yesterday
        ).select_related('server').order_by('-timestamp')[:10])
        cache.set(recent_logs_key, recent_logs, 60)  # Cache for 1 minute only
    
    # Activity statistics - cached per user per day
    today = timezone.now().date()
    today_stats_key = f'{cache_key_prefix}_today_stats_{today.isoformat()}'
    today_stats = cache.get(today_stats_key)
    
    if today_stats is None:
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
        
        today_stats = {
            'connections_today': connections_today,
            'commands_today': commands_today
        }
        
        cache.set(today_stats_key, today_stats, 300)  # Cache for 5 minutes
    else:
        connections_today = today_stats['connections_today']
        commands_today = today_stats['commands_today']
    
    # Weekly activity data - cached per user per day
    weekly_activity_key = f'{cache_key_prefix}_weekly_activity_{today.isoformat()}'
    weekly_activity = cache.get(weekly_activity_key)
    
    if weekly_activity is None:
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
        cache.set(weekly_activity_key, weekly_activity, 3600)  # Cache for 1 hour
    
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
    """Server overview with detailed statistics and caching"""
    user = request.user
    cache_key_prefix = f'server_overview_{user.id}'
    cache_timeout = 300  # 5 minutes cache timeout
    
    # Try to get cached data
    cache_key = f'{cache_key_prefix}_{request.GET.urlencode()}'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        servers = Server.objects.filter(created_by=user).select_related('group')
        
        # Group servers by status
        servers_by_status = {
            'online': list(servers.filter(status='online')),
            'offline': list(servers.filter(status='offline')),
            'error': list(servers.filter(status='error')),
            'unknown': list(servers.filter(status='unknown')),
        }
        
        # Group servers by group
        servers_by_group = {}
        for group in ServerGroup.objects.filter(created_by=user):
            group_servers = list(servers.filter(group=group))
            if group_servers:
                servers_by_group[group.name] = group_servers
        
        # Ungrouped servers
        ungrouped_servers = list(servers.filter(group__isnull=True))
        if ungrouped_servers:
            servers_by_group['Ungrouped'] = ungrouped_servers
        
        total_servers = servers.count()
        
        # Cache the data
        cached_data = {
            'servers_by_status': servers_by_status,
            'servers_by_group': servers_by_group,
            'total_servers': total_servers,
        }
        cache.set(cache_key, cached_data, cache_timeout)
    
    context = cached_data
    
    return render(request, 'dashboard/server_overview.html', context)

@login_required
def activity_logs(request):
    """Activity logs view with optimized queries and caching"""
    user = request.user
    
    # Cache key based on user and request parameters
    params = request.GET.copy()
    if 'page' in params:
        del params['page']  # Don't include page in cache key
    cache_key = f'activity_logs_{user.id}_{params.urlencode()}'
    
    # Get servers for filter dropdown - cached
    servers_cache_key = f'activity_logs_servers_{user.id}'
    servers = cache.get(servers_cache_key)
    if servers is None:
        servers = list(Server.objects.filter(created_by=user).order_by('name'))
        cache.set(servers_cache_key, servers, 300)  # Cache for 5 minutes
    
    # Get filter parameters
    log_type = request.GET.get('type')
    server_id = request.GET.get('server')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    page_number = request.GET.get('page', 1)
    
    # Try to get cached logs count
    logs_count_key = f'{cache_key}_count'
    logs_count = cache.get(logs_count_key)
    
    # Try to get cached page
    page_cache_key = f'{cache_key}_page_{page_number}'
    page_obj = cache.get(page_cache_key)
    
    if page_obj is None:
        # Build query with optimized filters
        logs = ServerLog.objects.filter(server__created_by=user)
        
        # Apply filters
        if log_type:
            logs = logs.filter(log_type=log_type)
        if server_id:
            logs = logs.filter(server_id=server_id)
        if date_from:
            logs = logs.filter(timestamp__date__gte=date_from)
        if date_to:
            logs = logs.filter(timestamp__date__lte=date_to)
        
        # Add select_related to optimize queries
        logs = logs.select_related('server', 'user').order_by('-timestamp')
        
        # Get count if not cached
        if logs_count is None:
            logs_count = logs.count()
            cache.set(logs_count_key, logs_count, 60)  # Cache for 1 minute
        
        # Pagination
        from django.core.paginator import Paginator
        paginator = Paginator(logs, 50)
        page_obj = paginator.get_page(page_number)
        
        # Cache the page object
        cache.set(page_cache_key, page_obj, 60)  # Cache for 1 minute
    
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