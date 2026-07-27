from django.core.management.base import BaseCommand
from QAID_Manager.models import QAStatus


class Command(BaseCommand):
    help = 'Add "Passed with Deviation" status to QAStatus'

    def handle(self, *args, **options):
        # Check if the status already exists
        existing_status = QAStatus.objects.filter(name='passed_with_exception').first()
        
        if existing_status:
            self.stdout.write(
                self.style.WARNING('Status "passed_with_exception" already exists.')
            )
            return
        
        # Create the new status
        new_status = QAStatus.objects.create(
            name='passed_with_exception',
            color='#ffc107',  # Yellow/Orange color
            description='QA passed but with deviations (manually accepted failed QA)'
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created status: {new_status.name}')
        )
