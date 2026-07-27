from django.core.management.base import BaseCommand
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up all uploaded files in uploads directory to prevent storage bloat'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt and delete files immediately',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        # Define the upload directories to clean
        upload_dirs = [
            os.path.join(settings.MEDIA_ROOT, 'film_uploads'),
            os.path.join(settings.MEDIA_ROOT, 'qa_results'),
        ]
        
        total_files_found = 0
        total_size_found = 0
        
        # First, scan and show what would be deleted
        for upload_dir in upload_dirs:
            if os.path.exists(upload_dir):
                self.stdout.write(f"📁 Scanning directory: {upload_dir}")
                files_in_dir = 0
                size_in_dir = 0
                
                for filename in os.listdir(upload_dir):
                    file_path = os.path.join(upload_dir, filename)
                    
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        files_in_dir += 1
                        size_in_dir += file_size
                        total_files_found += 1
                        total_size_found += file_size
                        
                        self.stdout.write(f"  📄 {filename} ({file_size} bytes)")
                
                self.stdout.write(f"  📊 Found {files_in_dir} files ({size_in_dir} bytes) in {upload_dir}")
            else:
                self.stdout.write(f"⚠️ Directory does not exist: {upload_dir}")
        
        if total_files_found == 0:
            self.stdout.write(self.style.SUCCESS('No files found to clean up'))
            return
        
        # Show summary
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"  Total files: {total_files_found}")
        self.stdout.write(f"  Total size: {total_size_found} bytes ({total_size_found / 1024 / 1024:.2f} MB)")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🧹 DRY RUN - No files would be deleted'))
            return
        
        # Ask for confirmation (unless --force is used)
        if not force:
            self.stdout.write(f"\n⚠️ This will permanently delete {total_files_found} files ({total_size_found / 1024 / 1024:.2f} MB)")
            response = input('Do you want to proceed? (yes/no): ')
            if response.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform the cleanup
        total_files_removed = 0
        total_size_removed = 0
        
        for upload_dir in upload_dirs:
            if os.path.exists(upload_dir):
                self.stdout.write(f"\n🧹 Cleaning up directory: {upload_dir}")
                files_removed = 0
                size_removed = 0
                
                for filename in os.listdir(upload_dir):
                    file_path = os.path.join(upload_dir, filename)
                    
                    if os.path.isfile(file_path):
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            files_removed += 1
                            size_removed += file_size
                            total_files_removed += 1
                            total_size_removed += file_size
                            
                            self.stdout.write(f"  🗑️ Removed: {filename} ({file_size} bytes)")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  ❌ Failed to remove {filename}: {e}"))
                            logger.error(f"Failed to remove file {filename}: {e}")
                
                self.stdout.write(f"  ✅ Cleaned up {files_removed} files ({size_removed} bytes) from {upload_dir}")
        
        # Final summary
        self.stdout.write(f"\n🎉 Cleanup complete!")
        self.stdout.write(f"  Files removed: {total_files_removed}")
        self.stdout.write(f"  Space freed: {total_size_removed} bytes ({total_size_removed / 1024 / 1024:.2f} MB)")
        
        if total_files_removed != total_files_found:
            self.stdout.write(self.style.WARNING(f"  ⚠️ {total_files_found - total_files_removed} files could not be removed")) 