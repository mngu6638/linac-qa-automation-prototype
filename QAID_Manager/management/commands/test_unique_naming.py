from django.core.management.base import BaseCommand
from django.conf import settings
from QAID_Manager.models import Linac, QARecord, QAFilmAnalysis
from QAID_Manager.services import QAService
import os
import uuid
from datetime import datetime

class Command(BaseCommand):
    help = 'Test the unique naming system for film analysis images'

    def handle(self, *args, **options):
        self.stdout.write('Testing unique naming system...')
        
        # Get or create a test LINAC
        linac, created = Linac.objects.get_or_create(name='TEST_LINAC')
        if created:
            self.stdout.write(f'Created test LINAC: {linac.name}')
        
        # Create a test QA record
        qa_record = QARecord.objects.create(
            linac=linac,
            performed_by=None,  # No user for test
            notes='Test QA record for unique naming'
        )
        
        self.stdout.write(f'Created test QA record: {qa_record.id}')
        
        # Test unique filename generation
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        
        # Test different analysis types
        test_analyses = [
            ('fieldsize', 'fieldsize_analysis_result'),
            ('collimator_isocenter', 'collimator_analysis_result'),
            ('gantry_isocenter', 'gantry_analysis_result')
        ]
        
        for analysis_type, base_filename in test_analyses:
            # Generate unique filename
            new_filename = f"{analysis_type}_{qa_record.linac.name}_{timestamp}_{unique_id}.png"
            self.stdout.write(f'Generated filename for {analysis_type}: {new_filename}')
            
            # Create a dummy file for testing
            test_file_path = os.path.join(settings.MEDIA_ROOT, 'film_uploads', f'{base_filename}_{timestamp}_{unique_id}.png')
            
            # Create a simple test image (1x1 pixel)
            from PIL import Image
            test_img = Image.new('RGB', (100, 100), color='red')
            test_img.save(test_file_path)
            
            # Create database record
            film_analysis = QAFilmAnalysis.objects.create(
                qa_record=qa_record,
                analysis_type=analysis_type,
                result_image=f'qa_results/{new_filename}'
            )
            
            self.stdout.write(f'Created {analysis_type} analysis record: {film_analysis.id}')
        
        # Test the get_film_analysis_images method
        film_analyses = QAService.get_film_analysis_images()
        self.stdout.write(f'Found {len(film_analyses)} film analyses: {list(film_analyses.keys())}')
        
        # Test the get_qa_record_film_analyses method
        qa_film_analyses = QAService.get_qa_record_film_analyses(qa_record)
        self.stdout.write(f'QA record has {len(qa_film_analyses)} film analyses: {list(qa_film_analyses.keys())}')
        
        # Clean up test data
        qa_record.delete()
        linac.delete()
        
        # Clean up test files
        for base_filename in ['fieldsize_analysis_result', 'collimator_analysis_result', 'gantry_analysis_result']:
            test_file = os.path.join(settings.MEDIA_ROOT, 'film_uploads', f'{base_filename}_{timestamp}_{unique_id}.png')
            if os.path.exists(test_file):
                os.remove(test_file)
                self.stdout.write(f'Cleaned up: {test_file}')
        
        self.stdout.write(self.style.SUCCESS('Unique naming system test completed successfully!')) 