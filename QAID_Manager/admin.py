"""
Django Admin configuration for QAID Manager.

This module registers all models with the Django admin interface and provides
custom admin classes with enhanced display, filtering, and actions.
"""
from django.contrib import admin
from .models import (
    Linac, QARecord, QATest, QAStatus, QASchedule, 
    UserActivity, FilmUpload, Dosimeter,
    QAFilmAnalysis, QATestNote, PhysicsParameters, DoseCalculation,
    VietnameseHoliday, DosimeterDocument, LinacDocument, Device, DeviceDocument,
    LinacServiceReport
)
from django.utils.html import mark_safe, format_html
from django import forms
from django.urls import reverse
import os
from datetime import datetime
from .reporting import QAReportGenerator

# ============================================================================
# Test Name and Tolerance Mappings
# ============================================================================

# Test name mapping for admin display (Vietnamese names for QA tests)
TEST_NAME_MAPPING = {
    'test_01': 'Kích thước trường ánh sáng (đối xứng và bất đối xứng)',
    'test_02': 'Góc quay bộ chuẩn trực (collimator)',
    'test_03': 'Góc quay bàn điều trị',
    'test_04': 'Độ chính xác trong chuyển động của Bàn điều trị',
    'test_05': 'Góc quay thân máy (gantry)',
    'test_06': 'Độ chính xác của chùm laser tại điểm đồng tâm',
    'test_07': 'Độ chính xác của ODI',
    'test_08': 'Tâm dây chữ thập',
    'test_09': 'Đồng tâm quay collimator',
    'test_10': 'Đồng tâm quay bàn điều trị',
    'test_11': 'Đồng tâm quay gantry',
    'test_12': 'Field Size Analysis',
    'test_13': 'Collimator Isocenter Circle Diameter',
    'test_14': 'Gantry Isocenter Circle Diameter',
    'test_15': 'Liều tuyệt đối',
    'test_16': 'Sự ổn định của năng lượng (D10)',
    'test_17': 'Tính đối xứng so với giá trị tại thời điểm commissioning',
    'test_18': 'Tính phẳng so với giá trị tại thời điểm commissioning',
    'test_19': 'Tính tuyến tính của liều và số MU',
    'test_20': 'Hệ số liều lối ra theo kích thước trường chiếu',
}

# Tolerance mapping for each test (used for pass/fail determination)
TEST_TOLERANCE_MAPPING = {
    'test_01': 1.0,  # mm
    'test_02': 1.0,  # độ
    'test_03': 1.0,  # độ
    'test_04': 1.0,  # mm
    'test_05': 1.0,  # độ
    'test_06': 1.0,  # mm
    'test_07': 1.0,  # mm
    'test_08': 1.0,  # mm
    'test_09': 1.0,  # mm
    'test_10': 1.0,  # mm
    'test_11': 2.0,  # mm
    'test_12': 1.0,  # mm
    'test_13': 1.0,  # mm
    'test_14': 1.0,  # mm
    'test_15': 2.0,  # %
    'test_16': 1.0,  # %
    'test_17': 3.0,  # %
    'test_18': 3.0,  # %
    'test_19': 1.0,  # %
    'test_20': 2.0,  # %
}

# ============================================================================
# Custom Admin Forms
# ============================================================================

class LinacAdminForm(forms.ModelForm):
    """
    Custom form for Linac admin with CAT test headings.
    """
    class Meta:
        model = Linac
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom labels for better organization
        self.fields['cat_gantry_isocenter'].label = 'Gantry Isocenter'
        self.fields['cat_d10_6mv'].label = 'D10 6MV'
        self.fields['cat_uniformity'].label = 'Uniformity'

# ============================================================================
# Model Admin Classes
# ============================================================================

@admin.register(Linac)
class LinacAdmin(admin.ModelAdmin):
    """
    Admin interface for LINAC model.
    
    Provides enhanced display, filtering, and organization of LINAC fields
    including CAT test results and beam modelling information.
    """
    form = LinacAdminForm
    list_display = ['name', 'series_number', 'energy_display', 'dosimetry_method', 'installation_date', 'certification_due_date', 'is_active']
    list_filter = ['is_active', 'dosimetry_method', 'installation_date', 'created_at']
    search_fields = ['name', 'series_number']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    def energy_display(self, obj):
        """Display energy options as comma-separated list"""
        if obj.energy:
            return ", ".join(obj.energy)
        return "No energy selected"
    energy_display.short_description = 'Năng lượng'
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to use custom form for energy field"""
        form = super().get_form(request, obj, **kwargs)
        if 'energy' in form.base_fields:
            # Convert JSONField to MultipleChoiceField
            from django import forms
            form.base_fields['energy'] = forms.MultipleChoiceField(
                choices=Linac.ENERGY_CHOICES,
                widget=forms.CheckboxSelectMultiple,
                required=False,
                label="Năng lượng"
            )
            # Set initial value from JSON data
            if obj and obj.energy:
                form.base_fields['energy'].initial = obj.energy
        return form
    
    def save_model(self, request, obj, form, change):
        """Save the energy field as JSON"""
        if 'energy' in form.cleaned_data:
            obj.energy = form.cleaned_data['energy']
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/custom_linac_admin.css',)
        }
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to add custom form with headings"""
        form = super().get_form(request, obj, **kwargs)
        if 'energy' in form.base_fields:
            # Convert JSONField to MultipleChoiceField
            from django import forms
            form.base_fields['energy'] = forms.MultipleChoiceField(
                choices=Linac.ENERGY_CHOICES,
                widget=forms.CheckboxSelectMultiple,
                required=False,
                label="Năng lượng"
            )
            # Set initial value from JSON data
            if obj and obj.energy:
                form.base_fields['energy'].initial = obj.energy
        return form
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override to add custom context for headings"""
        extra_context = extra_context or {}
        extra_context['show_cat_headings'] = True
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override to add custom context for headings"""
        extra_context = extra_context or {}
        extra_context['show_cat_headings'] = True
        return super().add_view(request, form_url, extra_context)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'series_number', 'is_active')
        }),
        ('Installation & Certification', {
            'fields': ('installation_date', 'certification_due_date')
        }),
        ('Technical Specifications', {
            'fields': ('energy', 'dosimetry_method')
        }),
        ('CAT Information', {
            'fields': (
                'cat_info',
                ('cat_gantry_isocenter', 'cat_collimator_isocenter', 'cat_field_size_12x12', 'cat_table_isocenter', 
                 'cat_table_rotation', 'cat_table_height_isocenter', 'cat_table_height', 'cat_table_long', 'cat_table_lateral'),
                ('cat_d10_6mv', 'cat_d10_10mv', 'cat_r80_6mev', 'cat_r80_9mev', 'cat_r80_12mev', 'cat_r80_15mev',
                 'cat_symmetry_6mv_inline', 'cat_symmetry_6mv_crossline', 'cat_symmetry_10mv_inline', 'cat_symmetry_10mv_crossline',
                 'cat_symmetry_6mev_inline', 'cat_symmetry_6mev_crossline', 'cat_symmetry_9mev_inline', 'cat_symmetry_9mev_crossline', 
                 'cat_symmetry_12mev_inline', 'cat_symmetry_12mev_crossline', 'cat_symmetry_15mev_inline', 'cat_symmetry_15mev_crossline',
                 'cat_flatness_6mv_inline', 'cat_flatness_6mv_crossline', 'cat_flatness_10mv_inline', 'cat_flatness_10mv_crossline',
                 'cat_flatness_6mev_inline', 'cat_flatness_6mev_crossline', 'cat_flatness_9mev_inline', 'cat_flatness_9mev_crossline', 
                 'cat_flatness_12mev_inline', 'cat_flatness_12mev_crossline', 'cat_flatness_15mev_inline', 'cat_flatness_15mev_crossline',
                 'cat_output_factor_6mv', 'cat_output_factor_10mv', 'cat_output_factor_6mv_fff', 'cat_output_factor_10mv_fff', 
                 'cat_output_factor_6mev', 'cat_output_factor_9mev', 'cat_output_factor_12mev', 'cat_output_factor_15mev',
                 'cat_wedge_factor_6mv', 'cat_wedge_factor_10mv', 'cat_tmr_6mv', 'cat_tmr_10mv', 'cat_tmr_6mv_fff', 'cat_tmr_10mv_fff', 
                 'cat_pdd_20_10_6mv', 'cat_pdd_20_10_10mv', 'cat_pdd_20_10_6mv_fff', 'cat_pdd_20_10_10mv_fff'),
                ('cat_uniformity', 'cat_low_contrast', 'cat_high_contrast', 'cat_transverse_vertical_scale', 
                 'cat_transverse_horizontal_scale', 'cat_sagittal_geometric_scale', 'cat_table_movement_accuracy'),
            ),
            'classes': ('collapse',),
            'description': 'Mechanical Tests | Beam Tests | XVI Tests'
        }),
        ('Beam Modelling Information', {
            'fields': (
                'beam_modelling_info',
                ('beam_dose_ref_depth_6mv', 'beam_dose_ref_depth_10mv', 'beam_dose_ref_depth_15mv', 
                 'beam_dose_ref_depth_6mv_fff', 'beam_dose_ref_depth_10mv_fff', 'beam_dose_ref_depth_15mv_fff',
                 'beam_dose_ref_depth_4mev', 'beam_dose_ref_depth_5mev', 'beam_dose_ref_depth_6mev', 
                 'beam_dose_ref_depth_7mev', 'beam_dose_ref_depth_8mev', 'beam_dose_ref_depth_9mev', 
                 'beam_dose_ref_depth_10mev', 'beam_dose_ref_depth_11mev', 'beam_dose_ref_depth_12mev', 
                 'beam_dose_ref_depth_13mev', 'beam_dose_ref_depth_14mev', 'beam_dose_ref_depth_15mev', 
                 'beam_dose_ref_depth_16mev', 'beam_dose_ref_depth_17mev', 'beam_dose_ref_depth_18mev'),
                ('beam_tpr_zreff_6mv', 'beam_tpr_zreff_10mv', 'beam_tpr_zreff_15mv', 
                 'beam_tpr_zreff_6mv_fff', 'beam_tpr_zreff_10mv_fff', 'beam_tpr_zreff_15mv_fff'),
                ('beam_pdd_20_10_6mv', 'beam_pdd_20_10_10mv', 'beam_pdd_20_10_15mv', 
                 'beam_pdd_20_10_6mv_fff', 'beam_pdd_20_10_10mv_fff', 'beam_pdd_20_10_15mv_fff'),
                ('beam_tpr_calculated_6mv', 'beam_tpr_calculated_10mv', 'beam_tpr_calculated_15mv', 
                 'beam_tpr_calculated_6mv_fff', 'beam_tpr_calculated_10mv_fff', 'beam_tpr_calculated_15mv_fff'),
            ),
            'classes': ('collapse',),
            'description': 'Dose Reference Depth | TPR or TMR (Zreff) | PDD20/10 | TPR (calculated)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(QATest)
class QATestAdmin(admin.ModelAdmin):
    """
    Admin interface for QA Test model.
    """
    list_display = ['name', 'test_type', 'tolerance_value', 'tolerance_unit', 'order_index', 'is_active']
    list_filter = ['test_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['test_type', 'order_index']
    readonly_fields = ['created_at', 'updated_at']
    

    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'test_type', 'description')
        }),
        ('Tolerance Settings', {
            'fields': ('tolerance_value', 'tolerance_unit')
        }),
        ('Display Settings', {
            'fields': ('order_index', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# QA Status Management - HIDDEN FROM ADMIN INTERFACE
# (Users manage statuses through the web interface, not Django admin)
# @admin.register(QAStatus)
# class QAStatusAdmin(admin.ModelAdmin):
#     list_display = ['name', 'color', 'description']
#     search_fields = ['name', 'description']
#     ordering = ['name']

@admin.register(QARecord)
class QARecordAdmin(admin.ModelAdmin):
    """
    Admin interface for QA Record model.
    
    Provides comprehensive display of QA test results, film analyses,
    dose calculations, and test notes. Includes export and report generation actions.
    """
    list_display = ['id', 'linac', 'performed_by', 'date_performed', 'film_analyses_count', 'dose_calculations_count', 'notes_summary']
    list_filter = ['linac', 'date_performed', 'performed_by']
    search_fields = ['notes', 'linac__name', 'performed_by__username']
    ordering = ['-date_performed']
    date_hierarchy = 'date_performed'
    readonly_fields = ['created_at', 'updated_at', 'performed_by', 'date_performed', 'film_analyses_display', 'test_notes_display', 'report_actions']
    

    
    actions = ['export_qa_records', 'create_summary_report', 'view_dose_calculations', 'generate_qa_reports']
    
    def export_qa_records(self, request, queryset):
        """Export QA records with meaningful test names"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="qa_records_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header with meaningful test names
        header = ['ID', 'LINAC', 'Performed By', 'Date', 'Status']
        for i in range(1, 21):
            test_name = TEST_NAME_MAPPING.get(f'test_{i:02d}', f'Test {i}')
            header.append(test_name)
        header.extend(['Notes', 'Created At'])
        writer.writerow(header)
        
        # Write data
        for qa_record in queryset:
            row = [
                qa_record.id,
                qa_record.linac.name if qa_record.linac else '',
                qa_record.performed_by.username if qa_record.performed_by else '',
                qa_record.date_performed,
                qa_record.status.name if qa_record.status else '',
            ]
            
            # Add test values
            for i in range(1, 21):
                field_name = f'test_{i:02d}'
                value = getattr(qa_record, field_name)
                row.append(value if value is not None else '')
            
            row.extend([qa_record.notes, qa_record.created_at])
            writer.writerow(row)
        
        return response
    export_qa_records.short_description = "Export selected QA records to CSV"
    
    def create_summary_report(self, request, queryset):
        """Create a summary report of selected QA records"""
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        
        # Prepare summary data
        summary_data = {
            'total_records': queryset.count(),
            'linacs': {},
            'status_counts': {},
            'test_summaries': {},
        }
        
        for qa_record in queryset:
            # Count by LINAC
            linac_name = qa_record.linac.name if qa_record.linac else 'Unknown'
            if linac_name not in summary_data['linacs']:
                summary_data['linacs'][linac_name] = 0
            summary_data['linacs'][linac_name] += 1
            
            # Count by status
            status_name = qa_record.status.name if qa_record.status else 'No Status'
            if status_name not in summary_data['status_counts']:
                summary_data['status_counts'][status_name] = 0
            summary_data['status_counts'][status_name] += 1
            
            # Analyze test results
            for i in range(1, 21):
                field_name = f'test_{i:02d}'
                test_name = TEST_NAME_MAPPING.get(field_name, f'Test {i}')
                value = getattr(qa_record, field_name)
                
                if value is not None:
                    if test_name not in summary_data['test_summaries']:
                        summary_data['test_summaries'][test_name] = {
                            'count': 0,
                            'values': [],
                            'avg': 0,
                            'min': None,
                            'max': None
                        }
                    
                    summary_data['test_summaries'][test_name]['count'] += 1
                    summary_data['test_summaries'][test_name]['values'].append(value)
        
        # Calculate statistics for each test
        for test_name, data in summary_data['test_summaries'].items():
            if data['values']:
                data['avg'] = sum(data['values']) / len(data['values'])
                data['min'] = min(data['values'])
                data['max'] = max(data['values'])
        
        # Generate HTML report
        html_content = render_to_string('admin/QAID_Manager/qarecord/summary_report.html', {
            'summary_data': summary_data,
            'queryset': queryset,
        })
        
        response = HttpResponse(content_type='text/html')
        response['Content-Disposition'] = 'attachment; filename="qa_summary_report.html"'
        response.write(html_content)
        
        return response
    create_summary_report.short_description = "Create summary report of selected QA records"
    
    def view_dose_calculations(self, request, queryset):
        """View dose calculations for selected QA records"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # For now, just redirect to the first QA record's change page
        if queryset.count() == 1:
            qa_record = queryset.first()
            return HttpResponseRedirect(
                reverse('admin:QAID_Manager_qarecord_change', args=[qa_record.id])
            )
        else:
            # If multiple records selected, show a message
            self.message_user(request, "Please select only one QA record to view dose calculations")
            return HttpResponseRedirect(request.get_full_path())
    view_dose_calculations.short_description = "View dose calculations"
    
    def generate_qa_reports(self, request, queryset):
        """Generate QA reports for selected records"""
        if len(queryset) == 1:
            # Single report - return direct download
            qa_record = queryset.first()
            generator = QAReportGenerator()
            return generator.generate_report_response(qa_record)
        else:
            # Multiple reports - create zip file
            import tempfile
            import zipfile
            from django.http import HttpResponse
            
            # Create temporary zip file
            temp_dir = tempfile.gettempdir()
            zip_filename = f"qa_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                generator = QAReportGenerator()
                
                for qa_record in queryset:
                    # Generate document
                    doc = generator.generate_qa_report(qa_record)
                    
                    # Save and convert to PDF
                    filename = f"qa_report_{qa_record.id}_{qa_record.date_performed.strftime('%Y%m%d')}"
                    temp_file = generator.save_report(doc, filename)
                    
                    # Add to zip
                    if temp_file.endswith('.pdf'):
                        arcname = f"{filename}.pdf"
                    else:
                        arcname = f"{filename}.docx"
                    
                    zip_file.write(temp_file, arcname)
                    
                    # Clean up individual temp file
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            # Return zip file
            with open(zip_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            
            # Clean up zip file
            try:
                os.remove(zip_path)
            except:
                pass
            
            return response
    
    generate_qa_reports.short_description = "Generate QA Reports (PDF)"
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to set custom field labels and add tolerance checking"""
        form = super().get_form(request, obj, **kwargs)
        for field_name, test_name in TEST_NAME_MAPPING.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].label = test_name
                # Add tolerance information to help text
                tolerance = TEST_TOLERANCE_MAPPING.get(field_name, 0)
                form.base_fields[field_name].help_text = f"Tolerance: ±{tolerance}"
        return form
    
    def get_readonly_fields(self, request, obj=None):
        """Add tolerance status to readonly fields"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            # Add tolerance status fields for each test
            for i in range(1, 21):
                field_name = f'test_{i:02d}'
                tolerance_field = f'{field_name}_tolerance_status'
                readonly_fields.append(tolerance_field)
            # Add dose calculation summary only
            readonly_fields.append('dose_calculation_summary')
        return readonly_fields
    
    def film_analyses_count(self, obj):
        """Show count of film analyses"""
        count = obj.film_analyses.count()
        if count == 0:
            return "No films"
        return f"{count} film(s)"
    film_analyses_count.short_description = 'Film Analyses'
    
    def dose_calculations_count(self, obj):
        """Show count of dose calculations"""
        count = obj.dose_calculations.count()
        if count == 0:
            return "No dose calc"
        return f"{count} dose calc(s)"
    dose_calculations_count.short_description = 'Dose Calculations'
    
    def notes_summary(self, obj):
        """Show tests that are out of tolerance"""
        out_of_tolerance_tests = []
        
        for i in range(1, 21):
            field_name = f'test_{i:02d}'
            value = getattr(obj, field_name)
            tolerance = TEST_TOLERANCE_MAPPING.get(field_name, 0)
            
            if value is not None and abs(value) > tolerance:
                test_name = TEST_NAME_MAPPING.get(field_name, f'Test {i}')
                out_of_tolerance_tests.append(f"{test_name}: {value:.2f}")
        
        if out_of_tolerance_tests:
            return mark_safe(f'<div style="max-width: 400px; word-wrap: break-word; color: #dc3545;">{" | ".join(out_of_tolerance_tests)}</div>')
        else:
            return mark_safe('<div style="color: #28a745;">All tests within tolerance</div>')
    notes_summary.short_description = 'Notes'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('linac', 'performed_by', 'date_performed', 'status')
        }),
        ('Test Results', {
            'fields': (
                'test_01', 'test_02', 'test_03', 'test_04', 'test_05',
                'test_06', 'test_07', 'test_08', 'test_09', 'test_10',
                'test_11', 'test_12', 'test_13', 'test_14', 'test_15',
                'test_16', 'test_17', 'test_18', 'test_19', 'test_20',
            ),
            'classes': ('collapse',)
        }),
        ('Dose Calculation Summary', {
            'fields': ('dose_calculation_summary',),
            'classes': ('collapse',)
        }),
        ('Test Notes', {
            'fields': ('test_notes_display',),
            'classes': ('collapse',)
        }),

        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset to include related film analyses and dose calculations"""
        return super().get_queryset(request).prefetch_related('film_analyses', 'test_notes', 'dose_calculations')
    
    def film_analyses_display(self, obj):
        """Display film analyses in admin"""
        analyses = obj.film_analyses.all()
        if not analyses:
            return "No film analyses"
        
        html = []
        for analysis in analyses:
            if analysis.result_image:
                html.append(f'<div style="margin-bottom: 10px;"><strong>{analysis.analysis_type}:</strong><br>')
                html.append(f'<img src="{analysis.result_image.url}" style="max-width: 300px; height: auto; border: 1px solid #ddd;"><br>')
                html.append(f'<small>Created: {analysis.created_at}</small></div>')
        
        return mark_safe(''.join(html))
    film_analyses_display.short_description = 'Film Analysis Results'
    
    def test_notes_display(self, obj):
        """Display test notes in admin"""
        notes = obj.test_notes.all()
        if not notes:
            return "No test notes"
        
        html = []
        for note in notes:
            test_name = TEST_NAME_MAPPING.get(f'test_{note.test_number:02d}', f'Test {note.test_number}')
            html.append(f'<strong>{test_name}:</strong> {note.note_text}<br>')
        
        return mark_safe(''.join(html))
    test_notes_display.short_description = 'Test Notes'
    
    # Add dose calculation result methods for inline display
    def dose_calculation_summary(self, obj):
        """Display detailed dose calculation summary inline with test results"""
        dose_calculations = obj.dose_calculations.all()
        if not dose_calculations:
            return "No dose calculations"
        
        calc = dose_calculations.first()  # Show the most recent calculation
        html = []
        html.append('<div style="background-color: #f8f9fa; padding: 15px; border: 2px solid #28a745; border-radius: 8px; margin: 10px 0; font-family: Arial, sans-serif;">')
        html.append('<h3 style="margin: 0 0 15px 0; color: #155724; border-bottom: 2px solid #28a745; padding-bottom: 5px;">📊 Dose Calculation Results</h3>')
        
        # General Information
        html.append('<div style="margin-bottom: 15px; padding: 10px; background-color: #e8f5e8; border-radius: 5px;">')
        html.append('<strong style="color: #155724;">General Information:</strong><br>')
        html.append(f'<strong>Linac:</strong> {calc.linac.name}<br>')
        html.append(f'<strong>Energy:</strong> {calc.energy}<br>')
        html.append(f'<strong>Detector:</strong> {calc.detector.name} (SN: {calc.detector.series_number})<br>')
        html.append(f'<strong>Phantom:</strong> {calc.phantom}</div>')
        
        # Absolute Dose Calculations
        html.append('<div style="margin-bottom: 15px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">')
        html.append('<strong style="color: #856404;">Absolute Dose Calculations:</strong><br>')
        html.append(f'<strong>Raw Measurement:</strong> {calc.raw_measurement} nC<br>')
        
        # Add input values for Ktp calculation
        if hasattr(calc, 'temperature') and calc.temperature:
            html.append(f'<strong>Temperature:</strong> {calc.temperature}°C<br>')
        if hasattr(calc, 'pressure') and calc.pressure:
            html.append(f'<strong>Pressure:</strong> {calc.pressure} hPa<br>')
        
        # Add input values for Kpol calculation
        if hasattr(calc, 'm_plus') and calc.m_plus:
            html.append(f'<strong>M+:</strong> {calc.m_plus}<br>')
        if hasattr(calc, 'm_minus') and calc.m_minus:
            html.append(f'<strong>M-:</strong> {calc.m_minus}<br>')
        
        # Add input values for Ks calculation
        if hasattr(calc, 'm1') and calc.m1:
            html.append(f'<strong>M<sub>1</sub>:</strong> {calc.m1}<br>')
        if hasattr(calc, 'm2') and calc.m2:
            html.append(f'<strong>M<sub>2</sub>:</strong> {calc.m2}<br>')
        if hasattr(calc, 'v1') and calc.v1:
            html.append(f'<strong>V<sub>1</sub>:</strong> {calc.v1}<br>')
        if hasattr(calc, 'v2') and calc.v2:
            html.append(f'<strong>V<sub>2</sub>:</strong> {calc.v2}<br>')
        if hasattr(calc, 'v1_v2_ratio') and calc.v1_v2_ratio:
            html.append(f'<strong>V<sub>1</sub>/V<sub>2</sub>:</strong> {calc.v1_v2_ratio:.4f}<br>')
        
        # Add Ks coefficients
        if hasattr(calc, 'a0') and calc.a0:
            html.append(f'<strong>a<sub>0</sub>:</strong> {calc.a0:.6f}<br>')
        if hasattr(calc, 'a1') and calc.a1:
            html.append(f'<strong>a<sub>1</sub>:</strong> {calc.a1:.6f}<br>')
        if hasattr(calc, 'a2') and calc.a2:
            html.append(f'<strong>a<sub>2</sub>:</strong> {calc.a2:.6f}<br>')
        
        html.append(f'<strong>Ktp:</strong> {calc.ktp_result:.4f}<br>')
        html.append(f'<strong>Kpol:</strong> {calc.kpol_result:.4f}<br>')
        html.append(f'<strong>Ks:</strong> {calc.ks_result:.4f}<br>')
        if calc.solid_phantom_factor:
            html.append(f'<strong>Solid Phantom Factor:</strong> {calc.solid_phantom_factor:.3f}<br>')
        html.append(f'<strong>M<sub>Q</sub>:</strong> {calc.mq_result:.2f} nC<br>')
        html.append(f'<strong>D<sub>w,Q</sub>(z<sub>ref</sub>):</strong> {calc.dwq_zref:.2f} cGy<br>')
        html.append(f'<strong style="color: #155724; font-size: 16px;">D<sub>w,Q</sub>(z<sub>max</sub>): {calc.dwq_zmax:.2f} cGy</strong></div>')
        
        # Beam Quality Parameters
        html.append('<div style="margin-bottom: 15px; padding: 10px; background-color: #d1ecf1; border-radius: 5px;">')
        html.append('<strong style="color: #0c5460;">Beam Quality Parameters:</strong><br>')
        if calc.pdd_20_10:
            html.append(f'<strong>PDD(20/10):</strong> {calc.pdd_20_10:.6f}<br>')
        if calc.tmr:
            html.append(f'<strong>TMR:</strong> {calc.tmr:.6f}<br>')
        if calc.tpr_20_10:
            html.append(f'<strong>TPR(20/10):</strong> {calc.tpr_20_10:.6f}<br>')
        if calc.kq_factor:
            html.append(f'<strong>Kq Factor:</strong> {calc.kq_factor:.6f}</div>')
        
        # Relative Dose Measurements
        html.append('<div style="margin-bottom: 15px; padding: 10px; background-color: #f8d7da; border-radius: 5px;">')
        html.append('<strong style="color: #721c24;">Relative Dose Measurements:</strong><br>')
        if calc.m_ref:
            html.append(f'<strong>M<sub>ref</sub>:</strong> {calc.m_ref}<br>')
        if calc.m_left:
            html.append(f'<strong>M<sub>Left</sub>:</strong> {calc.m_left}<br>')
        if calc.m_right:
            html.append(f'<strong>M<sub>Right</sub>:</strong> {calc.m_right}<br>')
        if calc.m_gun:
            html.append(f'<strong>M<sub>Gun</sub>:</strong> {calc.m_gun}<br>')
        if calc.m_tar:
            html.append(f'<strong>M<sub>Tar</sub>:</strong> {calc.m_tar}<br>')
        if calc.m_mid:
            html.append(f'<strong>M<sub>Mid</sub>:</strong> {calc.m_mid}<br>')
        if calc.m_wedge:
            html.append(f'<strong>M<sub>Wedge</sub>:</strong> {calc.m_wedge}<br>')
        if calc.m_dmax:
            html.append(f'<strong>M<sub>Dmax</sub>:</strong> {calc.m_dmax}</div>')
        
        html.append(f'<div style="margin-top: 10px; padding: 5px; background-color: #e8f5e8; border-radius: 3px; text-align: center; font-size: 12px; color: #155724;">')
        html.append(f'<strong>Calculated: {calc.created_at.strftime("%Y-%m-%d %H:%M")}</strong></div>')
        html.append('</div>')
        
        return mark_safe(''.join(html))
    dose_calculation_summary.short_description = 'Dose Calculation Summary'
    
    # Add tolerance status methods for each test
    def test_01_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_01', 1.0)
    test_01_tolerance_status.short_description = 'Tolerance Status'
    
    def test_02_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_02', 1.0)
    test_02_tolerance_status.short_description = 'Tolerance Status'
    
    def test_03_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_03', 1.0)
    test_03_tolerance_status.short_description = 'Tolerance Status'
    
    def test_04_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_04', 1.0)
    test_04_tolerance_status.short_description = 'Tolerance Status'
    
    def test_05_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_05', 1.0)
    test_05_tolerance_status.short_description = 'Tolerance Status'
    
    def test_06_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_06', 1.0)
    test_06_tolerance_status.short_description = 'Tolerance Status'
    
    def test_07_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_07', 1.0)
    test_07_tolerance_status.short_description = 'Tolerance Status'
    
    def test_08_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_08', 1.0)
    test_08_tolerance_status.short_description = 'Tolerance Status'
    
    def test_09_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_09', 1.0)
    test_09_tolerance_status.short_description = 'Tolerance Status'
    
    def test_10_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_10', 1.0)
    test_10_tolerance_status.short_description = 'Tolerance Status'
    
    def test_11_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_11', 2.0)
    test_11_tolerance_status.short_description = 'Tolerance Status'
    
    def test_12_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_12', 1.0)
    test_12_tolerance_status.short_description = 'Tolerance Status'
    
    def test_13_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_13', 1.0)
    test_13_tolerance_status.short_description = 'Tolerance Status'
    
    def test_14_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_14', 1.0)
    test_14_tolerance_status.short_description = 'Tolerance Status'
    
    def test_15_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_15', 2.0)
    test_15_tolerance_status.short_description = 'Tolerance Status'
    
    def test_16_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_16', 1.0)
    test_16_tolerance_status.short_description = 'Tolerance Status'
    
    def test_17_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_17', 3.0)
    test_17_tolerance_status.short_description = 'Tolerance Status'
    
    def test_18_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_18', 3.0)
    test_18_tolerance_status.short_description = 'Tolerance Status'
    
    def test_19_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_19', 1.0)
    test_19_tolerance_status.short_description = 'Tolerance Status'
    
    def test_20_tolerance_status(self, obj):
        return self._get_tolerance_status(obj, 'test_20', 2.0)
    test_20_tolerance_status.short_description = 'Tolerance Status'
    
    def _get_tolerance_status(self, obj, field_name, tolerance):
        """Helper method to get tolerance status with color coding"""
        value = getattr(obj, field_name)
        if value is None:
            return mark_safe('<span style="color: #6c757d;">No data</span>')
        
        if abs(value) <= tolerance:
            return mark_safe(f'<span style="color: #28a745; font-weight: bold;">✓ PASS (±{tolerance})</span>')
        else:
            return mark_safe(f'<span style="color: #fd7e14; font-weight: bold;">✗ FAIL (±{tolerance})</span>')
    
    def report_actions(self, obj):
        """Display report generation button"""
        if obj:
            return format_html(
                '<a class="button" href="{}">Generate PDF Report</a>',
                reverse('generate_qa_report', args=[obj.id])
            )
        return "No report available"
    
    report_actions.short_description = "Report Actions"
    
    readonly_fields = ['created_at', 'updated_at', 'performed_by', 'date_performed', 'film_analyses_display', 'test_notes_display']

@admin.register(QASchedule)
class QAScheduleAdmin(admin.ModelAdmin):
    """
    Admin interface for QA Schedule model.
    """
    list_display = ['linac', 'month_year', 'performer1', 'performer2', 'status', 'qa_date', 'is_accepted', 'created_at']
    list_filter = ['linac', 'month_year', 'performer1', 'performer2', 'status', 'is_accepted', 'created_at']
    search_fields = ['linac__name', 'performer1__username', 'performer2__username', 'notes', 'qa_reason']
    ordering = ['month_year', 'linac__name']
    date_hierarchy = 'month_year'
    readonly_fields = ['created_at', 'updated_at']
    

    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('linac', 'month_year', 'performer1', 'performer2', 'status', 'qa_date')
        }),
        ('QA Details', {
            'fields': ('qa_reason', 'notes', 'is_accepted')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """
    Admin interface for User Activity model.
    """
    list_display = ['user', 'activity_type', 'description', 'ip_address', 'created_at']
    list_filter = ['activity_type', 'created_at', 'user']
    search_fields = ['user__username', 'description', 'ip_address']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Activity Information', {
            'fields': ('user', 'activity_type', 'description', 'ip_address')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Dosimeter)
class DosimeterAdmin(admin.ModelAdmin):
    """
    Admin interface for Dosimeter model.
    """
    list_display = ['name', 'brand', 'series_number', 'calibration_factor', 'calibration_date', 'is_active']
    list_filter = ['is_active', 'brand', 'calibration_date', 'created_at']
    search_fields = ['name', 'brand', 'series_number', 'calibration_factor', 'calibration_lab']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'brand', 'series_number', 'certificate_number')
        }),
        ('Calibration Information', {
            'fields': (
                'calibration_factor',
                'calibration_date',
                'calibration_radiation_source',
                'calibration_temperature',
                'calibration_pressure',
                'calibration_lab'
            )
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """
    Admin interface for Device model.
    """
    list_display = ['name', 'category', 'brand', 'series_number', 'storage_location', 'is_active']
    list_filter = ['is_active', 'category', 'brand', 'created_at']
    search_fields = ['name', 'brand', 'series_number', 'certificate_number', 'storage_location']
    ordering = ['category', 'name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'name', 'brand', 'date', 'series_number', 'certificate_number', 'storage_location')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# DeviceDocument admin removed - users manage documents through the web interface
# (Documents are managed via the web interface, not Django admin)
# @admin.register(DeviceDocument)
# class DeviceDocumentAdmin(admin.ModelAdmin):
#     list_display = ['device', 'file_name', 'file_type', 'uploaded_by', 'uploaded_at']
#     list_filter = ['file_type', 'uploaded_at']
#     search_fields = ['device__name', 'file_name', 'description']
#     ordering = ['-uploaded_at']
#     readonly_fields = ['uploaded_at']


@admin.register(LinacServiceReport)
class LinacServiceReportAdmin(admin.ModelAdmin):
    """
    Admin interface for LINAC Service Report model.
    """
    list_display = ['linac', 'date', 'report_type_display', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'pm_service', 'equipment_breakdown', 'date', 'created_at']
    search_fields = ['linac__name', 'issue_description', 'notes', 'created_by__username']
    ordering = ['-date', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('linac', 'date', 'pm_service', 'equipment_breakdown', 'status')
        }),
        ('Service Details', {
            'fields': ('issue_description', 'follow_up_actions', 'downtime', 'parts_replacement', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def report_type_display(self, obj):
        """Display report type"""
        types = []
        if obj.pm_service:
            types.append("PM Service")
        if obj.equipment_breakdown:
            types.append("Equipment Breakdown")
        return " / ".join(types) if types else "-"
    report_type_display.short_description = 'Report Type'
    
    def save_model(self, request, obj, form, change):
        """Set created_by on first save"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# QA Film Analysis Management - HIDDEN FROM ADMIN INTERFACE
# (Film analyses are managed through QA records, not directly in admin)
# @admin.register(QAFilmAnalysis)
# class QAFilmAnalysisAdmin(admin.ModelAdmin):
#     list_display = ['id', 'qa_record', 'analysis_type', 'created_at', 'image_preview']
#     list_filter = ['analysis_type', 'created_at', 'qa_record__linac']
#     search_fields = ['qa_record__linac__name', 'analysis_type']
#     ordering = ['-created_at']
#     readonly_fields = ['created_at', 'image_preview']
#     
#     def image_preview(self, obj):
#         """Show image preview in admin list"""
#         if obj.result_image:
#             return mark_safe(f'<img src="{obj.result_image.url}" style="max-width: 100px; height: auto; border: 1px solid #ddd;">')
#         return "No image"
#     image_preview.short_description = 'Image Preview'
#     
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('qa_record', 'analysis_type', 'result_image')
#         }),
#         ('Image Preview', {
#             'fields': ('image_preview',),
#             'classes': ('collapse',)
#         }),
#         ('Timestamps', {
#             'fields': ('created_at',),
#             'classes': ('collapse',)
#         }),
#     )

# QA Test Notes Management - HIDDEN FROM ADMIN INTERFACE
# (Test notes are managed through QA records, not directly in admin)
# @admin.register(QATestNote)
# class QATestNoteAdmin(admin.ModelAdmin):
#     list_display = ['qa_record', 'test_name', 'note_text', 'created_at']
#     list_filter = ['test_number', 'created_at', 'qa_record__linac']
#     search_fields = ['note_text', 'qa_record__linac__name']
#     ordering = ['qa_record', 'test_number']
#     readonly_fields = ['created_at', 'test_name']
#     
#     def test_name(self, obj):
#         """Display meaningful test name"""
#         return TEST_NAME_MAPPING.get(f'test_{obj.test_number:02d}', f'Test {obj.test_number}')
#     test_name.short_description = 'Test Name'
#     
#     fieldsets = (
#         ('Note Information', {
#             'fields': ('qa_record', 'test_number', 'test_name', 'note_text')
#         }),
#         ('Timestamps', {
#             'fields': ('created_at',),
#             'classes': ('collapse',)
#         }),
#     )

@admin.register(PhysicsParameters)
class PhysicsParametersAdmin(admin.ModelAdmin):
    """
    Admin interface for Physics Parameters model.
    
    Note: Adding new physics parameters is disabled - only editing is allowed.
    """
    list_display = ['name', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    # Disable adding new physics parameters - only allow editing
    def has_add_permission(self, request):
        return False


@admin.register(VietnameseHoliday)
class VietnameseHolidayAdmin(admin.ModelAdmin):
    """
    Admin interface for Vietnamese Holiday model.
    """
    list_display = ['name', 'date', 'holiday_type', 'is_active']
    list_filter = ['holiday_type', 'is_active', 'date', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['date']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Holiday Information', {
            'fields': ('name', 'date', 'holiday_type', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# DoseCalculation model is not registered in admin
# (Dose calculations are displayed inline within QA Records, not as separate admin entries)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description')
        }),
        ('Data', {
            'fields': ('editable_table_data',),
            'description': 'Edit table data directly - changes will be saved to parameter_values'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Hidden Fields', {
            'fields': ('parameter_values',),
            'classes': ('collapse',),
            'description': 'Hidden field for storing table data'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def editable_table_data(self, obj):
        """Display parameter values as an editable HTML table"""
        if not obj.parameter_values or 'table_data' not in obj.parameter_values:
            return "No table data available"
        
        table_data = obj.parameter_values.get('table_data', [])
        if not table_data:
            return "No table data available"
        
        # Get headers from the first row
        headers = list(table_data[0].keys())
        
        # Build editable HTML table
        html = '<div style="max-height: 500px; overflow-y: auto; border: 1px solid #ddd; margin: 10px 0;">'
        html += '<table id="editable-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">'
        
        # Header row
        html += '<thead style="background-color: #f5f5f5; position: sticky; top: 0;">'
        html += '<tr>'
        for header in headers:
            html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;">{header}</th>'
        html += '</tr>'
        html += '</thead>'
        
        # Data rows with editable cells
        html += '<tbody>'
        for row_idx, row in enumerate(table_data):
            html += '<tr>'
            for header in headers:
                value = row.get(header, '')
                html += f'<td style="border: 1px solid #ddd; padding: 6px; text-align: left;">'
                html += f'<input type="text" value="{value}" style="width: 100%; border: none; background: transparent; font-size: 12px;" '
                html += f'data-row="{row_idx}" data-column="{header}" onchange="updateTableData(this)">'
                html += '</td>'
            html += '</tr>'
        html += '</tbody>'
        html += '</table>'
        html += '</div>'
        
        # Add JavaScript for handling updates
        html += '''
        <script>
        function updateTableData(input) {
            const row = input.getAttribute('data-row');
            const column = input.getAttribute('data-column');
            const value = input.value;
            
            // Update the hidden JSON field
            const jsonField = document.getElementById('id_parameter_values');
            if (jsonField) {
                try {
                    let data = JSON.parse(jsonField.value);
                    if (!data.table_data) {
                        data.table_data = [];
                    }
                    if (!data.table_data[row]) {
                        data.table_data[row] = {};
                    }
                    data.table_data[row][column] = value;
                    jsonField.value = JSON.stringify(data, null, 2);
                    
                    // Trigger change event to ensure Django knows the field was modified
                    const event = new Event('change', { bubbles: true });
                    jsonField.dispatchEvent(event);
                } catch (e) {
                    console.error('Error updating JSON:', e);
                }
            }
        }
        
        // Add row functionality
        function addTableRow() {
            const table = document.getElementById('editable-table');
            const tbody = table.querySelector('tbody');
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
            const newRow = document.createElement('tr');
            
            headers.forEach((header, index) => {
                const cell = document.createElement('td');
                cell.style.cssText = 'border: 1px solid #ddd; padding: 6px; text-align: left;';
                const input = document.createElement('input');
                input.type = 'text';
                input.style.cssText = 'width: 100%; border: none; background: transparent; font-size: 12px;';
                input.setAttribute('data-row', tbody.children.length);
                input.setAttribute('data-column', header);
                input.onchange = function() { updateTableData(this); };
                cell.appendChild(input);
                newRow.appendChild(cell);
            });
            
            tbody.appendChild(newRow);
            updateJSONFromTable();
        }
        
        // Delete row functionality
        function deleteTableRow() {
            const table = document.getElementById('editable-table');
            const tbody = table.querySelector('tbody');
            if (tbody.children.length > 1) {
                tbody.removeChild(tbody.lastElementChild);
                updateJSONFromTable();
            }
        }
        
        // Add column functionality
        function addTableColumn() {
            const columnName = prompt('Enter column name:');
            if (!columnName) return;
            
            const table = document.getElementById('editable-table');
            const thead = table.querySelector('thead tr');
            const tbody = table.querySelector('tbody');
            
            // Add header
            const headerCell = document.createElement('th');
            headerCell.style.cssText = 'border: 1px solid #ddd; padding: 8px; text-align: left; font-weight: bold;';
            headerCell.textContent = columnName;
            thead.appendChild(headerCell);
            
            // Add cells to all rows
            const rows = tbody.querySelectorAll('tr');
            rows.forEach((row, rowIndex) => {
                const cell = document.createElement('td');
                cell.style.cssText = 'border: 1px solid #ddd; padding: 6px; text-align: left;';
                const input = document.createElement('input');
                input.type = 'text';
                input.style.cssText = 'width: 100%; border: none; background: transparent; font-size: 12px;';
                input.setAttribute('data-row', rowIndex);
                input.setAttribute('data-column', columnName);
                input.onchange = function() { updateTableData(this); };
                cell.appendChild(input);
                row.appendChild(cell);
            });
            
            updateJSONFromTable();
        }
        
        // Delete column functionality
        function deleteTableColumn() {
            const table = document.getElementById('editable-table');
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
            
            if (headers.length <= 1) {
                alert('Cannot delete the last column!');
                return;
            }
            
            const columnName = prompt('Enter column name to delete:\\n\\nAvailable columns: ' + headers.join(', '));
            if (!columnName || !headers.includes(columnName)) {
                alert('Invalid column name!');
                return;
            }
            
            const columnIndex = headers.indexOf(columnName);
            
            // Remove header
            const thead = table.querySelector('thead tr');
            thead.removeChild(thead.children[columnIndex]);
            
            // Remove cells from all rows
            const tbody = table.querySelector('tbody');
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                row.removeChild(row.children[columnIndex]);
            });
            
            updateJSONFromTable();
        }
        
        // Function to update JSON from current table state
        function updateJSONFromTable() {
            const table = document.getElementById('editable-table');
            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
            const rows = table.querySelectorAll('tbody tr');
            
            const tableData = [];
            rows.forEach((row, rowIndex) => {
                const rowData = {};
                const inputs = row.querySelectorAll('input');
                inputs.forEach((input, colIndex) => {
                    if (colIndex < headers.length) {
                        rowData[headers[colIndex]] = input.value;
                    }
                });
                tableData.push(rowData);
            });
            
            const jsonField = document.getElementById('id_parameter_values');
            if (jsonField) {
                try {
                    let data = JSON.parse(jsonField.value);
                    data.table_data = tableData;
                    jsonField.value = JSON.stringify(data, null, 2);
                    
                    // Trigger change event
                    const event = new Event('change', { bubbles: true });
                    jsonField.dispatchEvent(event);
                } catch (e) {
                    console.error('Error updating JSON:', e);
                }
            }
        </script>
        
        <div style="margin-top: 10px;">
            <div style="margin-bottom: 10px;">
                <button type="button" onclick="addTableRow()" style="margin-right: 10px; padding: 5px 10px; background: #007cba; color: white; border: none; border-radius: 3px; cursor: pointer;">Add Row</button>
                <button type="button" onclick="deleteTableRow()" style="margin-right: 10px; padding: 5px 10px; background: #dc3545; color: white; border: none; border-radius: 3px; cursor: pointer;">Delete Last Row</button>
            </div>
            <div>
                <button type="button" onclick="addTableColumn()" style="margin-right: 10px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer;">Add Column</button>
                <button type="button" onclick="deleteTableColumn()" style="padding: 5px 10px; background: #fd7e14; color: white; border: none; border-radius: 3px; cursor: pointer;">Delete Column</button>
            </div>
        </div>
        '''
        
        return mark_safe(html)
    
    editable_table_data.short_description = 'Editable Table Data'
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form based on parameter type"""
        form = super().get_form(request, obj, **kwargs)
        
        # Add help text for the remaining fields
        if 'name' in form.base_fields:
            form.base_fields['name'].help_text = 'Name of the physics parameter table'
        if 'description' in form.base_fields:
            form.base_fields['description'].help_text = 'Brief description of the table contents'
        
        return form


# DosimeterDocument admin removed - users manage documents through the web interface
# (Documents are managed via the web interface, not Django admin)
# @admin.register(DosimeterDocument)
# class DosimeterDocumentAdmin(admin.ModelAdmin):
#     list_display = ('file_name', 'dosimeter', 'file_type', 'uploaded_by', 'uploaded_at')
#     list_filter = ('file_type', 'uploaded_at', 'dosimeter')
#     search_fields = ('file_name', 'description', 'dosimeter__name')
#     readonly_fields = ('uploaded_at',)
#     date_hierarchy = 'uploaded_at'


@admin.register(LinacDocument)
class LinacDocumentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'linac', 'file_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at', 'linac')
    search_fields = ('file_name', 'description', 'linac__name')
    readonly_fields = ('uploaded_at',)
    date_hierarchy = 'uploaded_at'



