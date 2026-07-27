from django.core.management.base import BaseCommand
from QAID_Manager.models import QARecord, Linac, QAStatus
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Check admin display and troubleshoot QA records visibility'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Checking QA Records Admin Display...')
        
        # Check total records
        total_records = QARecord.objects.count()
        self.stdout.write(f'📊 Total QA Records: {total_records}')
        
        if total_records == 0:
            self.stdout.write('❌ No QA records found in database')
            return
        
        # Get first few records
        recent_records = QARecord.objects.all()[:5]
        self.stdout.write(f'\n📋 Recent QA Records:')
        
        for record in recent_records:
            self.stdout.write(f'   ID: {record.id}')
            self.stdout.write(f'   LINAC: {record.linac.name if record.linac else "None"}')
            self.stdout.write(f'   Performed By: {record.performed_by.username if record.performed_by else "None"}')
            self.stdout.write(f'   Date: {record.date_performed}')
            self.stdout.write(f'   Status: {record.status.name if record.status else "None"}')
            
            # Check for test values
            test_values = []
            for i in range(1, 21):
                field_name = f'test_{i:02d}'
                value = getattr(record, field_name)
                if value is not None:
                    test_values.append(f'{field_name}: {value}')
            
            if test_values:
                self.stdout.write(f'   Test Values: {", ".join(test_values[:3])}...')
            else:
                self.stdout.write(f'   Test Values: None')
            
            self.stdout.write('   ---')
        
        # Check admin configuration
        self.stdout.write(f'\n🔧 Admin Configuration Check:')
        
        from QAID_Manager.admin import QARecordAdmin
        admin_instance = QARecordAdmin(QARecord, None)
        
        # Test list_display
        self.stdout.write(f'   List Display Fields: {admin_instance.list_display}')
        
        # Test list_filter
        self.stdout.write(f'   List Filter Fields: {admin_instance.list_filter}')
        
        # Test search_fields
        self.stdout.write(f'   Search Fields: {admin_instance.search_fields}')
        
        # Test ordering
        self.stdout.write(f'   Ordering: {admin_instance.ordering}')
        
        # Check if there are any records that should be visible
        visible_records = QARecord.objects.all()
        self.stdout.write(f'\n👁️ Records that should be visible: {visible_records.count()}')
        
        # Check for any potential issues
        self.stdout.write(f'\n⚠️ Potential Issues:')
        
        # Check for records without LINAC
        records_without_linac = QARecord.objects.filter(linac__isnull=True).count()
        if records_without_linac > 0:
            self.stdout.write(f'   Records without LINAC: {records_without_linac}')
        
        # Check for records without performed_by
        records_without_user = QARecord.objects.filter(performed_by__isnull=True).count()
        if records_without_user > 0:
            self.stdout.write(f'   Records without user: {records_without_user}')
        
        # Check for records without status
        records_without_status = QARecord.objects.filter(status__isnull=True).count()
        if records_without_status > 0:
            self.stdout.write(f'   Records without status: {records_without_status}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Admin display check completed!'))
        self.stdout.write('\n💡 Troubleshooting Tips:')
        self.stdout.write('   1. Try refreshing the admin page (Ctrl+F5)')
        self.stdout.write('   2. Check if you have proper permissions')
        self.stdout.write('   3. Try accessing /admin/QAID_Manager/qarecord/ directly')
        self.stdout.write('   4. Check browser console for JavaScript errors') 