"""
LINAC Service Report Management Views.

This module contains view functions for managing LINAC service and error reports:
- Listing service reports with filtering
- Creating, editing, and deleting service reports
- Viewing report details
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum, Q
from django.http import HttpResponseBadRequest
from datetime import date

from ..models import Linac, Device, LinacServiceReport
from ..forms import LinacServiceReportForm
from ..service_report_generator import ServiceReportGenerator


@login_required
def linac_management(request):
    """Main page for Equipment Management - displays equipment service reports."""
    service_reports = LinacServiceReport.objects.select_related('linac', 'device').all()
    is_admin = request.user.is_staff
    
    # Get filter parameters from request
    equipment_filter = request.GET.get('equipment', '')
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    keyword = request.GET.get('q', '').strip()
    
    # Apply filters
    if equipment_filter:
        if equipment_filter.startswith('linac-'):
            linac_id = equipment_filter.split('-', 1)[1]
            service_reports = service_reports.filter(linac_id=linac_id)
        elif equipment_filter.startswith('device-'):
            device_id = equipment_filter.split('-', 1)[1]
            service_reports = service_reports.filter(device_id=device_id)
    
    if type_filter == 'pm_service':
        service_reports = service_reports.filter(pm_service=True)
    elif type_filter == 'equipment_breakdown':
        service_reports = service_reports.filter(equipment_breakdown=True)
    elif type_filter == 'both':
        service_reports = service_reports.filter(pm_service=True, equipment_breakdown=True)
    
    if status_filter:
        service_reports = service_reports.filter(status=status_filter)
    
    # Apply date range filters
    if date_from:
        service_reports = service_reports.filter(date__gte=date_from)
    if date_to:
        service_reports = service_reports.filter(date__lte=date_to)

    if keyword:
        service_reports = service_reports.filter(
            Q(issue_description__icontains=keyword) |
            Q(follow_up_actions__icontains=keyword) |
            Q(parts_replacement__icontains=keyword) |
            Q(notes__icontains=keyword)
        )
    
    # Order results
    service_reports = service_reports.order_by('-date', '-created_at')
    
    # Get active equipment for filter dropdown
    linacs = Linac.objects.filter(is_active=True).order_by('name')
    devices = Device.objects.filter(is_active=True).order_by('category', 'name')
    equipment_options = (
        [(f'linac-{linac.id}', linac.name) for linac in linacs] +
        [(f'device-{device.id}', device.name) for device in devices]
    )

    # Summary cards: always show statistics for all LINAC-related reports.
    linac_reports_all = LinacServiceReport.objects.filter(linac__isnull=False)
    summary = {
        'total_linacs': Linac.objects.count(),
        'total_linac_reports': linac_reports_all.count(),
        'completed_count': linac_reports_all.filter(status='completed').count(),
        'pending_count': linac_reports_all.filter(status='pending').count(),
        'temporary_count': linac_reports_all.filter(status='temporary').count(),
        'total_downtime_hours': linac_reports_all.aggregate(total=Sum('downtime_hours'))['total'] or 0,
    }

    linac_stats = []
    for linac in Linac.objects.order_by('name'):
        qs = LinacServiceReport.objects.filter(linac=linac)
        linac_stats.append({
            'linac': linac,
            'reports': qs.count(),
            'completed': qs.filter(status='completed').count(),
            'pending': qs.filter(status='pending').count(),
            'temporary': qs.filter(status='temporary').count(),
            'downtime_hours': qs.aggregate(total=Sum('downtime_hours'))['total'] or 0,
        })

    # Device dashboards: only equipment with pending/temporary reports.
    device_stats = []
    other_stats = []
    for device in Device.objects.order_by('name'):
        qs = LinacServiceReport.objects.filter(device=device)
        pending_count = qs.filter(status='pending').count()
        temporary_count = qs.filter(status='temporary').count()
        if pending_count == 0 and temporary_count == 0:
            continue
        stat = {
            'device': device,
            'reports': qs.count(),
            'completed': qs.filter(status='completed').count(),
            'pending': pending_count,
            'temporary': temporary_count,
            'downtime_hours': qs.aggregate(total=Sum('downtime_hours'))['total'] or 0,
        }
        if device.category == 'others':
            other_stats.append(stat)
        else:
            device_stats.append(stat)
    
    return render(request, 'QAID_Manager/linac_management.html', {
        'service_reports': service_reports,
        'is_admin': is_admin,
        'equipment_options': equipment_options,
        'current_equipment_filter': equipment_filter,
        'current_type_filter': type_filter,
        'current_status_filter': status_filter,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_keyword': keyword,
        'summary': summary,
        'linac_stats': linac_stats,
        'device_stats': device_stats,
        'other_stats': other_stats,
    })


@login_required
def service_report_detail(request, pk):
    """View equipment service report details."""
    report = get_object_or_404(LinacServiceReport, pk=pk)
    is_admin = request.user.is_staff
    
    return render(request, 'QAID_Manager/service_report_detail.html', {
        'report': report,
        'is_admin': is_admin
    })


@login_required
def service_report_create(request):
    """Create a new equipment service report."""
    if request.method == 'POST':
        form = LinacServiceReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user
            report.save()
            messages.success(request, f'Equipment service report for {report.get_equipment_display()} created successfully.')
            return redirect('linac_management')
    else:
        form = LinacServiceReportForm()
    
    return render(request, 'QAID_Manager/service_report_form.html', {
        'form': form,
        'title': 'Create Equipment Service Report'
    })


@login_required
def service_report_edit(request, pk):
    """Edit an existing equipment service report."""
    report = get_object_or_404(LinacServiceReport, pk=pk)
    
    if request.method == 'POST':
        form = LinacServiceReportForm(request.POST, instance=report)
        if form.is_valid():
            report = form.save()
            messages.success(request, f'Equipment service report for {report.get_equipment_display()} updated successfully.')
            return redirect('linac_management')
    else:
        form = LinacServiceReportForm(instance=report)
    
    return render(request, 'QAID_Manager/service_report_form.html', {
        'form': form,
        'report': report,
        'title': f'Edit Equipment Service Report: {report.get_equipment_display()}'
    })


@login_required
@staff_member_required
def service_report_delete(request, pk):
    """Delete an equipment service report (admin only)."""
    report = get_object_or_404(LinacServiceReport, pk=pk)
    
    if request.method == 'POST':
        equipment_name = report.get_equipment_display()
        report.delete()
        messages.success(request, f'Equipment service report for {equipment_name} deleted successfully.')
        return redirect('linac_management')
    
    return render(request, 'QAID_Manager/service_report_confirm_delete.html', {
        'report': report
    })


@login_required
@require_POST
def service_report_print_selected(request):
    ids = request.POST.getlist('report_ids')
    output_format = (request.POST.get('format', 'pdf') or 'pdf').strip().lower()
    if output_format not in ('pdf', 'docx'):
        output_format = 'pdf'
    preview = request.POST.get('preview') == '1'
    if not ids:
        return HttpResponseBadRequest("No report selected.")

    reports = list(
        LinacServiceReport.objects.select_related('linac', 'device')
        .filter(id__in=ids)
        .order_by('date', 'id')
    )
    generator = ServiceReportGenerator()
    return generator.build_response(reports, output_format=output_format, preview=preview)


@login_required
@require_POST
def service_report_print_periodic(request):
    date_from_raw = request.POST.get('date_from')
    date_to_raw = request.POST.get('date_to')
    output_format = (request.POST.get('format', 'pdf') or 'pdf').strip().lower()
    if output_format not in ('pdf', 'docx'):
        output_format = 'pdf'
    preview = request.POST.get('preview') == '1'

    if not date_from_raw or not date_to_raw:
        return HttpResponseBadRequest("Date range is required.")
    try:
        date_from = date.fromisoformat(date_from_raw)
        date_to = date.fromisoformat(date_to_raw)
    except ValueError:
        return HttpResponseBadRequest("Invalid date format.")
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    reports = list(
        LinacServiceReport.objects.select_related('linac', 'device')
        .filter(
            Q(date__gte=date_from, date__lte=date_to) |
            Q(status__in=['pending', 'temporary'])
        )
        .order_by('date', 'id')
    )
    generator = ServiceReportGenerator()
    return generator.build_response(
        reports,
        output_format=output_format,
        preview=preview,
        date_from=date_from,
        date_to=date_to,
    )

