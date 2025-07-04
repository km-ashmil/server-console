from django.utils.cache import get_cache_key, learn_cache_key, patch_response_headers
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.cache import cache

class OptimizedCacheMiddleware(MiddlewareMixin):
    """
    Middleware that applies cache to responses for authenticated users.
    
    This middleware must be placed AFTER:
    - UpdateCacheMiddleware
    - SessionMiddleware
    - AuthenticationMiddleware
    
    And BEFORE:
    - CommonMiddleware
    - FetchFromCacheMiddleware
    """
    
    def process_response(self, request, response):
        """Set appropriate cache headers and cache the response if applicable."""
        # Only cache for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
            
        # Don't cache responses with error status codes
        if response.status_code != 200:
            return response
            
        # Don't cache streaming responses
        if getattr(response, 'streaming', False):
            return response
            
        # Don't cache if the response already has cache headers
        if response.has_header('Cache-Control') and 'max-age=0' not in response['Cache-Control']:
            return response
            
        # Don't cache POST requests or requests with query parameters
        if request.method != 'GET' or len(request.GET) > 0:
            return response
            
        # Only cache specific URL patterns
        cacheable_urls = [
            '/dashboard/',
            '/dashboard/server-overview/',
            '/dashboard/activity-logs/',
        ]
        
        should_cache = False
        for url in cacheable_urls:
            if request.path.startswith(url):
                should_cache = True
                break
                
        if not should_cache:
            return response
            
        # Set cache timeout based on URL
        if request.path == '/dashboard/':
            timeout = 300  # 5 minutes
        elif request.path == '/dashboard/server-overview/':
            timeout = 300  # 5 minutes
        elif request.path == '/dashboard/activity-logs/':
            timeout = 60   # 1 minute
        else:
            timeout = 600  # 10 minutes
            
        # Set cache headers
        patch_response_headers(response, timeout)
        
        # Generate cache key based on user ID and URL
        if hasattr(request, 'user') and request.user.is_authenticated:
            cache_key = f'user_{request.user.id}_{request.path}'
            
            # Store in cache
            cache.set(cache_key, response.content, timeout)
            
        return response