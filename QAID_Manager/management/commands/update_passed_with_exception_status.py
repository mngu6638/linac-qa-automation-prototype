from django.core.management.base import BaseCommand
from QAID_Manager.models import QAStatus


class Command(BaseCommand):
    help = 'Update "passed_with_exception" status to show "Passed with Deviation"'

    def handle(self, *args, **options):
        # Find the existing status
        existing_status = QAStatus.objects.filter(name='passed_with_exception').first()
        
        if not existing_status:
            self.stdout.write(
                self.style.ERROR('Status "passed_with_exception" not found. Please run add_passed_with_exception_status first.')
            )
            return
        
        # Update the status
        existing_status.description = 'QA passed but with deviations (manually accepted failed QA)'
        existing_status.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated status: {existing_status.name} - {existing_status.get_name_display()}')
        )
