"""
QA Schedule Management Views.

This module contains view functions for managing QA schedules, including
monthly schedule display, creating/editing schedules, assigning performers,
and handling QA record synchronization.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from ..models import QASchedule, Linac, QAStatus, QARecord, QATest
from ..forms import QAScheduleForm, QARecordForm, BulkScheduleForm, AdhocQAScheduleForm
from ..services import QAService, QAScheduleService
from ..qa_test_mapping import get_display_order_index, get_test_name_for_field
import json


def _parse_json_body(request):
    """Safely parse JSON request body for AJAX handlers."""
    try:
        return json.loads(request.body or "{}"), None
    except json.JSONDecodeError:
        return None, JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)


def get_failed_tests(qa_record):
    """Get list of failed tests from a QA record.
    Film tests (12, 13, 14) use semantic mapping: app stores test_12=field size,
    test_13=collimator isocenter, test_14=gantry isocenter, which does not match
    QATest order_index (12=Gantry/MLC, 13=Collimator, 14=Field size). So we map
    test_12 -> order_index 14 (field size), test_13 -> 13 (colli), test_14 -> 12 (gantry).
    Other tests use position: test_i -> i-th test in order_index order.
    """
    failed_tests = []
    
    if not qa_record or not qa_record.is_failed():
        return failed_tests
    
    ordered_tests = list(QATest.objects.filter(is_active=True).order_by('order_index'))

    for i in range(1, 21):
        test_field = f'test_{i:02d}'
        test_value = getattr(qa_record, test_field, None)

        if test_value is not None:
            try:
                tolerance_value, _ = QAService.get_tolerance_for_test(
                    get_display_order_index(i)
                )
                if abs(test_value) > tolerance_value:
                    test_name = get_test_name_for_field(i, ordered_tests)
                    failed_tests.append({
                        'test_number': i,
                        'test_name': test_name,
                        'value': test_value,
                        'tolerance': tolerance_value
                    })
            except Exception:
                continue
    
    return failed_tests


@login_required
def qa_schedule_monthly(request):
    """Display the monthly QA schedule with one cell per LINAC"""
    # Get month/year from request, default to current month
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    month = int(month)
    year = int(year)
    
    # Temporary: Force clean interface for current month
    force_clean = request.GET.get('clean', 'false').lower() == 'true'
    
    # Create the month_year date for the first day of the month
    month_year = date(year, month, 1)
    
    # Get existing QA schedules for this month only (do not auto-create, only show created schedules)
    schedules = QASchedule.objects.filter(month_year=month_year).order_by('linac__name')
    
    # Get all active LINACs for reference (used in context but not displayed)
    active_linacs = Linac.objects.filter(is_active=True)
    
    # Get QA records for this month to sync with schedules
    qa_records = QARecord.objects.filter(
        date_performed__year=year,
        date_performed__month=month
    )
    
    # Sync QA records with schedules
    for schedule in schedules:
        # Skip if schedule has no LINAC (shouldn't happen, but safety check)
        if not schedule.linac:
            continue
        
        # Track latest draft QA record for resume flow
        draft_record = QARecord.objects.filter(
            qa_schedule=schedule,
            is_draft=True
        ).order_by('-updated_at', '-date_performed').first()
        schedule.has_draft = draft_record is not None
        schedule.draft_record_id = draft_record.id if draft_record else None

        # Find FINAL QA records directly linked to this schedule
        qa_records_for_schedule = QARecord.objects.filter(
            qa_schedule=schedule,
            is_draft=False
        ).order_by('-date_performed')
        
        # If no directly linked records, try to find by LINAC and month/year
        # This allows non-scheduled QA to appear on schedule pages
        # BUT we only link if the schedule doesn't already have a QA record
        # This prevents overwriting existing scheduled QA results
        if not qa_records_for_schedule.exists() and schedule.month_year:
            # Only find QA records that are NOT already linked to another schedule
            # This ensures each QA record maintains its independence
            potential_qa_records = QARecord.objects.filter(
                linac=schedule.linac,
                date_performed__year=year,
                date_performed__month=month,
                is_draft=False,
                qa_schedule__isnull=True  # Only unlinked QA records
            ).order_by('-date_performed')
            
            # Only link if schedule doesn't already have a QA record
            # For regular (non-adhoc) schedules, only link if no existing QA record
            # For adhoc schedules, we can link multiple QA records
            if potential_qa_records.exists():
                if schedule.is_adhoc:
                    # Adhoc schedules can have multiple QA records
                    for qa_record in potential_qa_records:
                        qa_record.qa_schedule = schedule
                        qa_record.save()
                    qa_records_for_schedule = QARecord.objects.filter(
                        qa_schedule=schedule,
                        is_draft=False
                    ).order_by('-date_performed')
                else:
                    # Regular schedules: only link if no existing QA record
                    # This prevents non-scheduled QA from overwriting scheduled QA
                    qa_record = potential_qa_records.first()
                    qa_record.qa_schedule = schedule
                    qa_record.save()
                    qa_records_for_schedule = QARecord.objects.filter(
                        qa_schedule=schedule,
                        is_draft=False
                    ).order_by('-date_performed')
        
        if qa_records_for_schedule.exists():
            # Use the most recent QA record that is directly linked to this schedule
            qa_record = qa_records_for_schedule.first()
            
            # Store the QA record for template access (always, even if status is None)
            schedule.qa_record = qa_record
            
            # IMPORTANT: Only update schedule with data from the QA record that is linked to it
            # Each QA record maintains its own independent results
            # For regular (non-adhoc) schedules, prefer the first/linked QA record
            # For adhoc schedules, use the most recent QA record
            if qa_record.performed_by and qa_record.status:
                # Update schedule with THIS QA record's data only
                # This ensures each QA record's results are independent
                schedule.performer1 = qa_record.performed_by
                schedule.status = qa_record.status
                schedule.qa_date = qa_record.date_performed
                
                # Update notes if QA failed
                if qa_record.notes and "results out of tolerances" in qa_record.notes.lower():
                    schedule.notes = qa_record.notes
                
                # Get failed tests from THIS QA record only
                if qa_record.is_failed():
                    failed_tests = get_failed_tests(qa_record)
                    schedule.failed_tests = failed_tests
                    # Store failed tests data for THIS QA record
                    schedule.failed_tests_data = failed_tests
                
                # Use stored failed tests data if available (for accepted failed QA)
                elif schedule.failed_tests_data:
                    schedule.failed_tests = schedule.failed_tests_data
                
                schedule.save()
            elif qa_record.performed_by:
                # QA record exists but no status - still update performer and date
                schedule.performer1 = qa_record.performed_by
                schedule.qa_date = qa_record.date_performed
                schedule.save()
        else:
            # No QA records exist for this schedule - clear the status and QA date
            if schedule.status or schedule.qa_date or schedule.is_accepted:
                schedule.status = None
                schedule.qa_date = None
                schedule.notes = ""  # Clear notes too
                schedule.is_accepted = False  # Reset acceptance status
                schedule.failed_tests_data = []  # Clear stored failed tests data
                schedule.save()
    
    # Get filter options
    performers = User.objects.filter(is_active=True)
    
    # Calculate previous and next month
    current_date = date(year, month, 1)
    prev_month = current_date - relativedelta(months=1)
    next_month = current_date + relativedelta(months=1)
    
    context = {
        'schedules': schedules,
        'month_year': month_year,
        'current_month': month,
        'current_year': year,
        'prev_month': prev_month,
        'next_month': next_month,
        'performers': performers,
        'active_linacs': active_linacs,
    }
    
    return render(request, 'QAID_Manager/qa_schedule_monthly.html', context)


@login_required
@require_http_methods(["POST"])
def assign_performers(request):
    """Handle AJAX request to assign performers and expected date to a QA schedule"""
    try:
        data, error_response = _parse_json_body(request)
        if error_response:
            return error_response
        QAScheduleService.assign_performers(
            schedule_id=data.get('schedule_id'),
            performer1_id=data.get('performer1_id'),
            performer2_id=data.get('performer2_id'),
            expected_qa_date=data.get('expected_qa_date'),
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def confirm_schedule(request):
    """Handle AJAX request to confirm schedule assignment (same as assign_performers)"""
    try:
        data, error_response = _parse_json_body(request)
        if error_response:
            return error_response
        QAScheduleService.confirm_schedule(
            schedule_id=data.get('schedule_id'),
            linac_id=data.get('linac_id'),
            performer1_id=data.get('performer1_id'),
            performer2_id=data.get('performer2_id'),
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def create_schedule(request):
    """Handle AJAX request to create a new QA schedule"""
    try:
        data, error_response = _parse_json_body(request)
        if error_response:
            return error_response
        schedule = QAScheduleService.create_schedule(
            date_str=data.get('date'),
            linac_id=data.get('linac_id'),
            performer1_id=data.get('performer1_id'),
            performer2_id=data.get('performer2_id'),
        )
        return JsonResponse({'success': True, 'schedule_id': schedule.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def accept_failed_qa(request, schedule_id):
    """Manually accept failed QA results and change status to PASSED WITH EXCEPTION (with logging)"""
    schedule = get_object_or_404(QASchedule, id=schedule_id)
    
    if request.method == 'POST':
        if schedule.is_failed() and not schedule.is_accepted:
            # Get the "passed_with_exception" status
            passed_with_exception_status = QAStatus.objects.filter(name='passed_with_exception').first()
            
            if passed_with_exception_status:
                # Change status from FAILED to PASSED WITH DEVIATION
                schedule.status = passed_with_exception_status
                schedule.is_accepted = True
                schedule.accepted_by = request.user
                schedule.accepted_at = timezone.now()
                schedule.save()
                
                # Log the acceptance activity
                from ..models import UserActivity
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='qa_update',
                    description=f'Accepted failed QA for {schedule.linac.name} - {schedule.month_year.strftime("%B %Y")}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # Also update the corresponding QA record if it exists
                qa_records = QARecord.objects.filter(
                    linac=schedule.linac,
                    date_performed__year=schedule.month_year.year,
                    date_performed__month=schedule.month_year.month,
                    is_draft=False
                )
                
                if qa_records.exists():
                    # Update the most recent QA record
                    qa_record = qa_records.order_by('-date_performed').first()
                    qa_record.status = passed_with_exception_status
                    qa_record.save()
                
                messages.success(request, 'Failed QA results have been accepted and status changed to PASSED WITH DEVIATION.')
            else:
                messages.error(request, 'Could not find "passed_with_exception" status in database.')
        else:
            messages.error(request, 'This QA does not need acceptance or has already been accepted.')
    
    # Redirect back to the monthly schedule view
    return redirect('qa_schedule_monthly')


@login_required
def create_qa_schedule(request):
    """Create a manual QA schedule (single schedule)"""
    if request.method == 'POST':
        form = QAScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.save()
            messages.success(request, 'QA schedule created successfully.')
            return redirect('qa_schedule_monthly')
    else:
        form = QAScheduleForm()
    
    context = {
        'form': form,
        'title': 'Create QA Schedule'
    }
    
    return render(request, 'QAID_Manager/qa_schedule_form.html', context)


@login_required
def create_bulk_schedule(request):
    """Bulk create QA schedules for multiple machines with frequency"""
    if request.method == 'POST':
        form = BulkScheduleForm(request.POST)
        if form.is_valid():
            linacs = form.cleaned_data['linacs']
            frequency_months = form.cleaned_data['frequency_months']
            start_month = form.cleaned_data['start_month']
            end_month = form.cleaned_data['end_month']
            qa_reason = form.cleaned_data.get('qa_reason', '')
            
            # Generate schedules for each month in the range
            current_month = start_month.replace(day=1)
            end_month_first = end_month.replace(day=1)
            schedules_created = 0
            
            while current_month <= end_month_first:
                for linac in linacs:
                    # Check if schedule already exists for this month and linac
                    schedule, created = QASchedule.objects.get_or_create(
                        linac=linac,
                        month_year=current_month,
                        defaults={
                            'qa_reason': qa_reason or f'QA for {linac.name}',
                            'notes': ''
                        }
                    )
                    if created:
                        schedules_created += 1
                
                # Move to next month based on frequency
                current_month = current_month + relativedelta(months=frequency_months)
            
            messages.success(request, f'Successfully created {schedules_created} QA schedule(s).')
            return redirect('qa_schedule_monthly')
    else:
        form = BulkScheduleForm()
    
    context = {
        'form': form,
        'title': 'Create Bulk QA Schedule'
    }
    
    return render(request, 'QAID_Manager/qa_schedule_bulk_create.html', context)


@login_required
def create_adhoc_qa_schedule(request):
    """Create a non-scheduled QA session for unexpected QA (breakdown, maintenance, etc.)"""
    if request.method == 'POST':
        form = AdhocQAScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.is_adhoc = True
            # Auto-set month_year from expected_qa_date
            if schedule.expected_qa_date:
                schedule.month_year = schedule.expected_qa_date.replace(day=1)
            
            # Check if a regular (non-adhoc) schedule already exists for this LINAC and month
            existing_schedule = QASchedule.objects.filter(
                linac=schedule.linac,
                month_year=schedule.month_year,
                is_adhoc=False
            ).first()
            
            if existing_schedule:
                # Allow ad-hoc schedule even if regular schedule exists
                # This is intentional - ad-hoc schedules are for unexpected QA
                pass
            
            schedule.save()
            messages.success(request, 'Non-scheduled QA created successfully.')
            return redirect('qa_schedule_monthly')
    else:
        form = AdhocQAScheduleForm()
    
    context = {
        'form': form,
        'title': 'Create Non-scheduled QA'
    }
    
    return render(request, 'QAID_Manager/qa_schedule_adhoc_form.html', context)


@login_required
def edit_qa_schedule(request, schedule_id):
    """Edit a QA schedule (admin only)"""
    schedule = get_object_or_404(QASchedule, id=schedule_id)
    
    # Check if user is admin or if schedule is not completed
    if not request.user.is_staff and schedule.is_completed():
        messages.error(request, 'Only administrators can edit completed QA schedules.')
        return redirect('qa_schedule_monthly')
    
    if request.method == 'POST':
        form = QAScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, 'QA schedule updated successfully.')
            return redirect('qa_schedule_monthly')
    else:
        form = QAScheduleForm(instance=schedule)
    
    context = {
        'form': form,
        'schedule': schedule,
        'title': 'Edit QA Schedule'
    }
    
    return render(request, 'QAID_Manager/qa_schedule_form.html', context)


@login_required
def view_qa_records(request, schedule_id):
    """View QA records in read-only mode using existing QA form"""
    schedule = get_object_or_404(QASchedule, id=schedule_id)
    
    # First, try to find QA records directly linked to this schedule
    qa_records = QARecord.objects.filter(qa_schedule=schedule, is_draft=False).order_by('-date_performed')
    
    # If no directly linked records, try to find by LINAC and month/year
    # This allows non-scheduled QA to be viewed, but only if not already linked to another schedule
    if not qa_records.exists() and schedule.month_year:
        qa_records = QARecord.objects.filter(
            linac=schedule.linac,
            date_performed__year=schedule.month_year.year,
            date_performed__month=schedule.month_year.month,
            is_draft=False,
            qa_schedule__isnull=True  # Only show unlinked QA records
        ).order_by('-date_performed')
    
    if not qa_records.exists():
        messages.error(request, 'No QA records found for this schedule.')
        return redirect('qa_schedule_monthly')
    
    qa_record = qa_records.first()
    
    # Pre-populate form data from the QA record
    initial_data = {
        'linac': qa_record.linac,
        'date_performed': qa_record.date_performed,
        'performed_by': qa_record.performed_by,
        'status': qa_record.status,
        'notes': qa_record.notes,
    }
    
    # Add all test fields
    for i in range(1, 21):
        test_field = f'test_{i:02d}'
        test_value = getattr(qa_record, test_field, None)
        if test_value is not None:
            initial_data[test_field] = test_value
    
    # Create form with initial data
    form = QARecordForm(initial=initial_data)
    
    # Make all fields read-only
    for field_name, field in form.fields.items():
        field.widget.attrs['readonly'] = 'readonly'
        field.widget.attrs['disabled'] = 'disabled'
    
    # Get QA tests organized by type from database (same as qa_entry view)
    from ..services import QAService
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
    
    # Get film analysis images from stored QAFilmAnalysis objects (similar to Django admin)
    # Order: fieldsize, collimator_isocenter, gantry_isocenter
    from ..models import QAFilmAnalysis
    analysis_type_order = {'fieldsize': 1, 'collimator_isocenter': 2, 'gantry_isocenter': 3}
    film_analyses = sorted(
        qa_record.film_analyses.all(),
        key=lambda x: (analysis_type_order.get(x.analysis_type, 99), -x.created_at.timestamp())
    )
    
    # Prepare data for the existing template
    mechanical_group = mechanical_tests
    beam_group = beam_tests
    film_group = film_tests
    isocenter_group = isocenter_tests
    
    # Create isocenter matrix rows for the interactive matrix (same as qa_entry view)
    isocenter_matrix_rows = [
        (8, "Tâm dây chữ thập"),      # Test #8
        (9, "Đồng tâm quay collimator"),  # Test #9
        (10, "Đồng tâm quay bàn điều trị")  # Test #10
    ]
    
    # Create angle list for isocenter
    angle_list = [0, 90, 135, 180]
    
    # Create a dictionary of test values and tolerances for JavaScript to populate
    test_values = {}
    test_tolerances = {}
    
    for i in range(1, 21):
        test_field = f'test_{i:02d}'
        test_value = getattr(qa_record, test_field, None)
        if test_value is not None:
            test_values[test_field] = test_value
            
            # Get tolerance for this test
            test_obj = QATest.objects.filter(order_index=i, is_active=True).first()
            if test_obj:
                test_tolerances[test_field] = test_obj.tolerance_value
            else:
                # Default tolerances if test not found
                if i <= 14:
                    test_tolerances[test_field] = 2  # mechanical default
                else:
                    test_tolerances[test_field] = 3  # beam default
    
    # Extract isocenter matrix data for populating the matrix inputs
    isocenter_matrix_values = qa_record.isocenter_matrix_data or {}
    
    # Extract multi-energy beam test results
    beam_test_results_by_energy = qa_record.beam_test_results or {}
    
    # Extract test notes
    from ..models import QATestNote
    test_notes = {}
    for note in qa_record.test_notes.all():
        test_notes[note.test_number] = note.note_text
    
    # Reconstruct dose calculator state from saved DoseCalculation objects
    from ..models import DoseCalculation
    dose_state_for_view = {}
    for dc in DoseCalculation.objects.filter(qa_record=qa_record).select_related('linac', 'detector'):
        energy_key = str(dc.energy)
        dose_state_for_view[energy_key] = {
            'linac_id': dc.linac_id,
            'energy': dc.energy,
            'detector_id': dc.detector_id,
            'phantom': dc.phantom,
            'raw_measurement': dc.raw_measurement,
            'temperature': dc.temperature,
            'pressure': dc.pressure,
            'm_plus': dc.m_plus,
            'm_minus': dc.m_minus,
            'm1': dc.m1,
            'm2': dc.m2,
            'v1': dc.v1,
            'v2': dc.v2,
            'v1_v2_ratio': dc.v1_v2_ratio,
            'a0': dc.a0,
            'a1': dc.a1,
            'a2': dc.a2,
            'ktp_result': dc.ktp_result,
            'kpol_result': dc.kpol_result,
            'ks_result': dc.ks_result,
            'solid_phantom_factor': dc.solid_phantom_factor,
            'mq_result': dc.mq_result,
            'dwq_zref': dc.dwq_zref,
            'dwq_zmax': dc.dwq_zmax,
            'absolute_setup_mode': dc.absolute_setup_mode,
            'pdd_zref': dc.pdd_zref,
            'pdd_zref_source': dc.pdd_zref_source,
            'pdd_20_10': dc.pdd_20_10,
            'tmr': dc.tmr,
            'tpr_20_10': dc.tpr_20_10,
            'kq_factor': dc.kq_factor,
            'm_ref': dc.m_ref,
            'm_left': dc.m_left,
            'm_right': dc.m_right,
            'm_gun': dc.m_gun,
            'm_tar': dc.m_tar,
            'm_mid': dc.m_mid,
            'm_wedge': dc.m_wedge,
            'm_dmax': dc.m_dmax,
            'm_d10': dc.m_d10,
            'symmetry_crossline': dc.symmetry_crossline,
            'symmetry_inline': dc.symmetry_inline,
            'flatness_crossline': dc.flatness_crossline,
            'flatness_inline': dc.flatness_inline,
            'output_factor': dc.output_factor,
            'wedge_factor': dc.wedge_factor,
            'beam_energy_d10': dc.beam_energy_d10,
            'mu_10': dc.mu_10,
            'mu_30': dc.mu_30,
            'mu_50': dc.mu_50,
            'mu_100': dc.mu_100,
            'mu_300': dc.mu_300,
            'mu_500': dc.mu_500,
            'mu_r2': dc.mu_r2,
            'absolute_dose_deviation': dc.absolute_dose_deviation,
            'energy_stability_d10': dc.energy_stability_d10,
            'symmetry_vs_commissioning': dc.symmetry_vs_commissioning,
            'flatness_vs_commissioning': dc.flatness_vs_commissioning,
            'output_factor_deviation': dc.output_factor_deviation,
        }

    # Separate film sub-groups for template rendering (IDs align with DB order_index)
    fieldsize_group = [t for t in film_tests if t[0] == 12]
    colliiso_group = [t for t in film_tests if t[0] == 13]
    gantryiso_group = [t for t in film_tests if t[0] == 14]

    context = {
        'form': form,
        'qa_record': qa_record,
        'schedule': schedule,
        'mechanical_group': mechanical_group,
        'beam_group': beam_group,
        'film_group': film_group,
        'fieldsize_group': fieldsize_group,
        'colliiso_group': colliiso_group,
        'gantryiso_group': gantryiso_group,
        'isocenter_group': isocenter_group,
        'isocenter_matrix_rows': isocenter_matrix_rows,
        'angle_list': angle_list,
        'film_analyses': film_analyses,
        'title': 'View QA Records',
        'is_readonly': True,
        'temp_qa_record_id': qa_record.id,
        'test_values': test_values,
        'test_tolerances': test_tolerances,
        'isocenter_matrix_values': isocenter_matrix_values,
        'beam_test_results_by_energy': beam_test_results_by_energy,
        'test_notes': test_notes,
        'draft_dose_calculation_state': dose_state_for_view,
        'custom_test_types': custom_test_types,
        'custom_test_results_json': qa_record.custom_test_results or {},
    }
    
    return render(request, 'QAID_Manager/qa_form.html', context)


@login_required
@require_http_methods(["POST"])
def update_schedule_notes(request, schedule_id):
    """Update schedule notes with edit history tracking"""
    try:
        data, error_response = _parse_json_body(request)
        if error_response:
            return error_response
        schedule = QAScheduleService.update_schedule_notes(
            schedule_id=schedule_id,
            new_notes=data.get('notes', ''),
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return JsonResponse({
            'success': True,
            'notes': schedule.notes,
            'edit_history': schedule.notes_edit_history[-5:]  # Return last 5 edits
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_qa_status_color(schedule):
    """Get status color for QA schedule"""
    if not schedule.status:
        return None
    
    if schedule.status.name == 'passed':
        return '#28a745'  # Green
    elif schedule.status.name == 'passed_with_exception':
        return '#ffc107'  # Yellow/Orange
    elif schedule.status.name in ['failed', 'minor_service', 'major_service']:
        return '#ff6b6b'  # Pale red
    else:
        return '#6c757d'  # Gray


def sync_qa_status_from_records():
    """Sync QA status from QARecord data for month-based schedules"""
    schedules = QASchedule.objects.all()
    passed_status = QAStatus.objects.filter(name='passed').first()
    failed_status = QAStatus.objects.filter(name='failed').first()
    
    for schedule in schedules:
        if not schedule.month_year:
            continue
            
        # Find corresponding QA records for this month
        qa_records = QARecord.objects.filter(
            linac=schedule.linac,
            date_performed__year=schedule.month_year.year,
            date_performed__month=schedule.month_year.month,
            is_draft=False
        )
        
        if qa_records.exists():
            # Use the most recent QA record
            qa_record = qa_records.order_by('-date_performed').first()
            
            # Update performers from QA record
            if qa_record.performed_by:
                schedule.performer1 = qa_record.performed_by
            
            # Set actual QA date
            schedule.qa_date = qa_record.date_performed
            
            # Determine status based on test results
            if qa_record.notes:
                if "All tests within tolerance" in qa_record.notes:
                    schedule.status = passed_status
                elif "results out of tolerances" in qa_record.notes:
                    schedule.status = failed_status
            
            schedule.save()
        else:
            # No QA records exist for this schedule - clear the status and QA date
            if schedule.status or schedule.qa_date or schedule.is_accepted:
                schedule.status = None
                schedule.qa_date = None
                schedule.notes = ""  # Clear notes too
                schedule.is_accepted = False  # Reset acceptance status
                schedule.failed_tests_data = []  # Clear stored failed tests data
                schedule.save()
    
    return True 