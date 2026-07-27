from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import calendar
from QAID_Manager.models import QASchedule, Linac


class Command(BaseCommand):
    help = 'Set expected QA dates for each LINAC based on hardcoded Saturday dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            default=timezone.now().year,
            help='Year to set expected dates for (default: current year)'
        )
        parser.add_argument(
            '--month',
            type=int,
            default=timezone.now().month,
            help='Month to set expected dates for (default: current month)'
        )

    def handle(self, *args, **options):
        year = options['year']
        month = options['month']
        
        self.stdout.write(f'🔧 Setting expected QA dates for {calendar.month_name[month]} {year}...')
        
        # Get the first day of the month
        first_day = date(year, month, 1)
        
        # Find the first Saturday of the month
        first_saturday = first_day + timedelta(days=(5 - first_day.weekday()) % 7)
        
        # Get all active LINACs ordered by name
        active_linacs = Linac.objects.filter(is_active=True).order_by('name')
        
        updated_count = 0
        
        # Calculate how many Saturdays are available in this month
        last_day = date(year, month, 1).replace(day=28) + timedelta(days=4)
        last_day = last_day.replace(day=1) - timedelta(days=1)  # Last day of the month
        
        # Find the last Saturday of the month
        last_saturday = last_day - timedelta(days=(last_day.weekday() - 5) % 7)
        
        # Count how many Saturdays are in this month
        saturdays_in_month = 0
        current_saturday = first_saturday
        while current_saturday <= last_saturday:
            saturdays_in_month += 1
            current_saturday += timedelta(weeks=1)
        
        self.stdout.write(f'📅 Found {saturdays_in_month} Saturdays in {calendar.month_name[month]} {year}')
        
        # Create a list of all available Saturdays in the month
        available_saturdays = []
        current_saturday = first_saturday
        while current_saturday <= last_saturday:
            available_saturdays.append(current_saturday)
            current_saturday += timedelta(weeks=1)
        
        for index, linac in enumerate(active_linacs, 1):
            # Calculate which Saturday to use (cycle through available Saturdays)
            saturday_index = (index - 1) % len(available_saturdays)
            expected_date = available_saturdays[saturday_index]
            
            # Get or create the schedule for this month
            schedule, created = QASchedule.objects.get_or_create(
                linac=linac,
                month_year=first_day,
                defaults={
                    'expected_qa_date': expected_date,
                    'qa_reason': f'Monthly QA for {linac.name}'
                }
            )
            
            if not created:
                # Update existing schedule
                schedule.expected_qa_date = expected_date
                schedule.save()
            
            # Determine which Saturday this is (1st, 2nd, 3rd, etc.)
            saturday_number = saturday_index + 1
            saturday_ordinal = f"{saturday_number}{'st' if saturday_number == 1 else 'nd' if saturday_number == 2 else 'rd' if saturday_number == 3 else 'th'}"
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {linac.name}: Expected QA date set to {expected_date.strftime("%B %d, %Y")} ({saturday_ordinal} Saturday)'
                )
            )
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Successfully set expected QA dates for {updated_count} LINACs'
            )
        )
