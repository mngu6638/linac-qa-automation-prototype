from django.core.management.base import BaseCommand
from QAID_Manager.models import VietnameseHoliday
from datetime import date


class Command(BaseCommand):
    help = 'Populate Vietnamese holidays for testing'

    def handle(self, *args, **options):
        # Vietnamese holidays for 2024, 2025, 2026, and 2027
        holidays_2024 = [
            ('Tết Dương lịch', date(2024, 1, 1), 'national'),
            ('Tết Nguyên đán', date(2024, 2, 10), 'national'),
            ('Tết Nguyên đán', date(2024, 2, 11), 'national'),
            ('Tết Nguyên đán', date(2024, 2, 12), 'national'),
            ('Giỗ tổ Hùng Vương', date(2024, 4, 18), 'national'),
            ('Giải phóng miền Nam', date(2024, 4, 30), 'national'),
            ('Quốc tế Lao động', date(2024, 5, 1), 'national'),
            ('Quốc khánh', date(2024, 9, 2), 'national'),
            ('Tết Trung thu', date(2024, 9, 17), 'national'),
        ]
        
        holidays_2025 = [
            ('Tết Dương lịch', date(2025, 1, 1), 'national'),
            ('Tết Nguyên đán', date(2025, 1, 29), 'national'),
            ('Tết Nguyên đán', date(2025, 1, 30), 'national'),
            ('Tết Nguyên đán', date(2025, 1, 31), 'national'),
            ('Giỗ tổ Hùng Vương', date(2025, 4, 7), 'national'),
            ('Giải phóng miền Nam', date(2025, 4, 30), 'national'),
            ('Quốc tế Lao động', date(2025, 5, 1), 'national'),
            ('Quốc khánh', date(2025, 9, 2), 'national'),
            ('Tết Trung thu', date(2025, 10, 6), 'national'),
        ]
        
        holidays_2026 = [
            ('Tết Dương lịch', date(2026, 1, 1), 'national'),
            ('Tết Nguyên đán', date(2026, 2, 17), 'national'),
            ('Tết Nguyên đán', date(2026, 2, 18), 'national'),
            ('Tết Nguyên đán', date(2026, 2, 19), 'national'),
            ('Giỗ tổ Hùng Vương', date(2026, 3, 28), 'national'),
            ('Giải phóng miền Nam', date(2026, 4, 30), 'national'),
            ('Quốc tế Lao động', date(2026, 5, 1), 'national'),
            ('Quốc khánh', date(2026, 9, 2), 'national'),
            ('Tết Trung thu', date(2026, 9, 25), 'national'),
        ]
        
        holidays_2027 = [
            ('Tết Dương lịch', date(2027, 1, 1), 'national'),
            ('Tết Nguyên đán', date(2027, 2, 6), 'national'),
            ('Tết Nguyên đán', date(2027, 2, 7), 'national'),
            ('Tết Nguyên đán', date(2027, 2, 8), 'national'),
            ('Giỗ tổ Hùng Vương', date(2027, 4, 16), 'national'),
            ('Giải phóng miền Nam', date(2027, 4, 30), 'national'),
            ('Quốc tế Lao động', date(2027, 5, 1), 'national'),
            ('Quốc khánh', date(2027, 9, 2), 'national'),
            ('Tết Trung thu', date(2027, 10, 4), 'national'),
        ]
        
        all_holidays = holidays_2024 + holidays_2025 + holidays_2026 + holidays_2027
        
        created_count = 0
        for name, holiday_date, holiday_type in all_holidays:
            holiday, created = VietnameseHoliday.objects.get_or_create(
                date=holiday_date,
                defaults={
                    'name': name,
                    'holiday_type': holiday_type,
                    'description': f'{name} - Vietnamese National Holiday',
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created holiday: {name} on {holiday_date}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} Vietnamese holidays')
        ) 