from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
import time

class Command(BaseCommand):
    help = 'Clears expired cache entries to free up memory'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force clear all cache entries, not just expired ones'
        )
        
    def handle(self, *args, **options):
        force = options['force']
        
        if force:
            self.stdout.write(self.style.WARNING('Clearing all cache entries (forced)'))
            cache.clear()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all cache entries'))
            return
            
        # For Redis cache, we can't directly clear only expired entries
        # For LocMem cache, expired entries are automatically cleared on access
        # So we'll just report cache statistics
        
        cache_backend = settings.CACHES['default']['BACKEND']
        
        if 'redis' in cache_backend.lower():
            self.stdout.write(self.style.NOTICE(
                'Redis cache backend detected. Redis automatically removes expired keys.\n'
                'To manually clear all cache, use --force option.'
            ))
        elif 'locmem' in cache_backend.lower():
            self.stdout.write(self.style.NOTICE(
                'LocMem cache backend detected. Django automatically removes expired entries on access.\n'
                'To manually clear all cache, use --force option.'
            ))
        else:
            self.stdout.write(self.style.NOTICE(
                f'Unknown cache backend: {cache_backend}\n'
                'To manually clear all cache, use --force option.'
            ))
            
        # Try to get cache statistics if possible
        try:
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_stats'):
                stats = cache._cache.get_stats()
                self.stdout.write(self.style.SUCCESS(f'Cache statistics: {stats}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting cache statistics: {e}'))