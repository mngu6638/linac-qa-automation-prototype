from django.core.management.base import BaseCommand
from QAID_Manager.models import QATest

class Command(BaseCommand):
    help = 'Set up default QA tests with tolerances'

    def handle(self, *args, **options):
        # Default QA tests with tolerances
        default_tests = [
            # Mechanical Tests
            {
                'name': 'Kích thước trường ánh sáng (đối xứng và bất đối xứng)',
                'test_type': 'mechanical',
                'description': 'Kiểm tra kích thước trường ánh sáng',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 1
            },
            {
                'name': 'Góc quay bộ chuẩn trực (collimator)',
                'test_type': 'mechanical',
                'description': 'Kiểm tra góc quay collimator',
                'tolerance_value': 1.0,
                'tolerance_unit': 'độ',
                'order_index': 2
            },
            {
                'name': 'Góc quay bàn điều trị',
                'test_type': 'mechanical',
                'description': 'Kiểm tra góc quay bàn điều trị',
                'tolerance_value': 1.0,
                'tolerance_unit': 'độ',
                'order_index': 3
            },
            {
                'name': 'Độ chính xác trong chuyển động của Bàn điều trị',
                'test_type': 'mechanical',
                'description': 'Kiểm tra độ chính xác chuyển động bàn',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 4
            },
            {
                'name': 'Góc quay thân máy (gantry)',
                'test_type': 'mechanical',
                'description': 'Kiểm tra góc quay gantry',
                'tolerance_value': 1.0,
                'tolerance_unit': 'độ',
                'order_index': 5
            },
            {
                'name': 'Độ chính xác của chùm laser tại điểm đồng tâm',
                'test_type': 'mechanical',
                'description': 'Kiểm tra độ chính xác laser',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 6
            },
            {
                'name': 'Độ chính xác của ODI',
                'test_type': 'mechanical',
                'description': 'Kiểm tra độ chính xác ODI',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 7
            },
            
            # Isocenter Tests
            {
                'name': 'Tâm dây chữ thập',
                'test_type': 'isocenter',
                'description': 'Kiểm tra tâm dây chữ thập',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 8
            },
            {
                'name': 'Đồng tâm quay collimator',
                'test_type': 'isocenter',
                'description': 'Kiểm tra đồng tâm quay collimator',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 9
            },
            {
                'name': 'Đồng tâm quay bàn điều trị',
                'test_type': 'isocenter',
                'description': 'Kiểm tra đồng tâm quay bàn điều trị',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 10
            },
            {
                'name': 'Đồng tâm quay gantry',
                'test_type': 'isocenter',
                'description': 'Kiểm tra đồng tâm quay gantry',
                'tolerance_value': 2.0,
                'tolerance_unit': 'mm',
                'order_index': 11
            },
            
            # Film Tests
            {
                'name': 'Độ trùng tâm của các trường xạ tạo bởi MLC khi quay thân máy',
                'test_type': 'film',
                'description': 'Kiểm tra độ trùng tâm MLC',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 12
            },
            {
                'name': 'Độ trùng tâm của các trường xạ khi quay bộ chuẩn trực đa lá',
                'test_type': 'film',
                'description': 'Kiểm tra độ trùng tâm collimator',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 13
            },
            {
                'name': 'Độ trùng khít của kích thước trường xạ và trường sáng',
                'test_type': 'film',
                'description': 'Kiểm tra độ trùng khít trường xạ',
                'tolerance_value': 1.0,
                'tolerance_unit': 'mm',
                'order_index': 14
            },
            
            # Beam Tests
            {
                'name': 'Liều tuyệt đối',
                'test_type': 'beam',
                'description': 'Kiểm tra liều tuyệt đối',
                'tolerance_value': 2.0,
                'tolerance_unit': '%',
                'order_index': 15
            },
            {
                'name': 'Sự ổn định của năng lượng (D10)',
                'test_type': 'beam',
                'description': 'Kiểm tra ổn định năng lượng',
                'tolerance_value': 1.0,
                'tolerance_unit': '%',
                'order_index': 16
            },
            {
                'name': 'Tính đối xứng so với giá trị tại thời điểm commissioning',
                'test_type': 'beam',
                'description': 'Kiểm tra tính đối xứng',
                'tolerance_value': 3.0,
                'tolerance_unit': '%',
                'order_index': 17
            },
            {
                'name': 'Tính phẳng so với giá trị tại thời điểm commissioning',
                'test_type': 'beam',
                'description': 'Kiểm tra tính phẳng',
                'tolerance_value': 3.0,
                'tolerance_unit': '%',
                'order_index': 18
            },
            {
                'name': 'Tính tuyến tính của liều và số MU',
                'test_type': 'beam',
                'description': 'Kiểm tra tính tuyến tính',
                'tolerance_value': 1.0,
                'tolerance_unit': '%',
                'order_index': 19
            },
            {
                'name': 'Hệ số liều lối ra theo kích thước trường chiếu',
                'test_type': 'beam',
                'description': 'Kiểm tra hệ số liều lối ra',
                'tolerance_value': 2.0,
                'tolerance_unit': '%',
                'order_index': 20
            },
        ]
        
        created_count = 0
        for test_data in default_tests:
            test, created = QATest.objects.get_or_create(
                name=test_data['name'],
                defaults=test_data
            )
            if created:
                created_count += 1
                self.stdout.write(f"Created test: {test.name}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} QA tests')
        ) 