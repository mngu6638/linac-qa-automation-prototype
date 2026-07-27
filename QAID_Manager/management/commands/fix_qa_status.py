from django.core.management.base import BaseCommand
from QAID_Manager.models import QARecord, QAStatus

class Command(BaseCommand):
    help = 'Fix QA records status by assigning default status to records without status'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Fixing QA Records Status...')
        
        # Get or create a default status
        default_status, created = QAStatus.objects.get_or_create(
            name='completed',
            defaults={
                'color': '#28a745',
                'description': 'QA completed successfully'
            }
        )
        
        if created:
            self.stdout.write(f'✅ Created default status: {default_status.name}')
        else:
            self.stdout.write(f'📋 Using existing status: {default_status.name}')
        
        # Count records without status
        records_without_status = QARecord.objects.filter(status__isnull=True).count()
        self.stdout.write(f'📊 Records without status: {records_without_status}')
        
        if records_without_status == 0:
            self.stdout.write('✅ All records already have status assigned')
            return
        
        # Update all records without status
        updated_count = QARecord.objects.filter(status__isnull=True).update(status=default_status)
        self.stdout.write(f'✅ Updated {updated_count} records with default status')
        
        # Verify the fix
        remaining_without_status = QARecord.objects.filter(status__isnull=True).count()
        self.stdout.write(f'📊 Remaining records without status: {remaining_without_status}')
        
        if remaining_without_status == 0:
            self.stdout.write(self.style.SUCCESS('🎉 All QA records now have status assigned!'))
            self.stdout.write('💡 You should now be able to see QA records in the admin interface.')
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ {remaining_without_status} records still without status')) 