from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from servers.models import ServerConnection
from datetime import timedelta

class Command(BaseCommand):
    help = 'Cleans up expired server sessions and connections'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days of inactivity after which to consider a connection expired'
        )
        
    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(self.style.NOTICE(f'Looking for connections inactive since {cutoff_date}'))
        
        with transaction.atomic():
            # Find expired connections
            expired_connections = ServerConnection.objects.filter(
                last_activity__lt=cutoff_date,
                is_active=True
            )
            
            count = expired_connections.count()
            
            if count > 0:
                # Mark connections as inactive
                expired_connections.update(is_active=False)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully cleaned up {count} expired connections')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('No expired connections found')
                )