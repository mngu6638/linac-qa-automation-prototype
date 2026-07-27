from django.core.management.base import BaseCommand
from QAID_Manager.models import QARecord, QASchedule, QAStatus, Linac
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Sync existing QA records with QA schedule system'

    def handle(self, *args, **options):
        # Get QA statuses
        passed_status = QAStatus.objects.filter(name='passed').first()
        failed_status = QAStatus.objects.filter(name='failed').first()
        
        if not passed_status or not failed_status:
            self.stdout.write(
                self.style.ERROR('QA statuses not found. Please run setup_qa_statuses first.')
            )
            return
        
        # Get all QA records
        qa_records = QARecord.objects.all()
        
        created_count = 0
        updated_count = 0
        
        for qa_record in qa_records:
            # Check if a schedule already exists for this QA record
            existing_schedule = QASchedule.objects.filter(
                linac=qa_record.linac,
                scheduled_date=qa_record.date_performed
            ).first()
            
            if existing_schedule:
                # Update existing schedule with QA record data
                if qa_record.performed_by:
                    existing_schedule.performer1 = qa_record.performed_by
                
                # Determine status based on notes
                if qa_record.notes:
                    if "All tests within tolerance" in qa_record.notes:
                        existing_schedule.status = passed_status
                    elif "results out of tolerances" in qa_record.notes:
                        existing_schedule.status = failed_status
                
                existing_schedule.save()
                updated_count += 1
                self.stdout.write(f'Updated schedule for {qa_record.linac.name} on {qa_record.date_performed}')
            else:
                # Create new schedule from QA record
                schedule = QASchedule.objects.create(
                    linac=qa_record.linac,
                    scheduled_date=qa_record.date_performed,
                    performer1=qa_record.performed_by,
                    is_manual=True,
                    qa_reason='Migrated from existing QA record'
                )
                
                # Determine status based on notes
                if qa_record.notes:
                    if "All tests within tolerance" in qa_record.notes:
                        schedule.status = passed_status
                    elif "results out of tolerances" in qa_record.notes:
                        schedule.status = failed_status
                
                schedule.save()
                created_count += 1
                self.stdout.write(f'Created schedule for {qa_record.linac.name} on {qa_record.date_performed}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully synced QA records: {created_count} created, {updated_count} updated'
            )
        ) 