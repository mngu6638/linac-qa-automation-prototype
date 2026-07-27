"""
QA Entry and Management Views.

This module contains view functions for:
- QA entry form and submission
- QA record listing and detail views
- Dose calculation API endpoints
- Film upload handling
- QA report generation
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.files import File
from ..forms import QARecordForm
from ..film_constants import (
    FILM_UPLOAD_CLEANUP_PATTERNS,
    FILM_UPLOAD_SUBDIR,
    SESSION_LATEST_PATHS_KEY,
)
from ..models import QARecord, QATestNote, Linac
from ..services import QAService, ActivityService
from pathlib import Path
import logging
import os
import re
import json
import glob
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


def _normalize_linac_energies(raw_energy):
    """Normalize LINAC energy field into a clean string list."""
    if raw_energy is None:
        return []
    if isinstance(raw_energy, list):
        return [str(item).strip() for item in raw_energy if str(item).strip()]
    if isinstance(raw_energy, str):
        raw_text = raw_energy.strip()
        if not raw_text:
            return []
        try:
            parsed = json.loads(raw_text)
        except (ValueError, TypeError):
            return [raw_text]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, str):
            parsed_text = parsed.strip()
            return [parsed_text] if parsed_text else []
        return []
    if hasattr(raw_energy, '__iter__') and not isinstance(raw_energy, (str, bytes)):
        return [str(item).strip() for item in raw_energy if str(item).strip()]
    return []


def get_app_version():
    """Read version from VERSION.txt (project root in dev, exe folder when packaged)."""
    fallback = '1.4.1'
    try:
        candidates = []
        app_dir = getattr(settings, 'APP_DIR', None)
        base_dir = getattr(settings, 'BASE_DIR', None)
        if app_dir:
            candidates.append(Path(app_dir) / 'VERSION.txt')
            candidates.append(Path(app_dir) / 'config' / 'VERSION.txt')
        if base_dir:
            base_path = Path(base_dir)
            candidates.append(base_path / 'VERSION.txt')
            candidates.append(base_path / 'config' / 'VERSION.txt')
            candidates.append(base_path.parent / 'VERSION.txt')
        seen = set()
        for path in candidates:
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            if path.exists():
                version = path.read_text(encoding='utf-8').strip()
                if version:
                    return version
    except Exception:
        pass
    return fallback

def cleanup_uploaded_files():
    """
    Clean up temporary uploaded files to prevent storage bloat.
    Only remove transient working files under uploads/film_uploads/.
    Persisted evidence in uploads/qa_results/ is intentionally preserved.
    """
    try:
        film_dir = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR)
        if not os.path.exists(film_dir):
            return 0

        total_files_removed = 0
        files_to_remove = set()
        for pattern in FILM_UPLOAD_CLEANUP_PATTERNS:
            files_to_remove.update(glob.glob(os.path.join(film_dir, pattern)))

        for file_path in files_to_remove:
            if not os.path.isfile(file_path):
                continue
            try:
                os.remove(file_path)
                total_files_removed += 1
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {file_path}: {e}")
        
        return total_files_removed
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        logger.error(f"Error during uploaded files cleanup: {e}")
        raise


def _get_current_film_analysis_images(request):
    """
    Resolve latest analysis image paths for this request/session.
    Prefer explicit session-bound paths only.
    In single-user workflow this is intentional: if session pointers are missing,
    we do not guess from shared folder globs because that can reattach stale files
    after redo/re-crop/restart. User should re-run analysis to regenerate pointers.
    """
    session_paths = request.session.get(SESSION_LATEST_PATHS_KEY, {})
    result = {}
    if isinstance(session_paths, dict):
        for analysis_type in ('fieldsize', 'collimator_isocenter', 'gantry_isocenter'):
            candidate = session_paths.get(analysis_type)
            if candidate and os.path.exists(candidate):
                result[analysis_type] = candidate
    return result


def _upsert_qa_record_film_analyses(qa_record, film_analyses):
    """Attach current film analyses to an existing QA record by replacing type-wise artifacts."""
    if not film_analyses:
        return
    for analysis_type, result_image_path in film_analyses.items():
        if not result_image_path or not os.path.exists(result_image_path):
            continue
        qa_record.film_analyses.filter(analysis_type=analysis_type).delete()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        extension = os.path.splitext(result_image_path)[1] or '.png'
        new_filename = f"{analysis_type}_{qa_record.linac.name}_{timestamp}_{unique_id}{extension}"
        with open(result_image_path, 'rb') as f:
            qa_record.film_analyses.create(
                analysis_type=analysis_type,
                result_image=File(f, name=f'qa_results/{new_filename}')
            )

@login_required
def home(request):
    """Home page view"""
    try:
        # Log user activity
        ActivityService.log_activity(
            user=request.user,
            activity_type='login',
            description='User accessed home page'
        )
        
        # Get organization settings
        from ..models import OrganizationSettings
        org_settings = OrganizationSettings.get_settings()
        
        return render(request, 'QAID_Manager/home.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })
    except Exception as e:
        logger.error(f"Error in home view: {e}")
        messages.error(request, "An error occurred while loading the home page.")
        try:
            from ..models import OrganizationSettings
            org_settings = OrganizationSettings.get_settings()
        except Exception:
            org_settings = None
        return render(request, 'QAID_Manager/home.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })

@login_required
def about(request):
    """About page view"""
    try:
        # Get organization settings for consistent branding
        from ..models import OrganizationSettings
        org_settings = OrganizationSettings.get_settings()
        
        return render(request, 'QAID_Manager/about.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })
    except Exception as e:
        logger.error(f"Error in about view: {e}")
        messages.error(request, "An error occurred while loading the about page.")
        try:
            from ..models import OrganizationSettings
            org_settings = OrganizationSettings.get_settings()
        except Exception:
            org_settings = None
        return render(request, 'QAID_Manager/about.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })

@login_required
def help(request):
    """Help page view"""
    try:
        # Get organization settings for consistent branding
        from ..models import OrganizationSettings
        org_settings = OrganizationSettings.get_settings()
        
        return render(request, 'QAID_Manager/help.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })
    except Exception as e:
        logger.error(f"Error in help view: {e}")
        messages.error(request, "An error occurred while loading the help page.")
        try:
            from ..models import OrganizationSettings
            org_settings = OrganizationSettings.get_settings()
        except Exception:
            org_settings = None
        return render(request, 'QAID_Manager/help.html', {
            'org_settings': org_settings,
            'app_version': get_app_version()
        })

@login_required
def qa_entry(request):
    """QA entry form view"""
    try:
        # Get QA tests organized by type from database
        tests_by_type = QAService.get_qa_tests_by_type()
        
        # Get all active tests ordered by order_index
        from ..models import QATest, CustomTestType
        all_tests = QATest.objects.filter(is_active=True).order_by('order_index')

        custom_test_types = list(
            CustomTestType.objects.filter(is_active=True)
            .prefetch_related('tests')
            .order_by('display_order', 'name')
        )
        
        # Organize tests by type
        mechanical_tests = []
        beam_tests = []
        film_tests = []
        isocenter_tests = []
        
        for test in all_tests:
            tolerance = (test.tolerance_value, test.tolerance_unit)
            test_info = (test.order_index, test.name, tolerance)
            
            if test.test_type == 'mechanical':
                mechanical_tests.append(test_info)
            elif test.test_type == 'beam':
                beam_tests.append(test_info)
            elif test.test_type == 'film':
                film_tests.append(test_info)
            elif test.test_type == 'isocenter':
                isocenter_tests.append(test_info)
        
    
        if len(beam_tests) == 0:
            print("⚠️ No beam tests found in database, creating default beam tests")
            # Create default beam tests if none exist in database
            default_beam_tests = [
                (15, "Liều tuyệt đối", (2, "%")),
                (16, "Sự ổn định của năng lượng (D10)", (1, "%")),
                (17, "Tính đối xứng so với giá trị tại thời điểm commissioning", (3, "%")),
                (18, "Tính phẳng so với giá trị tại thời điểm commissioning", (3, "%")),
                (19, "Tính tuyến tính của liều và số MU", (1, "%")),
                (20, "Hệ số liều lối ra theo kích thước trường chiếu so với giá trị commissioning", (2, "%"))
            ]
            beam_tests = default_beam_tests

        temp_qa_record = None
        test_values = None
        test_tolerances = None
        isocenter_matrix_values = None
        beam_test_results_by_energy = None
        test_notes_context = None
        draft_dose_calculation_state = None
        selected_linac_id = None
        
        if request.method == 'POST':
            form = QARecordForm(request.POST)
            if form.is_valid():
                try:
                    linac_obj = form.cleaned_data.get('linac')
                    selected_linac_id = linac_obj.id if linac_obj else None
                    # Check if we have an existing QA record ID to update
                    existing_qa_id = request.POST.get('current_qa_record_id')
                    save_mode = (request.POST.get('save_mode') or 'final').strip().lower()
                    is_draft_save = save_mode == 'draft'
                    from QAID_Manager.models import QAStatus
                    draft_status = QAStatus.objects.filter(name='in_progress').first()
                    
                    # Extract test data from form
                    test_data = {}
                    for i in range(1, 21):
                        field_name = f'test_{i:02d}'
                        if field_name in form.cleaned_data:
                            test_data[field_name] = form.cleaned_data[field_name]
                    
                    # Extract test notes from form
                    test_notes = {}
                    for i in range(1, 21):
                        # Determine note field name based on test type
                        if i <= 7:
                            # Mechanical tests
                            note_field = f'note_m_{i}'
                        elif i <= 11:
                            # Isocenter tests
                            note_field = f'note_iso_{i}'
                        elif i <= 14:
                            # Film tests
                            note_field = f'note_film_{i}'
                        else:
                            # Beam tests
                            note_field = f'note_b_{i-14}'
                        
                        if note_field in request.POST:
                            test_notes[i] = request.POST.get(note_field, '').strip()
                    
                    # Extract isocenter matrix data (individual angle values)
                    isocenter_matrix_data = {}
                    angle_list = [0, 90, 135, 180]
                    for test_num in [8, 9, 10]:
                        for angle in angle_list:
                            ab_key = f'iso_{test_num}_ab_{angle}'
                            gt_key = f'iso_{test_num}_gt_{angle}'
                            ab_value = request.POST.get(ab_key, '').strip()
                            gt_value = request.POST.get(gt_key, '').strip()
                            if ab_value:
                                try:
                                    isocenter_matrix_data[ab_key] = float(ab_value)
                                except (ValueError, TypeError):
                                    pass
                            if gt_value:
                                try:
                                    isocenter_matrix_data[gt_key] = float(gt_value)
                                except (ValueError, TypeError):
                                    pass
                    
                    # Extract multi-energy beam test results
                    beam_test_results = {}
                    selected_energies = request.POST.getlist('selected_energies[]')
                    if not selected_energies:
                        # Fallback: infer energies from posted beam_* fields for resume safety.
                        inferred = set()
                        for post_key in request.POST.keys():
                            match = re.match(r'^beam_(.+?)_test_(1[5-9]|20)$', post_key)
                            if match:
                                inferred.add(match.group(1))
                        selected_energies = sorted(inferred)
                    
                    for energy in selected_energies:
                        energy_results = {}
                        has_any_value = False
                        # Extract test results for this energy (tests 15-20)
                        for test_num in range(15, 21):
                            test_key = f'beam_{energy}_test_{test_num}'
                            test_value = request.POST.get(test_key, '').strip()
                            if test_value:
                                try:
                                    # Extract numeric value from formatted string like "0.1% (67.5%)"
                                    # Pattern: extract first number before % or (
                                    match = re.match(r'^([-\d.]+)%?\s*(?:\(|$)', test_value)
                                    if match:
                                        numeric_value = float(match.group(1))
                                        energy_results[f'test_{test_num}'] = numeric_value
                                        # Also store the formatted string for display
                                        energy_results[f'test_{test_num}_formatted'] = test_value
                                        has_any_value = True
                                    else:
                                        # Try direct float conversion as fallback
                                        energy_results[f'test_{test_num}'] = float(test_value)
                                        has_any_value = True
                                except (ValueError, TypeError):
                                    energy_results[f'test_{test_num}'] = None
                            else:
                                energy_results[f'test_{test_num}'] = None
                            
                            # Extract individual test notes
                            note_key = f'beam_{energy}_note_{test_num}'
                            note_value = request.POST.get(note_key, '').strip()
                            if note_value:
                                energy_results[f'test_{test_num}_note'] = note_value
                                has_any_value = True
                        
                        # Extract general notes for this energy
                        energy_notes_key = f'beam_{energy}_notes'
                        energy_notes = request.POST.get(energy_notes_key, '').strip()
                        if energy_notes:
                            energy_results['notes'] = energy_notes
                            has_any_value = True
                        
                        if has_any_value:
                            beam_test_results[energy] = energy_results
                    
                    # Extract custom test type results
                    custom_test_results = {}
                    for ct in custom_test_types:
                        type_results = {}
                        for t in ct.tests.filter(is_active=True).order_by('order_index'):
                            field_key = f'custom_{ct.slug}_{t.id}'
                            raw = request.POST.get(field_key, '').strip()
                            if raw:
                                try:
                                    type_results[str(t.id)] = float(raw)
                                except (ValueError, TypeError):
                                    pass
                        if type_results:
                            custom_test_results[ct.slug] = type_results

                    # Get current film analysis images (session-scoped first, then fallback).
                    film_analyses = _get_current_film_analysis_images(request)
                    
                    # v1.1.2: Do NOT overwrite test_data with film/analysis - store what user sees on submit
                    # (film_test_values would overwrite user edits to test_12, test_13, test_14)
                    
                    # v1.1.2: Ensure test_15-20 in test_data reflect displayed (POST) values from primary energy
                    if beam_test_results:
                        primary_energy = list(beam_test_results.keys())[0]
                        primary_results = beam_test_results[primary_energy]
                        for test_num in range(15, 21):
                            test_key = f'test_{test_num}'
                            if test_key in primary_results and primary_results[test_key] is not None:
                                test_data[test_key] = primary_results[test_key]
                    
                    if existing_qa_id:
                        # Update existing QA record
                        try:
                            qa_record = QARecord.objects.get(id=existing_qa_id)
                        except QARecord.DoesNotExist:
                            qa_record = None

                        if qa_record is None:
                            existing_qa_id = None
                    
                    if existing_qa_id and qa_record is not None:
                        qa_record.linac = form.cleaned_data['linac']
                        qa_record.notes = form.cleaned_data.get('notes', '')
                        if is_draft_save:
                            qa_record.is_draft = True
                            qa_record.status = draft_status
                        else:
                            qa_record.is_draft = False
                            qa_record.status = QAService._determine_qa_status(test_data)
                        qa_record.save()
                        
                        # Update test data (includes form values for isocenter, film, and beam; v1.1.2 no overwrite)
                        for field_name, value in test_data.items():
                            setattr(qa_record, field_name, value)
                        # Update isocenter matrix data
                        qa_record.isocenter_matrix_data = isocenter_matrix_data
                        # Update multi-energy beam test results.
                        # If request does not carry beam payload, preserve existing data.
                        if beam_test_results:
                            qa_record.beam_test_results = beam_test_results
                        if custom_test_results:
                            qa_record.custom_test_results = custom_test_results
                        # test_15-20 already set from test_data above (from form / primary energy POST)
                        qa_record.save()

                        # Refresh persisted film analyses for this QA record.
                        # This keeps resume/final views in sync after redo/re-analyze.
                        _upsert_qa_record_film_analyses(qa_record, film_analyses)
                        
                        # Update test notes
                        if test_notes:
                            for test_number, note_text in test_notes.items():
                                if note_text.strip():  # Only save non-empty notes
                                    # Get or create the test note
                                    test_note, created = QATestNote.objects.get_or_create(
                                        qa_record=qa_record,
                                        test_number=test_number,
                                        defaults={'note_text': note_text}
                                    )
                                    if not created:
                                        # Update existing note
                                        test_note.note_text = note_text
                                        test_note.save()
                                else:
                                    # Delete note if it's empty
                                    QATestNote.objects.filter(
                                        qa_record=qa_record,
                                        test_number=test_number
                                    ).delete()
                        
                        if not is_draft_save:
                            # Update corresponding QA schedule only for final submissions
                            from ..models import QASchedule, QAStatus
                            from datetime import date

                            # Find the schedule for this month and LINAC
                            current_month = date.today().replace(day=1)
                            schedule = QASchedule.objects.filter(
                                linac=qa_record.linac,
                                month_year=current_month
                            ).first()

                            if schedule:
                                # Update schedule with QA record data
                                schedule.performer1 = qa_record.performed_by
                                schedule.qa_date = qa_record.date_performed

                                # Determine status based on test results
                                if qa_record.notes:
                                    if "All tests within tolerance" in qa_record.notes:
                                        passed_status = QAStatus.objects.filter(name='passed').first()
                                        if passed_status:
                                            schedule.status = passed_status
                                    elif "results out of tolerances" in qa_record.notes.lower():
                                        failed_status = QAStatus.objects.filter(name='failed').first()
                                        if failed_status:
                                            schedule.status = failed_status

                                # Update notes if QA failed
                                if qa_record.notes and "results out of tolerances" in qa_record.notes.lower():
                                    schedule.notes = qa_record.notes

                                schedule.save()
                        
            
                    else:
                        # Create new enhanced QA record
                        # Check if coming from schedule page
                        schedule_id = request.GET.get('schedule') or request.POST.get('schedule_id')
                        schedule = None
                        if schedule_id:
                            from ..models import QASchedule
                            try:
                                schedule = QASchedule.objects.get(id=schedule_id)
                            except QASchedule.DoesNotExist:
                                pass
                        
                        if is_draft_save:
                            qa_record = QAService.create_enhanced_qa_record(
                                linac=form.cleaned_data['linac'],
                                performed_by=request.user,
                                test_data=test_data,
                                notes=form.cleaned_data.get('notes', ''),
                                test_notes=test_notes,
                                film_analyses=film_analyses,
                                isocenter_matrix_data=isocenter_matrix_data,
                                beam_test_results=beam_test_results,
                                custom_test_results=custom_test_results
                            )
                            qa_record.is_draft = True
                            qa_record.status = draft_status
                            qa_record.save(update_fields=['is_draft', 'status'])
                        else:
                            # test_data already includes test_15-20 from primary energy POST (v1.1.2)
                            qa_record = QAService.create_enhanced_qa_record(
                                linac=form.cleaned_data['linac'],
                                performed_by=request.user,
                                test_data=test_data,
                                notes=form.cleaned_data.get('notes', ''),
                                test_notes=test_notes,
                                film_analyses=film_analyses,
                                isocenter_matrix_data=isocenter_matrix_data,
                                beam_test_results=beam_test_results,
                                custom_test_results=custom_test_results
                            )
                            # test_15-20 are already in test_data, saved via create_enhanced_qa_record
                        
                        # Link QA record to schedule if provided
                        if schedule:
                            # Check if this is a regular schedule that already has a QA record
                            # If so, don't link the new QA record to prevent overwriting existing results
                            if schedule.is_adhoc:
                                # Ad-hoc schedules are fine - always link
                                qa_record.qa_schedule = schedule
                                qa_record.save()
                            else:
                                # Regular schedule - check if it already has a QA record
                                from django.db.models import Count
                                existing_count = schedule.qa_records.filter(is_draft=False).count()
                                if existing_count == 0:
                                    # No existing QA record, safe to link
                                    qa_record.qa_schedule = schedule
                                    qa_record.save()
                                    
                                    if not is_draft_save:
                                        # Update schedule with QA record data
                                        schedule.performer1 = qa_record.performed_by
                                        schedule.qa_date = qa_record.date_performed
                                        schedule.status = qa_record.status

                                        # Get failed tests if QA failed
                                        if qa_record.is_failed():
                                            from ..views.qa_schedule_views import get_failed_tests
                                            failed_tests = get_failed_tests(qa_record)
                                            schedule.failed_tests_data = failed_tests

                                        schedule.save()
                                else:
                                    # Schedule already has a QA record - don't link to prevent overwriting
                                    # This prevents non-scheduled QA from pulling results from existing scheduled QA
                                    logger.warning(f"Schedule {schedule.id} already has {existing_count} QA record(s). Not linking new QA record to prevent overwriting existing results.")
                        else:
                            # Find the schedule for this month and LINAC if not provided
                            from ..models import QASchedule, QAStatus
                            from datetime import date
                            
                            # Use the QA record's date_performed month, not today's month
                            qa_month = qa_record.date_performed.replace(day=1)
                            
                            # Only link to a regular (non-adhoc) schedule that does NOT already have a QA record
                            # This prevents non-scheduled QA from being linked to schedules with existing results
                            # First, find all regular schedules for this month and LINAC
                            potential_schedules = QASchedule.objects.filter(
                                linac=qa_record.linac,
                                month_year=qa_month,
                                is_adhoc=False  # Only consider regular schedules
                            )
                            
                            # Check each schedule to see if it has any QA records
                            schedule = None
                            for sched in potential_schedules:
                                # Explicitly check if this schedule has any linked final QA records
                                existing_qa_count = sched.qa_records.filter(is_draft=False).count()
                                if existing_qa_count == 0:
                                    # This schedule has no QA records - safe to link
                                    schedule = sched
                                    break
                            
                            if schedule:
                                # Double-check: verify no final QA records exist (defensive check)
                                final_check = schedule.qa_records.filter(is_draft=False).count()
                                if final_check == 0:
                                    # Link QA record to schedule
                                    qa_record.qa_schedule = schedule
                                    qa_record.save()
                                    
                                    if not is_draft_save:
                                        # Update schedule with QA record data (safe because we verified no existing records)
                                        schedule.performer1 = qa_record.performed_by
                                        schedule.qa_date = qa_record.date_performed
                                        schedule.status = qa_record.status

                                        # Get failed tests if QA failed
                                        if qa_record.is_failed():
                                            from ..views.qa_schedule_views import get_failed_tests
                                            failed_tests = get_failed_tests(qa_record)
                                            schedule.failed_tests_data = failed_tests

                                        schedule.save()
                                else:
                                    # Schedule has QA records after all - don't link
                                    logger.warning(f"Schedule {schedule.id} has {final_check} QA record(s) after verification. Not linking new QA record.")
                            else:
                                # No suitable schedule found - this is fine for non-scheduled QA
                                logger.info(f"No suitable schedule found for non-scheduled QA (LINAC: {qa_record.linac.name}, Month: {qa_month}). QA record will remain unlinked.")
                    
                    # Persist dose calculator draft state to QA record for Save & Resume flow.
                    if is_draft_save:
                        pending_dose = request.session.get('pending_dose_calculation')
                        if pending_dose:
                            qa_record.draft_dose_calculation_state = pending_dose
                            qa_record.save(update_fields=['draft_dose_calculation_state', 'updated_at'])

                    # Check if there's pending dose calculation data in session
                    if not is_draft_save:
            
                        from QAID_Manager.models import DoseCalculation

                        def _normalize_dose_payloads(payload):
                            if not isinstance(payload, dict):
                                return []
                            # Backward-compatible: old shape is one single dose object.
                            if 'linac_id' in payload and 'energy' in payload:
                                return [payload]
                            normalized = []
                            for _, item in payload.items():
                                if isinstance(item, dict) and 'linac_id' in item and 'energy' in item:
                                    normalized.append(item)
                            return normalized

                        dose_payload = request.session.get('pending_dose_calculation') or qa_record.draft_dose_calculation_state or None
                        dose_payloads = _normalize_dose_payloads(dose_payload)

                        for dose_data in dose_payloads:
                            try:
                                # Create dose calculation record linked to the QA record
                                DoseCalculation.objects.create(
                                    qa_record=qa_record,
                                    linac_id=dose_data['linac_id'],
                                    energy=dose_data['energy'],
                                    detector_id=dose_data['detector_id'],
                                    phantom=dose_data['phantom'],
                                    
                                    # Absolute Dose Calculations - Input Values
                                    raw_measurement=dose_data['raw_measurement'],
                                    temperature=dose_data.get('temperature'),
                                    pressure=dose_data.get('pressure'),
                                    m_plus=dose_data.get('m_plus'),
                                    m_minus=dose_data.get('m_minus'),
                                    m1=dose_data.get('m1'),
                                    m2=dose_data.get('m2'),
                                    v1=dose_data.get('v1'),
                                    v2=dose_data.get('v2'),
                                    v1_v2_ratio=dose_data.get('v1_v2_ratio'),
                                    a0=dose_data.get('a0'),
                                    a1=dose_data.get('a1'),
                                    a2=dose_data.get('a2'),
                                    
                                    # Absolute Dose Calculations - Results
                                    ktp_result=dose_data['ktp_result'],
                                    kpol_result=dose_data['kpol_result'],
                                    ks_result=dose_data['ks_result'],
                                    solid_phantom_factor=dose_data['solid_phantom_factor'],
                                    mq_result=dose_data['mq_result'],
                                    dwq_zref=dose_data['dwq_zref'],
                                    dwq_zmax=dose_data['dwq_zmax'],
                                    
                                    # SSD Setup Fields
                                    absolute_setup_mode=dose_data.get('absolute_setup_mode', 'SAD'),
                                    pdd_zref=dose_data.get('pdd_zref'),
                                    pdd_zref_source=dose_data.get('pdd_zref_source'),
                                    
                                    # Beam Quality Parameters
                                    pdd_20_10=dose_data['pdd_20_10'],
                                    tmr=dose_data['tmr'],
                                    tpr_20_10=dose_data['tpr_20_10'],
                                    kq_factor=dose_data['kq_factor'],
                                    
                                    # Relative Dose Measurements
                                    m_ref=dose_data['m_ref'],
                                    m_left=dose_data['m_left'],
                                    m_right=dose_data['m_right'],
                                    m_gun=dose_data['m_gun'],
                                    m_tar=dose_data['m_tar'],
                                    m_mid=dose_data['m_mid'],
                                    m_wedge=dose_data['m_wedge'],
                                    m_dmax=dose_data['m_dmax'],
                                    
                                    # Relative Dose Results
                                    symmetry_crossline=dose_data['symmetry_crossline'],
                                    symmetry_inline=dose_data['symmetry_inline'],
                                    flatness_crossline=dose_data['flatness_crossline'],
                                    flatness_inline=dose_data['flatness_inline'],
                                    output_factor=dose_data['output_factor'],
                                    wedge_factor=dose_data['wedge_factor'],
                                    beam_energy_d10=dose_data['beam_energy_d10'],
                                    
                                    # MU Linearity
                                    mu_10=dose_data.get('mu_10'),
                                    mu_30=dose_data.get('mu_30'),
                                    mu_50=dose_data.get('mu_50'),
                                    mu_100=dose_data.get('mu_100'),
                                    mu_300=dose_data.get('mu_300'),
                                    mu_500=dose_data.get('mu_500'),
                                    mu_r2=dose_data.get('mu_r2'),
                                    
                                    # QA Entry Auto-populated Values
                                    absolute_dose_deviation=dose_data.get('absolute_dose_deviation'),
                                    energy_stability_d10=dose_data.get('energy_stability_d10'),
                                    symmetry_vs_commissioning=dose_data.get('symmetry_vs_commissioning'),
                                    flatness_vs_commissioning=dose_data.get('flatness_vs_commissioning'),
                                    output_factor_deviation=dose_data.get('output_factor_deviation'),
                                )
                            except Exception as dose_create_error:
                                logger.warning(f"Skipping one dose payload due to invalid data: {dose_create_error}")

                        # Clear pending dose draft/session after final submit
                        if 'pending_dose_calculation' in request.session:
                            del request.session['pending_dose_calculation']
                        if qa_record.draft_dose_calculation_state:
                            qa_record.draft_dose_calculation_state = {}
                            qa_record.save(update_fields=['draft_dose_calculation_state', 'updated_at'])
                    else:
                        pass
                    
                    # Clean up uploaded files after successful final save
                    if not is_draft_save:
                        try:
                            cleanup_uploaded_files()
                            request.session.pop(SESSION_LATEST_PATHS_KEY, None)
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to cleanup uploaded files: {cleanup_error}")

                    if is_draft_save:
                        messages.success(request, f"Draft QA saved for {qa_record.linac.name}. You can resume later.")
                    else:
                        messages.success(request, f"QA record {'updated' if existing_qa_id else 'created'} successfully for {qa_record.linac.name}")
                    
                    # Redirect to QA Schedule page
                    # If we have a schedule, redirect to that month's schedule
                    if qa_record.qa_schedule:
                        from datetime import date
                        schedule_month = qa_record.qa_schedule.month_year
                        return redirect(f'/qa-schedule/?month={schedule_month.month}&year={schedule_month.year}')
                    else:
                        # Otherwise, redirect to current month's schedule
                        from datetime import date
                        today = date.today()
                        return redirect(f'/qa-schedule/?month={today.month}&year={today.year}')
                    
                except Exception as e:
                    logger.error(f"Error creating QA record: {e}")
                    messages.error(request, "An error occurred while saving the QA record.")
        else:
            # Check if linac parameter is provided in URL
            linac_id = request.GET.get('linac')
            schedule_id = request.GET.get('schedule')
            qa_record_id = request.GET.get('qa_record')
            resume_record = None
            test_values = None
            test_tolerances = None
            isocenter_matrix_values = None
            beam_test_results_by_energy = None
            test_notes_context = None
            draft_dose_calculation_state = None
            selected_linac_id = None
            initial_linac_energies = []
            
            # IMPORTANT: For non-scheduled QA, we should NOT pre-populate the form with existing QA data
            # Even if a schedule parameter is provided, we should only pre-select the LINAC, not the test results
            # This prevents non-scheduled QA from automatically pulling results from completed QA
            
            if qa_record_id:
                try:
                    resume_record = QARecord.objects.select_related('linac', 'qa_schedule').get(id=int(qa_record_id))

                    if not resume_record.is_draft:
                        raise ValueError("Selected QA record is not a draft.")

                    if schedule_id:
                        if resume_record.qa_schedule_id != int(schedule_id):
                            raise ValueError("Draft record does not belong to this schedule.")

                    if linac_id:
                        if resume_record.linac_id != int(linac_id):
                            raise ValueError("Draft record does not belong to this LINAC.")

                    form = QARecordForm(initial={
                        'linac': resume_record.linac_id,
                        'notes': resume_record.notes,
                    })
                    selected_linac_id = resume_record.linac_id
                    temp_qa_record = resume_record

                    test_values = {}
                    test_tolerances = {}
                    for i in range(1, 21):
                        test_field = f'test_{i:02d}'
                        test_value = getattr(resume_record, test_field, None)
                        if test_value is not None:
                            test_values[test_field] = test_value
                        test_obj = QATest.objects.filter(order_index=i, is_active=True).first()
                        if test_obj:
                            test_tolerances[test_field] = test_obj.tolerance_value

                    raw_iso = resume_record.isocenter_matrix_data
                    isocenter_matrix_values = raw_iso if isinstance(raw_iso, dict) else {}
                    raw_beam = resume_record.beam_test_results
                    beam_test_results_by_energy = raw_beam if isinstance(raw_beam, dict) else {}
                    raw_dose = resume_record.draft_dose_calculation_state
                    draft_dose_calculation_state = raw_dose if isinstance(raw_dose, dict) else {}
                    test_notes_context = {
                        note.test_number: note.note_text
                        for note in QATestNote.objects.filter(qa_record=resume_record)
                    }
                except (QARecord.DoesNotExist, ValueError, TypeError):
                    messages.error(request, "Draft QA record not found.")
                    form = QARecordForm()
                    temp_qa_record = None
            elif linac_id:
                try:
                    # Convert to integer and pre-select the linac in the form
                    linac_id = int(linac_id)
                    selected_linac_id = linac_id
                    form = QARecordForm(initial={'linac': linac_id})
                    print(f"DEBUG: Setting initial linac to {linac_id}")
                    
                    # If a schedule is provided, check if it already has a QA record
                    # If it does, we should NOT pre-populate the form to prevent pulling existing results
                    if schedule_id:
                        try:
                            from ..models import QASchedule
                            schedule = QASchedule.objects.get(id=schedule_id)
                            existing_qa_count = schedule.qa_records.count()
                            
                            if existing_qa_count > 0:
                                # Schedule already has a QA record - this is a non-scheduled QA
                                # Do NOT pre-populate form with existing QA data
                                logger.info(f"Schedule {schedule_id} has {existing_qa_count} existing QA record(s). Creating fresh non-scheduled QA without pre-populating test results.")
                                # Form is already created with only linac pre-selected, which is correct
                        except QASchedule.DoesNotExist:
                            pass
                except Exception as e:
                    print(f"DEBUG: Error setting initial linac: {e}")
                    form = QARecordForm()
            else:
                form = QARecordForm()
            
            # Don't create QA record immediately - we'll create it when dose calculation is saved
            if not qa_record_id:
                temp_qa_record = None

            if selected_linac_id:
                selected_linac = Linac.objects.filter(id=selected_linac_id).first()
                if selected_linac:
                    initial_linac_energies = _normalize_linac_energies(selected_linac.energy)
    
        
        # Prepare context for template
        angle_list = [0, 90, 135, 180]
        
        # Create isocenter matrix rows for the interactive matrix
        isocenter_matrix_rows = [
            (8, "Tâm dây chữ thập"),      # Test #8
            (9, "Đồng tâm quay collimator"),  # Test #9
            (10, "Đồng tâm quay bàn điều trị")  # Test #10
        ]
        
        # Separate film tests by specific type
        fieldsize_group = [t for t in film_tests if t[0] == 12]  # Test #12
        colliiso_group = [t for t in film_tests if t[0] == 13]   # Test #13
        gantryiso_group = [t for t in film_tests if t[0] == 14]  # Test #14
        
        # Check for uploaded film files
        import os
        from django.conf import settings
        fieldsize_result_image_url = None
        colli_result_image_url = None
        gantry_result_image_url = None
        
        film_filename = None
        film_image_url = None
        
        # Get the most recent uploaded field size film
        from QAID_Manager.models import FilmUpload
        latest_film = FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        
        if latest_film and latest_film.image:
            film_filename = os.path.basename(latest_film.image.name)
            film_image_url = latest_film.image.url if hasattr(latest_film.image, 'url') else None
        else:
            pass
        
        # Check for collimator film files
        colli_film_filename = None
        colli_film_image_url = None
        
        # Get the most recent uploaded collimator film
        from QAID_Manager.models import CollimatorFilmUpload
        latest_colli_film = CollimatorFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        
        if latest_colli_film and latest_colli_film.image:
            colli_film_filename = os.path.basename(latest_colli_film.image.name)
            colli_film_image_url = latest_colli_film.image.url if hasattr(latest_colli_film.image, 'url') else None
        else:
            pass
        
        # Check for gantry film files
        gantry_film_filename = None
        gantry_film_image_url = None
        
        # Get the most recent uploaded gantry film
        from QAID_Manager.models import GantryFilmUpload
        latest_gantry_film = GantryFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        
        if latest_gantry_film and latest_gantry_film.image:
            gantry_film_filename = os.path.basename(latest_gantry_film.image.name)
            gantry_film_image_url = latest_gantry_film.image.url if hasattr(latest_gantry_film.image, 'url') else None
        else:
            pass

        # For draft resume, prefer film images already stored on this QA record.
        if temp_qa_record and getattr(temp_qa_record, 'id', None):
            fieldsize_analysis = temp_qa_record.film_analyses.filter(analysis_type='fieldsize').order_by('-created_at').first()
            colli_analysis = temp_qa_record.film_analyses.filter(analysis_type='collimator_isocenter').order_by('-created_at').first()
            gantry_analysis = temp_qa_record.film_analyses.filter(analysis_type='gantry_isocenter').order_by('-created_at').first()

            if fieldsize_analysis and fieldsize_analysis.result_image:
                fieldsize_result_image_url = fieldsize_analysis.result_image.url
            if colli_analysis and colli_analysis.result_image:
                colli_result_image_url = colli_analysis.result_image.url
            if gantry_analysis and gantry_analysis.result_image:
                gantry_result_image_url = gantry_analysis.result_image.url
        
        # Get all active dosimeters for the dose calculator
        from QAID_Manager.models import Dosimeter
        dosimeters = Dosimeter.objects.filter(is_active=True).order_by('name')

        
        # If no active dosimeters found, show all dosimeters
        if dosimeters.count() == 0:
            dosimeters = Dosimeter.objects.all().order_by('name')
        
        # IMPORTANT: Do NOT pre-populate test_values for new QA entries
        # This prevents non-scheduled QA from automatically pulling results from existing QA
        # test_values should only be set when viewing/editing an existing QA record
        # For new QA entries, test_values should be None/empty to ensure a clean form
        
        context = {
            'form': form,
            'mechanical_group': mechanical_tests,
            'isocenter_group': isocenter_tests,
            'film_group': film_tests,
            'beam_group': beam_tests,
            'isocenter_matrix_rows': isocenter_matrix_rows,
            'angle_list': angle_list,
            'fieldsize_group': fieldsize_group,
            'colliiso_group': colliiso_group,
            'gantryiso_group': gantryiso_group,
            'film_filename': film_filename,
            'film_image_url': film_image_url,
            'fieldsize_result_image_url': fieldsize_result_image_url,
            'colli_film_filename': colli_film_filename,
            'colli_film_image_url': colli_film_image_url,
            'colli_result_image_url': colli_result_image_url,
            'gantry_film_filename': gantry_film_filename,
            'gantry_film_image_url': gantry_film_image_url,
            'gantry_result_image_url': gantry_result_image_url,
            'dosimeters': dosimeters,
            'temp_qa_record_id': temp_qa_record.id if temp_qa_record else None,
            # Keep resume prefill data only when opening from draft.
            'test_values': test_values,
            'test_tolerances': test_tolerances,
            'isocenter_matrix_values': isocenter_matrix_values,
            'beam_test_results_by_energy': beam_test_results_by_energy,
            'draft_dose_calculation_state': draft_dose_calculation_state or {},
            'test_notes': test_notes_context,
            'initial_linac_selected': bool(selected_linac_id),
            'initial_linac_energies': initial_linac_energies,
            'custom_test_types': custom_test_types,
            'custom_test_results_json': temp_qa_record.custom_test_results if temp_qa_record else {},
        }
        
        return render(request, 'QAID_Manager/qa_form.html', context)
        
    except Exception as e:
        logger.error(f"Error in qa_entry view: {e}")
        messages.error(request, "An error occurred while loading the QA form.")
        return render(request, 'QAID_Manager/qa_form.html', {'form': QARecordForm()})

@login_required
def qa_list(request):
    """List all QA records"""
    try:
        qa_records = QARecord.objects.select_related('linac', 'performed_by', 'status').filter(is_draft=False).order_by('-date_performed')
        
        # Filter by linac if specified
        linac_id = request.GET.get('linac')
        if linac_id:
            qa_records = qa_records.filter(linac_id=linac_id)
        
        # Filter by status if specified
        status = request.GET.get('status')
        if status:
            qa_records = qa_records.filter(status__name=status)
        
        context = {
            'qa_records': qa_records,
            'linacs': Linac.objects.filter(is_active=True),
        }
        
        return render(request, 'QAID_Manager/qa_list.html', context)
        
    except Exception as e:
        logger.error(f"Error in qa_list view: {e}")
        messages.error(request, "An error occurred while loading QA records.")
        return render(request, 'QAID_Manager/qa_list.html', {'qa_records': []})

@login_required
def qa_detail(request, qa_id):
    """Display detailed QA record with film analyses"""
    try:
        qa_record = QARecord.objects.select_related('linac', 'performed_by', 'status').get(id=qa_id)
        
        # Get film analyses for this QA record
        film_analyses = QAService.get_qa_record_film_analyses(qa_record)
        
        # Get test notes for this QA record
        test_notes = {}
        for note in qa_record.test_notes.all():
            test_notes[note.test_number] = note.note_text
        
        context = {
            'qa_record': qa_record,
            'film_analyses': film_analyses,
            'test_notes': test_notes,
        }
        
        return render(request, 'QAID_Manager/qa_detail.html', context)
        
    except QARecord.DoesNotExist:
        messages.error(request, "QA record not found.")
        return redirect('qa_list')
    except Exception as e:
        logger.error(f"Error in qa_detail view: {e}")
        messages.error(request, "An error occurred while loading the QA record.")
        return redirect('qa_list')

@login_required
def get_linac_energies(request, linac_id):
    """API endpoint to get energies for a specific linac (dose calculator)."""
    try:
        linac = Linac.objects.get(id=linac_id)
        energies = _normalize_linac_energies(linac.energy)

        return JsonResponse({
            'success': True,
            'linac_name': linac.name,
            'energies': energies
        })
        
    except Linac.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Linac not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting linac energies: {e}")
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@login_required
def get_ks_coefficients(request, voltage_ratio):
    """API endpoint to get Ks coefficients for a specific V1/V2 ratio"""
    try:
        from QAID_Manager.models import PhysicsParameters
        import json
        
        # Find the Ks Coefficients table
        ks_table = PhysicsParameters.objects.filter(
            name__icontains='Ks Coefficients',
            is_active=True
        ).first()
        
        if not ks_table or 'table_data' not in ks_table.parameter_values:
            return JsonResponse({
                'success': False,
                'error': 'Ks Coefficients table not found'
            })
        
        table_data = ks_table.parameter_values.get('table_data', [])
        
        # Convert voltage_ratio to float for comparison
        try:
            target_ratio = float(voltage_ratio)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid voltage ratio format'
            })
        
        # Find the row with matching V1/V2 ratio
        for row in table_data:
            try:
                row_ratio = float(row.get('V1/V2', 0))
                if abs(row_ratio - target_ratio) < 0.01:  # Allow small floating point differences
                    return JsonResponse({
                        'success': True,
                        'a0': float(row.get('a0', 0)),
                        'a1': float(row.get('a1', 0)),
                        'a2': float(row.get('a2', 0)),
                        'voltage_ratio': target_ratio
                    })
            except (ValueError, TypeError):
                continue
        
        # If no exact match found, return error
        return JsonResponse({
            'success': False,
            'error': f'Voltage ratio {voltage_ratio} not found in Ks Coefficients table'
        })
        
    except Exception as e:
        logger.error(f"Error getting Ks coefficients: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def get_beam_quality(request, linac_id, energy):
    """API endpoint to get beam quality parameters (PDD, TMR, TPR) for a specific linac and energy"""
    try:
        from QAID_Manager.models import Linac
        
        linac = Linac.objects.get(id=linac_id)
        
        # Bug 7 fix: Normalize energy string for field lookup
        # Handle both "6MV_FFF" (display) and "6MV FFF" (stored) formats
        energy_normalized = energy.replace('_', ' ').replace(' MV', '').replace('MeV', '').replace('MV', '').strip()
        
        # Map energy to field suffixes (normalize to lowercase with underscores)
        energy_field_map = {
            '6': '6mv',
            '10': '10mv',
            '6MV': '6mv',
            '10MV': '10mv',
            '6MV FFF': '6mv_fff',
            '6MV_FFF': '6mv_fff',
            '10MV FFF': '10mv_fff',
            '10MV_FFF': '10mv_fff',
            '6MeV': '6mev',
            '9MeV': '9mev',
            '12MeV': '12mev',
            '15MeV': '15mev',
        }
        
        # Try direct match first, then normalized
        field_suffix = energy_field_map.get(energy, None)
        if not field_suffix:
            field_suffix = energy_field_map.get(energy_normalized, energy_normalized.lower().replace(' ', '_'))
        
        # Get PDD20/10 value from the correct field
        pdd_field_name = f'beam_pdd_20_10_{field_suffix}'
        pdd_value = getattr(linac, pdd_field_name, None)
        
        # Get TMR value from the correct field
        tmr_field_name = f'beam_tpr_zreff_{field_suffix}'
        tmr_value = getattr(linac, tmr_field_name, None)
        
        if pdd_value is not None:
            # Calculate TPR using the formula: TPR20,10 = 1.2661*(PDD20,10) − 0.0595
            tpr_calculated = round(1.2661 * pdd_value - 0.0595, 6)
            
            return JsonResponse({
                'success': True,
                'pdd': pdd_value,
                'tmr': tmr_value,
                'tpr': tpr_calculated,
                'linac_name': linac.name,
                'energy': energy,
                'formula_used': 'TPR20,10 = 1.2661*(PDD20,10) − 0.0595'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'No PDD20/10 data found for {linac.name} at {energy}'
            })
        
    except Linac.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Linac not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting beam quality data: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def get_kq_factor(request, detector, tpr):
    """API endpoint to get Kq factor with interpolation for a specific detector and TPR"""
    try:
        from QAID_Manager.models import PhysicsParameters
        import json
        
        # Find the kQ Photon Beams table
        kq_table = PhysicsParameters.objects.filter(
            name__icontains='kQ Photon Beams',
            is_active=True
        ).first()
        
        if not kq_table or 'table_data' not in kq_table.parameter_values:
            return JsonResponse({
                'success': False,
                'error': 'kQ Photon Beams table not found'
            })
        
        table_data = kq_table.parameter_values.get('table_data', [])
        
        # Convert TPR to float for comparison
        try:
            target_tpr = float(tpr)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid TPR format'
            })
        
        # Find the row for the selected detector using best match
        detector_row = None
        best_match = None
        best_match_score = 0
        
        for row in table_data:
            ic_type = row.get('IC type', '').strip()
            
            # Try exact match first
            if ic_type == detector.strip():
                detector_row = row
                break
            
            # If no exact match, find best partial match
            if detector.strip() in ic_type or ic_type in detector.strip():
                # Calculate match score (longer common substring = better match)
                common_length = len(set(detector.strip().lower()) & set(ic_type.lower()))
                if common_length > best_match_score:
                    best_match_score = common_length
                    best_match = row
        
        # Use best match if no exact match found
        if not detector_row and best_match:
            detector_row = best_match
        
        if not detector_row:
            return JsonResponse({
                'success': False,
                'error': f'Detector {detector} not found in kQ Photon Beams table'
            })
        
        # Get all TPR columns and their Kq values
        tpr_columns = []
        for key, value in detector_row.items():
            if key != 'IC type' and key.strip():
                try:
                    tpr_val = float(key)
                    kq_val = float(value)
                    tpr_columns.append((tpr_val, kq_val))
                except (ValueError, TypeError):
                    continue
        
        if not tpr_columns:
            return JsonResponse({
                'success': False,
                'error': 'No valid TPR/Kq data found for this detector'
            })
        
        # Sort by TPR values
        tpr_columns.sort(key=lambda x: x[0])
        
        # Find exact match first
        for tpr_val, kq_val in tpr_columns:
            if abs(tpr_val - target_tpr) < 0.001:  # Exact match
                return JsonResponse({
                    'success': True,
                    'kq': kq_val,
                    'tpr': target_tpr,
                    'detector': detector,
                    'interpolated': False
                })
        
        # If no exact match, find the two closest values for interpolation
        if target_tpr < tpr_columns[0][0]:
            # Target TPR is below the lowest available value
            return JsonResponse({
                'success': True,
                'kq': tpr_columns[0][1],
                'tpr': target_tpr,
                'detector': detector,
                'interpolated': False,
                'note': 'Using lowest available TPR value'
            })
        elif target_tpr > tpr_columns[-1][0]:
            # Target TPR is above the highest available value
            return JsonResponse({
                'success': True,
                'kq': tpr_columns[-1][1],
                'tpr': target_tpr,
                'detector': detector,
                'interpolated': False,
                'note': 'Using highest available TPR value'
            })
        else:
            # Find the two closest values for interpolation
            for i in range(len(tpr_columns) - 1):
                tpr1, kq1 = tpr_columns[i]
                tpr2, kq2 = tpr_columns[i + 1]
                
                if tpr1 <= target_tpr <= tpr2:
                    # Linear interpolation: kq = kq1 + (kq2 - kq1) * (target_tpr - tpr1) / (tpr2 - tpr1)
                    kq_interpolated = kq1 + (kq2 - kq1) * (target_tpr - tpr1) / (tpr2 - tpr1)
                    
                    return JsonResponse({
                        'success': True,
                        'kq': kq_interpolated,
                        'tpr': target_tpr,
                        'detector': detector,
                        'interpolated': True,
                        'interpolation_points': {
                            'tpr1': tpr1, 'kq1': kq1,
                            'tpr2': tpr2, 'kq2': kq2
                        }
                    })
        
        return JsonResponse({
            'success': False,
            'error': f'Could not interpolate Kq for TPR {target_tpr}'
        })
        
    except Exception as e:
        logger.error(f"Error getting Kq factor: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def get_dosimeter_calibration(request, dosimeter_id):
    """API endpoint to get dosimeter calibration factor"""
    try:
        from QAID_Manager.models import Dosimeter
        
        dosimeter = Dosimeter.objects.get(id=dosimeter_id)
        
        return JsonResponse({
            'success': True,
            'calibration_factor': dosimeter.calibration_factor,
            'dosimeter_name': dosimeter.name,
            'series_number': dosimeter.series_number
        })
        
    except Dosimeter.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Dosimeter not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting dosimeter calibration: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def get_linac_cat_values(request, linac_id, energy):
    """API endpoint to get CAT values for a specific linac and energy"""
    try:
        from QAID_Manager.models import Linac
        
        linac = Linac.objects.get(id=linac_id)
        
        # Normalize energy string for field lookup
        energy_normalized = energy.replace(' MV', '').replace('MeV', '').replace('MV', '')
        
        # Map energy to field suffixes
        energy_field_map = {
            '6': '6mv',
            '10': '10mv',
            '6MV': '6mv',
            '10MV': '10mv',
            '6MV_FFF': '6mv_fff',
            '10MV_FFF': '10mv_fff',
            '6MeV': '6mev',
            '9MeV': '9mev',
            '12MeV': '12mev',
            '15MeV': '15mev',
        }
        
        field_suffix = energy_field_map.get(energy_normalized, energy_normalized.lower())
        
        # Get CAT D10 value
        cat_d10_field = f'cat_d10_{field_suffix}'
        cat_d10 = getattr(linac, cat_d10_field, None)
        
        # Get CAT output factor value
        cat_output_factor_field = f'cat_output_factor_{field_suffix}'
        cat_output_factor = getattr(linac, cat_output_factor_field, None)
        
        # Get CAT wedge factor value
        cat_wedge_factor_field = f'cat_wedge_factor_{field_suffix}'
        cat_wedge_factor = getattr(linac, cat_wedge_factor_field, None)
        
        # Get CAT symmetry value (use the maximum between crossline and inline if both exist)
        cat_symmetry_crossline_field = f'cat_symmetry_{field_suffix}_crossline'
        cat_symmetry_inline_field = f'cat_symmetry_{field_suffix}_inline'
        cat_symmetry_crossline = getattr(linac, cat_symmetry_crossline_field, None)
        cat_symmetry_inline = getattr(linac, cat_symmetry_inline_field, None)
        
        # Return separate symmetry values for crossline and inline
        cat_symmetry_crossline_value = cat_symmetry_crossline
        cat_symmetry_inline_value = cat_symmetry_inline
        
        # Keep the combined symmetry value for backward compatibility
        cat_symmetry = None
        if cat_symmetry_crossline is not None and cat_symmetry_inline is not None:
            cat_symmetry = max(cat_symmetry_crossline, cat_symmetry_inline)
        elif cat_symmetry_crossline is not None:
            cat_symmetry = cat_symmetry_crossline
        elif cat_symmetry_inline is not None:
            cat_symmetry = cat_symmetry_inline
        
        # Get CAT flatness value (use the maximum between crossline and inline if both exist)
        cat_flatness_crossline_field = f'cat_flatness_{field_suffix}_crossline'
        cat_flatness_inline_field = f'cat_flatness_{field_suffix}_inline'
        cat_flatness_crossline = getattr(linac, cat_flatness_crossline_field, None)
        cat_flatness_inline = getattr(linac, cat_flatness_inline_field, None)
        
        # Return separate flatness values for crossline and inline
        cat_flatness_crossline_value = cat_flatness_crossline
        cat_flatness_inline_value = cat_flatness_inline
        
        # Keep the combined flatness value for backward compatibility
        cat_flatness = None
        if cat_flatness_crossline is not None and cat_flatness_inline is not None:
            cat_flatness = max(cat_flatness_crossline, cat_flatness_inline)
        elif cat_flatness_crossline is not None:
            cat_flatness = cat_flatness_crossline
        elif cat_flatness_inline is not None:
            cat_flatness = cat_flatness_inline
        
        return JsonResponse({
            'success': True,
            'cat_d10': cat_d10,
            'cat_output_factor': cat_output_factor,
            'cat_wedge_factor': cat_wedge_factor,
            'cat_symmetry': cat_symmetry,
            'cat_symmetry_crossline': cat_symmetry_crossline_value,
            'cat_symmetry_inline': cat_symmetry_inline_value,
            'cat_flatness': cat_flatness,
            'cat_flatness_crossline': cat_flatness_crossline_value,
            'cat_flatness_inline': cat_flatness_inline_value,
            'linac_name': linac.name,
            'energy': energy
        })
        
    except Linac.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Linac not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting CAT values: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def save_dose_calculation(request):
    """API endpoint to save dose calculation results to session (not database yet)"""
    logger.info("Save dose calculation function called")
    try:
        import json
        
        logger.info(f"Save dose calculation called with method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.body}")
        
        if request.method != 'POST':
            print("❌ Method not allowed")
            return JsonResponse({
                'success': False,
                'error': 'Method not allowed'
            }, status=405)
        
        try:
            data = json.loads(request.body)
            logger.info(f"Received dose calculation data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON: {str(e)}'
            }, status=400)
        
        # Store dose calculation data in session by energy to avoid overwriting
        # when user calculates multiple energies in one QA draft.
        existing_pending = request.session.get('pending_dose_calculation', {})
        if isinstance(existing_pending, dict) and 'linac_id' in existing_pending and 'energy' in existing_pending:
            pending_map = {str(existing_pending.get('energy')): existing_pending}
        elif isinstance(existing_pending, dict):
            pending_map = existing_pending
        else:
            pending_map = {}

        energy_key = str(data.get('energy') or 'unknown')
        pending_map[energy_key] = data
        request.session['pending_dose_calculation'] = pending_map
        logger.info(f"Stored dose calculation data in session")

        # If an existing draft QA record is provided, persist the draft state to DB too.
        qa_record_id = data.get('qa_record_id')
        if qa_record_id:
            try:
                qa_record = QARecord.objects.get(id=int(qa_record_id), performed_by=request.user)
                existing_state = qa_record.draft_dose_calculation_state or {}
                if isinstance(existing_state, dict) and 'linac_id' in existing_state and 'energy' in existing_state:
                    state_map = {str(existing_state.get('energy')): existing_state}
                elif isinstance(existing_state, dict):
                    state_map = existing_state
                else:
                    state_map = {}
                state_map[energy_key] = data
                qa_record.draft_dose_calculation_state = state_map
                qa_record.save(update_fields=['draft_dose_calculation_state', 'updated_at'])
            except Exception as save_err:
                logger.warning(f"Could not persist draft dose state to QA record {qa_record_id}: {save_err}")
        
        return JsonResponse({
            'success': True,
            'message': 'Dose calculation data stored successfully'
        })
        
    except Exception as e:
        print(f"❌ Error in dose calculation save process: {e}")
        logger.error(f"Error in dose calculation save process: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def get_previous_dose_values(request, linac_id):
    """API endpoint to get previous dose calculation values for auto-population"""
    try:
        from ..models import DoseCalculation
        
        # Get the most recent dose calculation for this LINAC
        latest_dose_calc = DoseCalculation.objects.filter(
            linac_id=linac_id
        ).order_by('-created_at').first()
        
        if not latest_dose_calc:
            return JsonResponse({
                'success': False,
                'message': 'No previous dose calculation found for this LINAC'
            })
        
        # Return the values that can be inherited
        inherited_values = {
            'm_plus': latest_dose_calc.m_plus,
            'm_minus': latest_dose_calc.m_minus,
            'm1': latest_dose_calc.m1,
            'm2': latest_dose_calc.m2,
            'v1': latest_dose_calc.v1,
            'v2': latest_dose_calc.v2,
            'created_at': latest_dose_calc.created_at.strftime('%Y-%m-%d %H:%M'),
            'qa_record_id': latest_dose_calc.qa_record.id
        }
        
        return JsonResponse({
            'success': True,
            'inherited_values': inherited_values,
            'message': f'Found previous values from QA record #{latest_dose_calc.qa_record.id} ({latest_dose_calc.created_at.strftime("%Y-%m-%d %H:%M")})'
        })
        
    except Exception as e:
        logger.error(f"Error getting previous dose values: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)

@login_required
def generate_qa_report(request, qa_record_id):
    """Generate DOCX report for a QA record"""
    from ..reporting import generate_qa_report_view
    return generate_qa_report_view(request, qa_record_id)

@require_POST
def shutdown_app(request):
    """
    Desktop app only: signal shutdown when the browser tab/window closes.
    Ignored in server mode so LAN clients closing a tab do not stop the server.
    """
    from QAID_Manager.runtime_mode import is_server_mode

    if is_server_mode():
        return JsonResponse({'status': 'ignored', 'message': 'Server mode active'})

    import sys
    from pathlib import Path
    
    try:
        # Determine the directory where the exe is located (or script directory)
        if getattr(sys, 'frozen', False):
            exe_dir = Path(os.path.dirname(sys.executable))
        else:
            exe_dir = Path(__file__).parent.parent.parent
        
        # Create shutdown flag file
        shutdown_file = exe_dir / 'shutdown_flag.txt'
        try:
            shutdown_file.touch()
        except Exception as e:
            # If we can't create the file, that's okay - just log it
            logger.warning(f"Could not create shutdown flag: {e}")
        
        # Return success even if file creation failed
        return JsonResponse({'status': 'ok', 'message': 'Shutdown signal received'})
    except Exception as e:
        # Don't let shutdown endpoint errors crash the server
        logger.warning(f"Error in shutdown endpoint: {e}")
        return JsonResponse({'status': 'ok', 'message': 'Signal processed'})