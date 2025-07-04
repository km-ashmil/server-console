# ServerHub Performance Optimizations

This document outlines the performance optimizations implemented in the ServerHub application to improve response times, reduce server load, and enhance the overall user experience.

## Database Optimizations

### Query Caching

We've implemented strategic query caching throughout the application, particularly in dashboard views that perform expensive database operations:

- **Dashboard Home View**: Caches server statistics, server groups, recent activity, and daily/weekly activity data with varying timeouts:
  - Server statistics and groups: 5 minutes
  - Recent activity logs: 1 minute
  - Weekly activity data: 1 hour

- **Server Overview View**: Caches server status, server groups, and total server count data for 5 minutes.

- **Activity Logs View**: Implements user-specific caching with cache keys based on user ID and request parameters:
  - Server list for filter dropdown: 5 minutes
  - Logs count and paginated page objects: 1 minute

### Database Indexes

We've added strategic database indexes to improve query performance:

- **ServerGroup Model**:
  - `name` field for faster lookups
  - `created_by` field for user-specific queries

- **Server Model**:
  - `hostname` field for connection lookups
  - `status` field for filtering by server status
  - `last_checked` field for monitoring queries
  - `created_at` field for chronological sorting
  - Composite index on `(group, status)` for filtered group views

- **ServerConnection Model**:
  - `connected_at` field for chronological sorting
  - `last_activity` field for session timeout detection
  - `is_active` field for active connection filtering
  - Composite index on `(server, is_active)` for server-specific active connections

- **ServerLog Model**:
  - `log_type` field for filtering by log type
  - `timestamp` field for chronological sorting
  - `session_id` field for session-specific logs
  - Composite indexes on `(server, timestamp)`, `(user, timestamp)`, `(server, log_type, timestamp)`, and `(server, user, timestamp)` for common query patterns

## Caching Infrastructure

### Middleware-Level Caching

We've implemented a custom `OptimizedCacheMiddleware` that provides:

- **URL-specific caching**: Different cache timeouts for different dashboard views
- **User-specific caching**: Ensures users only see their own data
- **Smart cache invalidation**: Avoids caching error responses or streaming content

### Template Fragment Caching

We've implemented custom template tags for fragment caching:

- **User-specific fragment caching**: The `user_cache` template tag allows caching parts of templates with user-specific keys
- **Variable cache timeouts**: Different components can have different cache durations
- **Cache key generation**: The `cache_key` template tag helps generate consistent cache keys

## Maintenance and Cleanup

### Management Commands

We've added custom management commands to maintain system performance:

- **cleanup_sessions**: Automatically cleans up expired server sessions and connections
  ```bash
  python manage.py cleanup_sessions --days=1
  ```

- **clear_expired_cache**: Manages cache entries to prevent memory bloat
  ```bash
  python manage.py clear_expired_cache
  python manage.py clear_expired_cache --force  # Clear all cache entries
  ```

### Scheduled Optimization Script

We've created a script (`scripts/run_optimizations.py`) that can be scheduled to run periodically (e.g., via cron job) to:

- Clean up expired sessions
- Clear expired cache entries
- Log optimization activities

## Configuration

### Cache Settings

The application is configured to use:

- **Redis** in production for high-performance caching
- **LocMemCache** in development for easier testing

Cache timeouts are configured globally (5 minutes default) and can be overridden for specific views or template fragments.

## Future Optimization Opportunities

1. **WebSocket Payload Optimization**: Reduce the size of data transferred over WebSockets
2. **SSH Connection Pooling**: Implement connection pooling for SSH connections
3. **Frontend Asset Optimization**: Implement lazy loading and bundle splitting
4. **Rate Limiting**: Add rate limiting for API endpoints
5. **Key Rotation**: Implement automatic rotation of encryption keys