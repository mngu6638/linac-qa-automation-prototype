from django.core.management.base import BaseCommand
from QAID_Manager.models import QAStatus


class Command(BaseCommand):
    help = 'Set up default QA statuses'

    def handle(self, *args, **options):
        # Define default QA statuses
        statuses = [
            ('scheduled', '#6c757d', 'QA session is scheduled but not yet performed'),
            ('in_progress', '#ffc107', 'QA session is currently being performed'),
            ('completed', '#17a2b8', 'QA session is completed but not yet evaluated'),
            ('passed', '#28a745', 'QA passed - all tests within tolerance'),
            ('minor_service', '#ff6b6b', 'QA completed but needs minor service'),
            ('major_service', '#dc3545', 'QA completed but needs major service'),
            ('failed', '#ff6b6b', 'QA failed - tests out of tolerance'),
        ]
        
        created_count = 0
        for status_name, color, description in statuses:
            status, created = QAStatus.objects.get_or_create(
                name=status_name,
                defaults={
                    'color': color,
                    'description': description
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created status: {status_name}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} QA statuses')
        ) 