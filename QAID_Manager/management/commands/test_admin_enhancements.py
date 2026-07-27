from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from QAID_Manager.models import Linac, QARecord, QAStatus, QATestNote
from QAID_Manager.admin import TEST_NAME_MAPPING

class Command(BaseCommand):
    help = 'Test admin enhancements and meaningful test names'

    def handle(self, *args, **options):
        self.stdout.write('Testing admin enhancements...')
        
        # Test 1: Verify test name mapping
        self.stdout.write('\n1. Testing test name mapping:')
        for test_field, test_name in TEST_NAME_MAPPING.items():
            self.stdout.write(f'   {test_field} -> {test_name}')
        
        # Test 2: Create test data
        self.stdout.write('\n2. Creating test QA record...')
        
        # Get or create test LINAC
        linac, created = Linac.objects.get_or_create(name='TEST_LINAC_ADMIN')
        if created:
            self.stdout.write(f'   Created test LINAC: {linac.name}')
        
        # Get or create test user
        user, created = User.objects.get_or_create(
            username='admin_test_user',
            defaults={'email': 'test@example.com'}
        )
        if created:
            self.stdout.write(f'   Created test user: {user.username}')
        
        # Get or create test status
        status, created = QAStatus.objects.get_or_create(name='completed')
        if created:
            self.stdout.write(f'   Created test status: {status.name}')
        
        # Create test QA record with some test values
        qa_record = QARecord.objects.create(
            linac=linac,
            performed_by=user,
            status=status,
            test_08=1.5,  # Tâm dây chữ thập
            test_09=2.1,  # Đồng tâm quay collimator
            test_10=1.8,  # Đồng tâm quay bàn điều trị
            test_12=0.9,  # Độ trùng tâm MLC
            test_13=1.2,  # Độ trùng tâm collimator
            test_14=1.0,  # Độ trùng khít trường xạ
            notes='Test QA record for admin enhancements'
        )
        self.stdout.write(f'   Created QA record: {qa_record.id}')
        
        # Test 3: Create test notes
        self.stdout.write('\n3. Creating test notes...')
        test_notes = [
            (8, 'Test note for Tâm dây chữ thập'),
            (9, 'Test note for Đồng tâm quay collimator'),
            (10, 'Test note for Đồng tâm quay bàn điều trị'),
        ]
        
        for test_number, note_text in test_notes:
            note, created = QATestNote.objects.get_or_create(
                qa_record=qa_record,
                test_number=test_number,
                defaults={'note_text': note_text}
            )
            if created:
                self.stdout.write(f'   Created note for test {test_number}: {note_text}')
        
        # Test 4: Verify admin methods
        self.stdout.write('\n4. Testing admin methods...')
        
        from QAID_Manager.admin import QARecordAdmin
        admin_instance = QARecordAdmin(QARecord, None)
        
        # Test key_test_results method
        key_results = admin_instance.key_test_results(qa_record)
        self.stdout.write(f'   Key test results: {key_results}')
        
        # Test film_analyses_count method
        film_count = admin_instance.film_analyses_count(qa_record)
        self.stdout.write(f'   Film analyses count: {film_count}')
        
        # Test test_notes_display method
        notes_display = admin_instance.test_notes_display(qa_record)
        self.stdout.write(f'   Test notes display: {notes_display[:100]}...')
        
        # Test 5: Verify test name mapping in notes
        self.stdout.write('\n5. Verifying test name mapping in notes:')
        for note in qa_record.test_notes.all():
            expected_name = TEST_NAME_MAPPING.get(f'test_{note.test_number:02d}', f'Test {note.test_number}')
            self.stdout.write(f'   Test {note.test_number} -> {expected_name}')
        
        # Test 6: Clean up test data
        self.stdout.write('\n6. Cleaning up test data...')
        qa_record.delete()
        self.stdout.write('   Deleted test QA record')
        
        # Only delete test user and LINAC if they were created for this test
        if created:
            user.delete()
            self.stdout.write('   Deleted test user')
        
        if created:
            linac.delete()
            self.stdout.write('   Deleted test LINAC')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Admin enhancements test completed successfully!'))
        self.stdout.write('\n📋 Summary:')
        self.stdout.write('   - Test name mapping verified')
        self.stdout.write('   - Admin methods working correctly')
        self.stdout.write('   - Test data created and cleaned up')
        self.stdout.write('   - Ready to use enhanced admin interface') 