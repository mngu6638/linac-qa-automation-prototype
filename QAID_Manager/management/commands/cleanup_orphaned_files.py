from django.core.management.base import BaseCommand
from django.conf import settings
from QAID_Manager.models import QAFilmAnalysis
import os
import glob

class Command(BaseCommand):
    help = 'Clean up orphaned files in qa_results directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qa_results_dir = os.path.join(settings.MEDIA_ROOT, 'qa_results')
        
        if not os.path.exists(qa_results_dir):
            self.stdout.write(self.style.WARNING(f'Directory {qa_results_dir} does not exist'))
            return

        # Get all files in qa_results directory
        all_files = glob.glob(os.path.join(qa_results_dir, '*'))
        
        # Get all files referenced in database
        db_files = set()
        for analysis in QAFilmAnalysis.objects.all():
            if analysis.result_image:
                db_files.add(analysis.result_image.path)

        # Find orphaned files
        orphaned_files = []
        for file_path in all_files:
            if os.path.isfile(file_path) and file_path not in db_files:
                orphaned_files.append(file_path)

        if not orphaned_files:
            self.stdout.write(self.style.SUCCESS('No orphaned files found'))
            return

        self.stdout.write(f'Found {len(orphaned_files)} orphaned files:')
        for file_path in orphaned_files:
            file_size = os.path.getsize(file_path)
            self.stdout.write(f'  {os.path.basename(file_path)} ({file_size} bytes)')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No files were deleted'))
        else:
            # Ask for confirmation
            response = input('\nDo you want to delete these files? (yes/no): ')
            if response.lower() == 'yes':
                deleted_count = 0
                for file_path in orphaned_files:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        self.stdout.write(f'Deleted: {os.path.basename(file_path)}')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error deleting {file_path}: {e}'))
                
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} files'))
            else:
                self.stdout.write(self.style.WARNING('Operation cancelled')) 