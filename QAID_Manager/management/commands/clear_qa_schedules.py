from django.core.management.base import BaseCommand
from QAID_Manager.models import QASchedule


class Command(BaseCommand):
    help = 'Clear all QA schedules from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all QA schedules',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL QA schedules from the database. '
                    'Use --confirm to proceed.'
                )
            )
            return

        # Count existing schedules
        schedule_count = QASchedule.objects.count()
        
        if schedule_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No QA schedules found in database.')
            )
            return

        # Delete all schedules
        QASchedule.objects.all().delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {schedule_count} QA schedule(s) from database.'
            )
        ) 