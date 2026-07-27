"""
Service classes for QAID Manager business logic.

This module contains service classes that encapsulate business logic
for QA operations, user activities, and related functionality.
"""
from django.contrib.auth.models import User
from .models import QARecord, QATest, QAStatus, QASchedule, UserActivity, Linac, QATestNote
from django.core.files import File
from django.utils import timezone
import logging
import os
import glob
import uuid
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

# ============================================================================
# QA Service Class
# ============================================================================

class QAService:
    """
    Service class for QA-related business logic.
    
    Provides static methods for:
    - Retrieving QA tests and tolerances
    - Creating enhanced QA records with film analyses and test notes
    - Storing and retrieving film analysis results
    - Determining QA status based on test results
    """
    
    @staticmethod
    def get_qa_tests_by_type():
        """Get all QA tests organized by type"""
        tests = QATest.objects.filter(is_active=True).order_by('test_type', 'order_index')
        tests_by_type = {}
        for test in tests:
            if test.test_type not in tests_by_type:
                tests_by_type[test.test_type] = []
            tests_by_type[test.test_type].append(test)
        return tests_by_type
    
    @staticmethod
    def get_tolerance_for_test(test_number):
        """Get tolerance for a specific test number (for backward compatibility)"""
        try:
            # Get test from database based on order_index
            test = QATest.objects.filter(order_index=test_number, is_active=True).first()
            if test:
                return test.tolerance_value, test.tolerance_unit
            else:
                logger.warning(f"Test not found in database for order_index: {test_number}")
        except Exception as e:
            logger.error(f"Error getting tolerance for test {test_number}: {e}")
        
        # Fallback to hardcoded values
        fallback_tolerances = [
            (1, "mm"), (1, "độ"), (0.5, "độ"), (1, "mm"), (1, "độ"), (1, "mm"),
            (1, "mm"), (1, "mm"), (1, "mm"), (1, "mm"), (2, "mm"), (1, "mm"),
            (1, "mm"), (1, "mm"), (2, "%"), (1, "%"), (3, "%"), (3, "%"),
            (1, "%"), (2, "%")
        ]
        if 1 <= test_number <= len(fallback_tolerances):
            return fallback_tolerances[test_number - 1]
        return (1, "mm")  # Default tolerance
    
    @staticmethod
    def create_enhanced_qa_record(linac, performed_by, test_data, notes="", test_notes=None, film_analyses=None, isocenter_matrix_data=None, beam_test_results=None, custom_test_results=None):
        """Create a new QA record with film analyses and test notes"""
        try:
            # Determine initial status based on test results
            status = QAService._determine_qa_status(test_data)
            
            # Create the main QA record
            qa_record = QARecord.objects.create(
                linac=linac,
                performed_by=performed_by,
                status=status,
                notes=notes,
                isocenter_matrix_data=isocenter_matrix_data or {},
                beam_test_results=beam_test_results or {},
                custom_test_results=custom_test_results or {},
                **test_data
            )
            
            # Save test notes if provided
            if test_notes:
                for test_number, note_text in test_notes.items():
                    if note_text.strip():  # Only save non-empty notes
                        QATestNote.objects.create(
                            qa_record=qa_record,
                            test_number=test_number,
                            note_text=note_text
                        )
            
            # Save film analyses if provided
            if film_analyses:
                for analysis_type, result_image_path in film_analyses.items():
                    if result_image_path and os.path.exists(result_image_path):
                        # Create unique filename for the QA record
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        unique_id = str(uuid.uuid4())[:8]
                        file_extension = os.path.splitext(result_image_path)[1]
                        new_filename = f"{analysis_type}_{qa_record.linac.name}_{timestamp}_{unique_id}{file_extension}"
                        
                        # Copy the result image to the qa_results directory with unique naming
                        with open(result_image_path, 'rb') as f:
                            qa_record.film_analyses.create(
                                analysis_type=analysis_type,
                                result_image=File(f, name=f'qa_results/{new_filename}')
                            )
                        
                        logger.info(f"Saved {analysis_type} analysis image: {new_filename}")
            
            # Log activity
            UserActivity.objects.create(
                user=performed_by,
                activity_type='qa_create',
                description=f"Created enhanced QA record for {linac.name} with film analyses",
                ip_address=None
            )
            
            return qa_record
        except Exception as e:
            logger.error(f"Error creating enhanced QA record: {e}")
            raise

    @staticmethod
    def store_film_analysis_result(analysis_type, result_data):
        """Store film analysis result for later retrieval"""
        try:
            # Store in session or temporary storage
            # For now, we'll use a simple approach - in production, consider using Redis or database
            if not hasattr(QAService, '_film_analysis_results'):
                QAService._film_analysis_results = {}
            
            QAService._film_analysis_results[analysis_type] = result_data
            logger.info(f"Stored {analysis_type} analysis result: {result_data}")
            
        except Exception as e:
            logger.error(f"Error storing film analysis result: {e}")

    @staticmethod
    def get_stored_film_analysis_result(analysis_type):
        """Get stored film analysis result"""
        try:
            if hasattr(QAService, '_film_analysis_results'):
                return QAService._film_analysis_results.get(analysis_type, {})
            return {}
        except Exception as e:
            logger.error(f"Error getting stored film analysis result: {e}")
            return {}

    @staticmethod
    def extract_film_test_values():
        """Extract values from film analysis results for automatic test input"""
        try:
            film_values = {}
            
            # Get field size analysis result
            fieldsize_result = QAService.get_stored_film_analysis_result('fieldsize')
            if fieldsize_result:
                # Extract max shift value
                max_shift = fieldsize_result.get('match_mm', 0.0)
                film_values['test_12'] = max_shift
            
            # Get collimator isocenter analysis result
            colli_result = QAService.get_stored_film_analysis_result('collimator_isocenter')
            if colli_result:
                # Extract displacement value for test 13
                displacement = colli_result.get('displacement_mm', 0.0)
                film_values['test_13'] = displacement
                # Extract circle diameter for test 14 (Bug 5 fix: Test 14 should record enclosed circle diameter)
                circle_diameter = colli_result.get('circle_diameter_mm', 0.0)
                film_values['test_14'] = circle_diameter
            
            # Get gantry isocenter analysis result
            # Note: Gantry isocenter results are not automatically stored in test fields
            # as they are handled separately
            
            return film_values
        except Exception as e:
            logger.error(f"Error extracting film test values: {e}")
            return {}

    @staticmethod
    def get_film_analysis_images():
        """
        Get current film analysis result images.
        
        Searches for film analysis result images in the media directory
        and returns the most recent files for each analysis type.
        """
        try:
            film_analyses = {}
            
            # Check for field size analysis result (new unique naming)
            fieldsize_pattern = os.path.join(settings.MEDIA_ROOT, 'film_uploads', 'fieldsize_analysis_result_*.png')
            fieldsize_files = glob.glob(fieldsize_pattern)
            if fieldsize_files:
                # Get the most recent file
                fieldsize_files.sort(key=os.path.getmtime, reverse=True)
                film_analyses['fieldsize'] = fieldsize_files[0]
            
            # Check for collimator isocenter analysis result (new unique naming)
            colli_pattern = os.path.join(settings.MEDIA_ROOT, 'film_uploads', 'collimator_analysis_result_*.png')
            colli_files = glob.glob(colli_pattern)
            if colli_files:
                # Get the most recent file
                colli_files.sort(key=os.path.getmtime, reverse=True)
                film_analyses['collimator_isocenter'] = colli_files[0]
            
            # Check for gantry isocenter analysis result (new unique naming)
            gantry_pattern = os.path.join(settings.MEDIA_ROOT, 'film_uploads', 'gantry_analysis_result_*.png')
            gantry_files = glob.glob(gantry_pattern)
            if gantry_files:
                # Get the most recent file
                gantry_files.sort(key=os.path.getmtime, reverse=True)
                film_analyses['gantry_isocenter'] = gantry_files[0]
            
            return film_analyses
        except Exception as e:
            logger.error(f"Error getting film analysis images: {e}")
            return {}

    @staticmethod
    def get_qa_record_film_analyses(qa_record):
        """Get stored film analysis images for a specific QA record"""
        try:
            film_analyses = {}
            for analysis in qa_record.film_analyses.all():
                if analysis.result_image:
                    film_analyses[analysis.analysis_type] = {
                        'image_url': analysis.result_image.url,
                        'image_path': analysis.result_image.path,
                        'created_at': analysis.created_at
                    }
            return film_analyses
        except Exception as e:
            logger.error(f"Error getting QA record film analyses: {e}")
            return {}
    
    @staticmethod
    def _determine_qa_status(test_data):
        """Determine QA status based on test results"""
        try:
            # Get default statuses
            passed_status = QAStatus.objects.filter(name='passed').first()
            failed_status = QAStatus.objects.filter(name='failed').first()
            
            if not passed_status or not failed_status:
                return None
            
            # Check if any tests failed (assuming test_01 to test_20)
            for i in range(1, 21):
                test_field = f'test_{i:02d}'
                if test_field in test_data and test_data[test_field] is not None:
                    tolerance_value, _ = QAService.get_tolerance_for_test(i)
                    if abs(test_data[test_field]) > tolerance_value:
                        return failed_status
            
            return passed_status
        except Exception as e:
            logger.error(f"Error determining QA status: {e}")
            return None
    

# ============================================================================
# QA Schedule Service Class
# ============================================================================

class QAScheduleService:
    """Service class for QA schedule mutation workflows."""

    @staticmethod
    def assign_performers(schedule_id, performer1_id=None, performer2_id=None, expected_qa_date=None):
        """Assign performers and optional expected QA date to an existing schedule."""
        schedule = QASchedule.objects.get(id=schedule_id)
        schedule.performer1_id = performer1_id if performer1_id else None
        schedule.performer2_id = performer2_id if performer2_id else None

        if expected_qa_date:
            try:
                schedule.expected_qa_date = datetime.strptime(expected_qa_date, '%Y-%m-%d').date()
            except ValueError:
                # Preserve current behavior: ignore invalid date formats.
                pass

        schedule.save()
        return schedule

    @staticmethod
    def confirm_schedule(schedule_id, linac_id=None, performer1_id=None, performer2_id=None):
        """Confirm assignment details for an existing schedule."""
        schedule = QASchedule.objects.get(id=schedule_id)
        if linac_id:
            schedule.linac_id = linac_id
        schedule.performer1_id = performer1_id if performer1_id else None
        schedule.performer2_id = performer2_id if performer2_id else None
        schedule.save()
        return schedule

    @staticmethod
    def create_schedule(date_str, linac_id, performer1_id=None, performer2_id=None):
        """Create a schedule from API payload fields."""
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        linac = Linac.objects.get(id=linac_id)
        schedule = QASchedule.objects.create(
            linac=linac,
            month_year=schedule_date,
            performer1_id=performer1_id if performer1_id else None,
            performer2_id=performer2_id if performer2_id else None,
            qa_reason=f'QA for {linac.name} on {schedule_date.strftime("%B %Y")}',
        )
        return schedule

    @staticmethod
    def update_schedule_notes(schedule_id, new_notes, user, ip_address=None):
        """Update notes with edit-history append and activity logging."""
        schedule = QASchedule.objects.get(id=schedule_id)
        old_notes = schedule.notes
        schedule.notes = new_notes

        if not schedule.notes_edit_history:
            schedule.notes_edit_history = []

        history_entry = {
            'user': user.username,
            'user_full_name': user.get_full_name() or user.username,
            'old_notes': old_notes,
            'new_notes': new_notes,
            'timestamp': timezone.now().isoformat(),
        }
        schedule.notes_edit_history.append(history_entry)
        schedule.save()

        UserActivity.objects.create(
            user=user,
            activity_type='qa_update',
            description=f'Updated notes for QA schedule: {schedule.linac.name} - {schedule.month_year.strftime("%B %Y")}',
            ip_address=ip_address,
        )
        return schedule


# ============================================================================
# Activity Service Class
# ============================================================================

class ActivityService:
    """
    Service class for user activity tracking.
    
    Provides methods to log user activities such as login, QA record creation,
    film uploads, report generation, etc.
    """
    
    @staticmethod
    def log_activity(user, activity_type, description, ip_address=None):
        """
        Log user activity.
        
        Args:
            user: User instance performing the activity
            activity_type: Type of activity (login, qa_create, etc.)
            description: Description of the activity
            ip_address: Optional IP address of the user
        """
        try:
            UserActivity.objects.create(
                user=user,
                activity_type=activity_type,
                description=description,
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
    
