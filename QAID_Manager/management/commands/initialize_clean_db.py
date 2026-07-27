"""
Management command to initialize a clean database for QAID Manager.
This keeps universal data (Physics Parameters, QA Tests, Vietnamese Holidays, Organization Settings)
but removes department-specific data (LINACs, Dosimeters, Users, QA Records, etc.)
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from django.db import transaction
from QAID_Manager.models import (
    PhysicsParameters, QATest, VietnameseHoliday, OrganizationSettings,
    Linac, Dosimeter, QARecord, QASchedule, UserProfile, UserActivity,
    QAFilmAnalysis, QATestNote, FilmUpload,
    DoseCalculation, DosimeterDocument, LinacDocument
)
import os
import tempfile
from pathlib import Path

from QAID_Manager.bootstrap_credentials import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_EMAIL,
)

class Command(BaseCommand):
    help = 'Initialize clean database with universal data only'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-org-settings',
            action='store_true',
            help='Keep current organization settings (logo, images, template)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='',
            help='Optional explicit password for recreated admin user.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('=' * 60)
        self.stdout.write('Initializing Clean Database')
        self.stdout.write('=' * 60)
        
        # Step 0: Export universal data first (before any deletions)
        self.stdout.write('\n[0/7] Exporting universal data...')
        temp_dir = Path(tempfile.gettempdir())
        universal_data_file = temp_dir / 'qaid_universal_data.json'
        
        try:
            # Export universal data to temporary file with UTF-8 encoding
            # Use --output flag which handles encoding properly
            call_command(
                'dumpdata',
                'QAID_Manager.PhysicsParameters',
                'QAID_Manager.QATest',
                'QAID_Manager.VietnameseHoliday',
                '--indent', '2',
                '--output', str(universal_data_file),
                verbosity=0
            )
            # Ensure file is written with UTF-8 encoding
            # Read and rewrite with explicit UTF-8 encoding if needed
            try:
                with open(str(universal_data_file), 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(str(universal_data_file), 'w', encoding='utf-8') as f:
                    f.write(content)
            except UnicodeDecodeError:
                # If file was written with wrong encoding, try to fix it
                pass
            physics_count = PhysicsParameters.objects.count()
            test_count = QATest.objects.count()
            holiday_count = VietnameseHoliday.objects.count()
            self.stdout.write(f'   - Exported {physics_count} Physics Parameters')
            self.stdout.write(f'   - Exported {test_count} QA Tests')
            self.stdout.write(f'   - Exported {holiday_count} Vietnamese Holidays')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   - Warning: Could not export universal data: {e}'))
            universal_data_file = None
        
        # Step 1: Remove department-specific data
        self.stdout.write('\n[1/7] Removing department-specific data...')
        
        # Remove related data first (foreign key constraints)
        film_count = QAFilmAnalysis.objects.count()
        QAFilmAnalysis.objects.all().delete()
        self.stdout.write(f'   - Removed {film_count} Film Analyses')
        
        test_note_count = QATestNote.objects.count()
        QATestNote.objects.all().delete()
        self.stdout.write(f'   - Removed {test_note_count} Test Notes')
        
        film_upload_count = FilmUpload.objects.count()
        FilmUpload.objects.all().delete()
        self.stdout.write(f'   - Removed {film_upload_count} Film Uploads')
        
        dose_calc_count = DoseCalculation.objects.count()
        DoseCalculation.objects.all().delete()
        self.stdout.write(f'   - Removed {dose_calc_count} Dose Calculations')
        
        # Remove QA Records and related data
        # First, clear qa_schedule references to avoid foreign key issues
        QARecord.objects.all().update(qa_schedule=None)
        qa_count = QARecord.objects.count()
        QARecord.objects.all().delete()
        self.stdout.write(f'   - Removed {qa_count} QA Records')
        
        # Remove QASchedules (must be after QA Records to avoid foreign key issues)
        schedule_count = QASchedule.objects.count()
        # Delete schedules that reference non-existent LINACs first (safety)
        orphaned_schedules = QASchedule.objects.filter(linac__isnull=True)
        orphaned_count = orphaned_schedules.count()
        if orphaned_count > 0:
            orphaned_schedules.delete()
            self.stdout.write(f'   - Removed {orphaned_count} orphaned QA Schedules')
        # Delete all remaining schedules
        QASchedule.objects.all().delete()
        self.stdout.write(f'   - Removed {schedule_count} QA Schedules (total)')
        
        # Remove LINAC documents
        linac_doc_count = LinacDocument.objects.count()
        LinacDocument.objects.all().delete()
        self.stdout.write(f'   - Removed {linac_doc_count} LINAC Documents')
        
        # Remove LINACs
        linac_count = Linac.objects.count()
        Linac.objects.all().delete()
        self.stdout.write(f'   - Removed {linac_count} LINACs')
        
        # Remove Dosimeter documents
        dosimeter_doc_count = DosimeterDocument.objects.count()
        DosimeterDocument.objects.all().delete()
        self.stdout.write(f'   - Removed {dosimeter_doc_count} Dosimeter Documents')
        
        # Remove Dosimeters
        dosimeter_count = Dosimeter.objects.count()
        Dosimeter.objects.all().delete()
        self.stdout.write(f'   - Removed {dosimeter_count} Dosimeters')
        
        # Remove User Activities
        activity_count = UserActivity.objects.count()
        UserActivity.objects.all().delete()
        self.stdout.write(f'   - Removed {activity_count} User Activities')
        
        # Step 2: Clear universal data ONLY if we successfully exported it
        # If export failed, keep the existing data to prevent data loss
        self.stdout.write('\n[2/7] Clearing universal data tables...')
        
        if universal_data_file and universal_data_file.exists():
            # Only clear if we have a backup to restore
            physics_count = PhysicsParameters.objects.count()
            test_count = QATest.objects.count()
            holiday_count = VietnameseHoliday.objects.count()
            PhysicsParameters.objects.all().delete()
            QATest.objects.all().delete()
            VietnameseHoliday.objects.all().delete()
            self.stdout.write(f'   - Cleared {physics_count} Physics Parameters')
            self.stdout.write(f'   - Cleared {test_count} QA Tests')
            self.stdout.write(f'   - Cleared {holiday_count} Vietnamese Holidays')
        else:
            # Keep existing data if export failed
            physics_count = PhysicsParameters.objects.count()
            test_count = QATest.objects.count()
            holiday_count = VietnameseHoliday.objects.count()
            self.stdout.write(self.style.WARNING(f'   - Keeping existing universal data (export failed): Physics={physics_count}, Tests={test_count}, Holidays={holiday_count}'))
        
        # Step 3: Re-import universal data
        self.stdout.write('\n[3/7] Re-importing universal data...')
        if universal_data_file and universal_data_file.exists():
            try:
                call_command(
                    'loaddata',
                    str(universal_data_file),
                    verbosity=0
                )
                physics_count = PhysicsParameters.objects.count()
                test_count = QATest.objects.count()
                holiday_count = VietnameseHoliday.objects.count()
                self.stdout.write(f'   - Re-imported {physics_count} Physics Parameters')
                self.stdout.write(f'   - Re-imported {test_count} QA Tests')
                self.stdout.write(f'   - Re-imported {holiday_count} Vietnamese Holidays')
                # Clean up temp file
                try:
                    universal_data_file.unlink()
                except:
                    pass
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   - Error re-importing universal data: {e}'))
                self.stdout.write(self.style.WARNING('   - Universal data was cleared but could not be restored. Please restore from backup.'))
        else:
            self.stdout.write(self.style.WARNING('   - No universal data file found, keeping existing data'))
        
        # Step 4: Handle Organization Settings
        self.stdout.write('\n[4/7] Handling Organization Settings...')
        if options['keep_org_settings']:
            org_settings = OrganizationSettings.get_settings()
            self.stdout.write('   - Keeping current organization settings')
        else:
            # Reset to defaults but keep the structure
            org_settings = OrganizationSettings.get_settings()
            org_settings.organization_name = "Demo Radiotherapy Physics Department"
            # Clear image fields but keep structure
            org_settings.logo = None
            org_settings.left_side_image = None
            org_settings.bottom_image = None
            org_settings.report_template = None
            org_settings.save()
            self.stdout.write('   - Reset organization settings to defaults')
        
        # Step 5: Remove all users except we'll create admin
        self.stdout.write('\n[5/7] Removing existing users...')
        user_count = User.objects.count()
        # Delete user profiles first (import already at top, but ensure it's available)
        from QAID_Manager.models import UserProfile
        UserProfile.objects.all().delete()
        # Then delete users
        User.objects.all().delete()
        self.stdout.write(f'   - Removed {user_count} users')
        
        # Step 6: Create demo admin user (public prototype only)
        self.stdout.write('\n[6/7] Creating demo admin user...')
        admin_password = (
            options.get('admin_password')
            or os.environ.get('QAID_DEFAULT_ADMIN_PASSWORD', '').strip()
            or DEFAULT_ADMIN_PASSWORD
        )
        admin_user = User.objects.create_user(
            username=DEFAULT_ADMIN_USERNAME,
            password=admin_password,
            is_staff=True,
            is_superuser=True,
            email=DEFAULT_ADMIN_EMAIL,
        )
        self.stdout.write(
            f'   - Created demo admin user (username: {DEFAULT_ADMIN_USERNAME}). '
            'Change the password before any shared use.'
        )
        
        # Create user profile for admin
        from QAID_Manager.models import UserProfile
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'role': 'admin'}
        )
        
        # Step 7: Verify cleanup
        self.stdout.write('\n[7/7] Verifying cleanup...')
        remaining_linacs = Linac.objects.count()
        remaining_dosimeters = Dosimeter.objects.count()
        remaining_users = User.objects.count()
        remaining_qa = QARecord.objects.count()
        remaining_schedules = QASchedule.objects.count()
        
        if (remaining_linacs == 0 and remaining_dosimeters == 0 and 
            remaining_users == 1 and remaining_qa == 0 and remaining_schedules == 0):
            self.stdout.write('   [OK] Cleanup verified successfully')
            self.stdout.write('   [OK] All department-specific data removed')
        else:
            self.stdout.write(f'   [WARNING] Some data remains:')
            self.stdout.write(f'      - LINACs: {remaining_linacs}')
            self.stdout.write(f'      - Dosimeters: {remaining_dosimeters}')
            self.stdout.write(f'      - Users: {remaining_users} (should be 1)')
            self.stdout.write(f'      - QA Records: {remaining_qa}')
            self.stdout.write(f'      - QA Schedules: {remaining_schedules}')
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('Database initialization completed!')
        self.stdout.write('=' * 60)
        self.stdout.write('\nDemo admin credentials:')
        self.stdout.write(f'  Username: {DEFAULT_ADMIN_USERNAME}')
        self.stdout.write('  Password: (set via --admin-password, QAID_DEFAULT_ADMIN_PASSWORD, or demo default)')
        self.stdout.write('  Change the password before any shared use.')
        self.stdout.write('\nUniversal data preserved:')
        self.stdout.write(f'  - {physics_count} Physics Parameters')
        self.stdout.write(f'  - {test_count} QA Tests')
        self.stdout.write(f'  - {holiday_count} Holidays')
        self.stdout.write('  - Organization Settings')
        self.stdout.write('\n')
