"""
Django Forms for QAID Manager.

This module contains all form classes used in the application for creating
and editing models through the web interface.
"""
from django import forms
from django.contrib.auth.models import User
from .models import QARecord, FilmUpload, Dosimeter, QASchedule, Linac, QAStatus, QATest, PhysicsParameters, VietnameseHoliday, OrganizationSettings, UserProfile, DosimeterDocument, LinacDocument, Device, DeviceDocument, LinacServiceReport, CustomTestType, CustomTest

# ============================================================================
# QA Record Forms
# ============================================================================

class QARecordForm(forms.ModelForm):
    """
    Form for creating and editing QA records.
    """
    class Meta:
        model = QARecord
        exclude = ['performed_by', 'date_performed', 'created_at']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'style': 'width: 100%; max-width: 1525px;',
            }),
        }

    def __init__(self, *args, **kwargs):
        super(QARecordForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            if field.startswith('test_'):
                self.fields[field].widget.attrs.update({
                    'class': 'qa-input',
                    'step': 'any',
                    'style': 'width: 100px; text-align: center;'
                })
class FilmUploadForm(forms.ModelForm):
    """
    Form for uploading film images with optional manual DPI entry.
    """
    manual_dpi = forms.FloatField(required=False, label='DPI (nếu không phát hiện được)')

    class Meta:
        model = FilmUpload
        fields = ['image']

# ============================================================================
# Dosimeter Forms
# ============================================================================

class DosimeterForm(forms.ModelForm):
    """
    Form for creating and editing dosimeters.
    """
    class Meta:
        model = Dosimeter
        fields = '__all__'
        exclude = ['created_at', 'updated_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'series_number': forms.TextInput(attrs={'class': 'form-control'}),
            'certificate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'calibration_factor': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'calibration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'calibration_radiation_source': forms.TextInput(attrs={'class': 'form-control'}),
            'calibration_temperature': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'calibration_pressure': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'calibration_lab': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Ion Chamber Name',
            'brand': 'Manufacturer',
            'series_number': 'Series Number',
            'certificate_number': 'Certificate Number',
            'calibration_factor': 'Calibration Factor (N_d,w)',
            'calibration_date': 'Calibration Date',
            'calibration_radiation_source': 'Calibration Radiation Source',
            'calibration_temperature': 'Calibration Temperature (T₀)',
            'calibration_pressure': 'Calibration Pressure (P₀)',
            'calibration_lab': 'Calibration Laboratory',
            'is_active': 'Active',
        }


# ============================================================================
# LINAC Forms
# ============================================================================

class LinacForm(forms.ModelForm):
    """
    Form for creating and editing LINACs.
    
    Handles energy selection as multiple choice checkboxes.
    """
    energy = forms.MultipleChoiceField(
        choices=Linac.ENERGY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Energy'
    )
    
    class Meta:
        model = Linac
        fields = '__all__'
        exclude = ['created_at', 'updated_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'series_number': forms.TextInput(attrs={'class': 'form-control'}),
            'installation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'certification_due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'dosimetry_method': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cat_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'beam_modelling_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            # All float fields
            'beam_dose_ref_depth_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_15mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_15mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_4mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_5mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_7mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_8mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_10mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_11mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_13mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_14mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_16mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_17mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_dose_ref_depth_18mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_zreff_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_pdd_20_10_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'beam_tpr_calculated_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            # CAT fields
            'cat_gantry_isocenter': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_collimator_isocenter': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_field_size_12x12': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_isocenter': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_rotation': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_height_isocenter': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_height': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_long': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_lateral': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_d10_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_d10_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_6mv_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_6mv_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_10mv_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_10mv_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_6mv_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_6mv_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_10mv_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_10mv_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_r80_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_r80_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_r80_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_r80_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_6mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_6mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_9mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_9mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_12mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_12mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_15mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_symmetry_15mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_6mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_6mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_9mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_9mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_12mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_12mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_15mev_inline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_flatness_15mev_crossline': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_6mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_9mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_12mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_output_factor_15mev': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_wedge_factor_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_wedge_factor_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_tmr_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_tmr_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_tmr_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_tmr_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_pdd_20_10_6mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_pdd_20_10_10mv': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_pdd_20_10_6mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_pdd_20_10_10mv_fff': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_uniformity': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_low_contrast': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_high_contrast': forms.TextInput(attrs={'class': 'form-control'}),
            'cat_transverse_vertical_scale': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_transverse_horizontal_scale': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_sagittal_geometric_scale': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'cat_table_movement_accuracy': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
        }
        labels = {
            'name': 'Machine Name',
            'series_number': 'Series Number',
            'installation_date': 'Installation Date',
            'certification_due_date': 'Certification Due Date',
            'dosimetry_method': 'Dosimetry Method',
            'is_active': 'Active',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.energy:
            self.fields['energy'].initial = self.instance.energy
        
        # Dynamically add widgets for all FloatField fields that don't have explicit widgets
        # This ensures all new energy fields get proper styling
        for field_name, field in self.fields.items():
            if field_name not in self.Meta.widgets and isinstance(field, forms.FloatField):
                self.fields[field_name].widget = forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'})
            elif field_name not in self.Meta.widgets and isinstance(field, forms.CharField) and field_name not in ['name', 'series_number', 'cat_info', 'beam_modelling_info', 'cat_high_contrast']:
                self.fields[field_name].widget = forms.TextInput(attrs={'class': 'form-control'})
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Save energy as JSON
            instance.energy = self.cleaned_data.get('energy', [])
            instance.save()
        return instance


# ============================================================================
# Physics Parameters Forms
# ============================================================================

class PhysicsParametersForm(forms.ModelForm):
    """
    Form for creating and editing Physics Parameters.
    
    Handles parameter values as JSON field with table data support.
    """
    
    class Meta:
        model = PhysicsParameters
        fields = ['name', 'parameter_type', 'energy', 'beam_type', 'parameter_values',
                  'voltage_ratio', 'a0_coefficient', 'a1_coefficient', 'a2_coefficient', 
                  'reference_energy', 'kqqo_value', 'chamber_type', 'chamber_volume', 
                  'reference_standard', 'reference_table', 'reference_page', 
                  'description', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parameter_type': forms.Select(attrs={'class': 'form-control'}),
            'energy': forms.TextInput(attrs={'class': 'form-control'}),
            'beam_type': forms.Select(attrs={'class': 'form-control'}),
            'parameter_values': forms.HiddenInput(),  # Will be handled by JavaScript
            'voltage_ratio': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'a0_coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'a1_coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'a2_coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'reference_energy': forms.TextInput(attrs={'class': 'form-control'}),
            'kqqo_value': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'chamber_type': forms.TextInput(attrs={'class': 'form-control'}),
            'chamber_volume': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'reference_standard': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_table': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_page': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import json
        from .film_parameters_service import (
            DEFAULT_FIELD_SIZE_BAND_WIDTH_MM,
            DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD,
            FIELD_SIZE_BAND_WIDTH_MM_MAX,
            FIELD_SIZE_BAND_WIDTH_MM_MIN,
            FILM_ANALYSIS_PARAM_NAME,
        )

        self.fields['field_size_detection_threshold_percent'] = forms.FloatField(
            label='Field size detection threshold (%)',
            required=False,
            min_value=1,
            max_value=99,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1',
                'max': '99',
            }),
        )
        self.fields['field_size_band_width_mm'] = forms.FloatField(
            label='Field size analysis band width (mm)',
            required=False,
            min_value=FIELD_SIZE_BAND_WIDTH_MM_MIN,
            max_value=FIELD_SIZE_BAND_WIDTH_MM_MAX,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': str(FIELD_SIZE_BAND_WIDTH_MM_MIN),
                'max': str(FIELD_SIZE_BAND_WIDTH_MM_MAX),
            }),
        )

        if self.instance and self.instance.pk and self.instance.parameter_type == 'film_analysis':
            values = self.instance.parameter_values if isinstance(self.instance.parameter_values, dict) else {}
            threshold = values.get(
                'field_size_detection_threshold',
                DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD,
            )
            band_width_mm = values.get(
                'field_size_band_width_mm',
                DEFAULT_FIELD_SIZE_BAND_WIDTH_MM,
            )
            self.initial['field_size_detection_threshold_percent'] = round(float(threshold) * 100, 1)
            self.initial['field_size_band_width_mm'] = round(float(band_width_mm), 1)
            self.initial['parameter_values'] = json.dumps(values)
        elif self.instance and self.instance.pk:
            if not self.instance.parameter_values:
                self.instance.parameter_values = {}
            if isinstance(self.instance.parameter_values, list):
                self.initial['parameter_values'] = json.dumps(self.instance.parameter_values)
            elif isinstance(self.instance.parameter_values, dict):
                if 'table_data' in self.instance.parameter_values:
                    self.initial['parameter_values'] = json.dumps(self.instance.parameter_values)
                else:
                    self.initial['parameter_values'] = json.dumps({
                        'table_data': [self.instance.parameter_values]
                    })
            else:
                self.initial['parameter_values'] = json.dumps({'table_data': []})
        else:
            self.initial['parameter_values'] = json.dumps({'table_data': []})
            self.initial['field_size_detection_threshold_percent'] = round(
                DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD * 100, 1
            )
            self.initial['field_size_band_width_mm'] = DEFAULT_FIELD_SIZE_BAND_WIDTH_MM
            self.initial['name'] = FILM_ANALYSIS_PARAM_NAME

        is_film_analysis = False
        if self.is_bound:
            is_film_analysis = self.data.get('parameter_type') == 'film_analysis'
        elif self.instance.pk and self.instance.parameter_type == 'film_analysis':
            is_film_analysis = True
        if is_film_analysis:
            self.fields['parameter_values'].required = False

        editing_film_analysis = self.instance.pk and self.instance.parameter_type == 'film_analysis'
        if not editing_film_analysis and PhysicsParameters.objects.filter(parameter_type='film_analysis').exists():
            choices = [
                choice for choice in self.fields['parameter_type'].choices
                if choice[0] != 'film_analysis'
            ]
            self.fields['parameter_type'].choices = choices

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('parameter_type') == 'film_analysis':
            from .film_parameters_service import FILM_ANALYSIS_PARAM_NAME

            qs = PhysicsParameters.objects.filter(parameter_type='film_analysis')
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'parameter_type',
                    'A Film Analysis Parameters record already exists. Edit the existing row instead of creating another.',
                )

            from .film_parameters_service import (
                FIELD_SIZE_BAND_WIDTH_MM_MAX,
                FIELD_SIZE_BAND_WIDTH_MM_MIN,
            )

            percent = cleaned.get('field_size_detection_threshold_percent')
            band_mm = cleaned.get('field_size_band_width_mm')
            if percent is None:
                self.add_error(
                    'field_size_detection_threshold_percent',
                    'Enter the field size detection threshold (1–99%).',
                )
            elif percent < 1 or percent > 99:
                self.add_error(
                    'field_size_detection_threshold_percent',
                    'Threshold must be between 1% and 99%.',
                )
            if band_mm is None:
                self.add_error(
                    'field_size_band_width_mm',
                    'Enter the analysis band width in millimetres.',
                )
            elif band_mm < FIELD_SIZE_BAND_WIDTH_MM_MIN or band_mm > FIELD_SIZE_BAND_WIDTH_MM_MAX:
                self.add_error(
                    'field_size_band_width_mm',
                    f'Band width must be between {FIELD_SIZE_BAND_WIDTH_MM_MIN} and {FIELD_SIZE_BAND_WIDTH_MM_MAX} mm.',
                )

            if not self.errors:
                cleaned['parameter_values'] = {
                    'field_size_detection_threshold': percent / 100.0,
                    'field_size_band_width_mm': float(band_mm),
                }

            cleaned['name'] = FILM_ANALYSIS_PARAM_NAME
            cleaned['energy'] = ''
            cleaned['beam_type'] = 'photon'
        return cleaned

    def clean_parameter_values(self):
        """Ensure parameter_values is a valid list of dictionaries or wrapped format with metadata"""
        import json
        if self.data.get('parameter_type') == 'film_analysis':
            return {}
        param_values = self.cleaned_data.get('parameter_values')
        if isinstance(param_values, str):
            try:
                parsed = json.loads(param_values)
                # If it's a dict with table_data, preserve the wrapped format (for CSV imports with metadata)
                if isinstance(parsed, dict) and 'table_data' in parsed:
                    return parsed
                # If it's a list, return as-is
                elif isinstance(parsed, list):
                    return parsed
                # If it's a simple dict (no table_data), convert to list format
                elif isinstance(parsed, dict):
                    return [parsed]
                else:
                    return []
            except json.JSONDecodeError:
                return []
        elif isinstance(param_values, dict):
            # If it has table_data, preserve the wrapped format
            if 'table_data' in param_values:
                return param_values
            # Otherwise convert to list
            return [param_values]
        elif isinstance(param_values, list):
            return param_values
        return []


# ============================================================================
# QA Test Forms
# ============================================================================

class QATestForm(forms.ModelForm):
    """
    Form for creating and editing QA Tests.
    Dynamically includes user-defined test types from CustomTestType.
    """
    
    class Meta:
        model = QATest
        fields = ['name', 'test_type', 'description', 'tolerance_value', 'tolerance_unit', 
                  'order_index', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'test_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tolerance_value': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'tolerance_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'order_index': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builtin_choices = list(QATest.TEST_TYPES)
        custom_types = CustomTestType.objects.filter(is_active=True).order_by('display_order', 'name')
        custom_choices = [(f'custom_{ct.slug}', ct.name) for ct in custom_types]
        if custom_choices:
            self.fields['test_type'].choices = builtin_choices + [('', '---')] + custom_choices
        self.fields['test_type'].widget.attrs['class'] = 'form-control'


# ============================================================================
# Custom Test Type / Test Forms
# ============================================================================

class CustomTestTypeForm(forms.ModelForm):
    class Meta:
        model = CustomTestType
        fields = ['name', 'display_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CBCT, Imaging'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CustomTestForm(forms.ModelForm):
    class Meta:
        model = CustomTest
        fields = ['name', 'description', 'tolerance_value', 'tolerance_unit', 'order_index', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tolerance_value': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'tolerance_unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'mm, %, degree...'}),
            'order_index': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================================
# Vietnamese Holiday Forms
# ============================================================================

class VietnameseHolidayForm(forms.ModelForm):
    """
    Form for creating and editing Vietnamese Holidays.
    """
    
    class Meta:
        model = VietnameseHoliday
        fields = ['name', 'date', 'holiday_type', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'holiday_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ============================================================================
# QA Schedule Forms
# ============================================================================

class QAScheduleForm(forms.ModelForm):
    """
    Form for creating and editing QA schedules.
    
    Validates that performer1 and performer2 are different people.
    """
    
    class Meta:
        model = QASchedule
        fields = ['linac', 'month_year', 'performer1', 'performer2', 'status', 'qa_reason', 'notes', 'qa_date', 'expected_qa_date']
        widgets = {
            'month_year': forms.DateInput(attrs={'type': 'month'}),
            'qa_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_qa_date': forms.DateInput(attrs={'type': 'date'}),
            'qa_reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter reason for QA session'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Additional notes'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active Linacs
        self.fields['linac'].queryset = Linac.objects.filter(is_active=True)
        
        # Filter active users for performers
        self.fields['performer1'].queryset = User.objects.filter(is_active=True)
        self.fields['performer2'].queryset = User.objects.filter(is_active=True)
        
        # Make performer2 optional
        self.fields['performer2'].required = False
        
        # Add custom labels
        self.fields['linac'].label = 'Linac Machine'
        self.fields['month_year'].label = 'Month/Year'
        self.fields['performer1'].label = 'QA Performer 1'
        self.fields['performer2'].label = 'QA Performer 2 (Optional)'
        self.fields['qa_reason'].label = 'QA Reason'
        self.fields['notes'].label = 'Notes'
        self.fields['qa_date'].label = 'Actual QA Date'
        self.fields['expected_qa_date'].label = 'Expected QA Date'
    
    def clean(self):
        cleaned_data = super().clean()
        month_year = cleaned_data.get('month_year')
        performer1 = cleaned_data.get('performer1')
        performer2 = cleaned_data.get('performer2')
        
        # Check if performers are different
        if performer1 and performer2 and performer1 == performer2:
            raise forms.ValidationError("Performer 1 and Performer 2 must be different people.")
        
        return cleaned_data


class BulkScheduleForm(forms.Form):
    """
    Form for bulk creating QA schedules.
    
    Allows creating multiple QA schedules for multiple LINACs
    over a date range with specified frequency.
    """
    linacs = forms.ModelMultipleChoiceField(
        queryset=Linac.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="Select Machines",
        help_text="Select the machines to include in the schedule"
    )
    frequency_months = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=1,
        label="QA Frequency (Months)",
        help_text="How many months between each QA session (e.g., 1 = Monthly, 3 = Quarterly)"
    )
    start_month = forms.CharField(
        widget=forms.DateInput(attrs={'type': 'month'}),
        label="Start Month",
        help_text="First month to generate schedules for"
    )
    end_month = forms.CharField(
        widget=forms.DateInput(attrs={'type': 'month'}),
        label="End Month",
        help_text="Last month to generate schedules for"
    )
    qa_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional: Reason for QA schedule'}),
        label="QA Reason (Optional)"
    )
    
    def clean_start_month(self):
        """Convert month input (YYYY-MM) to date (YYYY-MM-01)"""
        start_month = self.cleaned_data.get('start_month')
        if start_month:
            from datetime import datetime
            # Handle YYYY-MM format from month input
            if isinstance(start_month, str):
                if len(start_month) == 7 and '-' in start_month:  # YYYY-MM format
                    try:
                        return datetime.strptime(start_month + '-01', '%Y-%m-%d').date()
                    except ValueError:
                        raise forms.ValidationError("Please enter a valid month (YYYY-MM format).")
                else:
                    # Try to parse as date string
                    try:
                        date_obj = datetime.strptime(start_month, '%Y-%m-%d').date()
                        return date_obj.replace(day=1)
                    except ValueError:
                        raise forms.ValidationError("Please enter a valid month (YYYY-MM format).")
            elif hasattr(start_month, 'day'):
                # It's already a date object, set to first day
                return start_month.replace(day=1)
        raise forms.ValidationError("Start month is required.")
    
    def clean_end_month(self):
        """Convert month input (YYYY-MM) to date (YYYY-MM-01)"""
        end_month = self.cleaned_data.get('end_month')
        if end_month:
            from datetime import datetime
            # Handle YYYY-MM format from month input
            if isinstance(end_month, str):
                if len(end_month) == 7 and '-' in end_month:  # YYYY-MM format
                    try:
                        return datetime.strptime(end_month + '-01', '%Y-%m-%d').date()
                    except ValueError:
                        raise forms.ValidationError("Please enter a valid month (YYYY-MM format).")
                else:
                    # Try to parse as date string
                    try:
                        date_obj = datetime.strptime(end_month, '%Y-%m-%d').date()
                        return date_obj.replace(day=1)
                    except ValueError:
                        raise forms.ValidationError("Please enter a valid month (YYYY-MM format).")
            elif hasattr(end_month, 'day'):
                # It's already a date object, set to first day
                return end_month.replace(day=1)
        raise forms.ValidationError("End month is required.")
    
    def clean(self):
        """Validate that end_month is after start_month"""
        cleaned_data = super().clean()
        start_month = cleaned_data.get('start_month')
        end_month = cleaned_data.get('end_month')
        
        if start_month and end_month:
            if end_month < start_month:
                raise forms.ValidationError("End month must be after or equal to start month.")
        
        return cleaned_data


class AdhocQAScheduleForm(forms.ModelForm):
    """
    Form for creating non-scheduled QA sessions (unexpected QA).
    
    Used for ad-hoc QA sessions such as machine breakdowns or maintenance.
    """
    
    class Meta:
        model = QASchedule
        fields = ['linac', 'performer1', 'performer2', 'expected_qa_date', 'qa_reason']
        widgets = {
            'expected_qa_date': forms.DateInput(attrs={'type': 'date'}),
            'qa_reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Reason for non-scheduled QA (e.g., Machine breakdown, Maintenance)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['linac'].queryset = Linac.objects.filter(is_active=True)
        self.fields['linac'].label = 'Machine'
        
        # Set up performer fields with full name display
        self.fields['performer1'].queryset = User.objects.filter(is_active=True)
        self.fields['performer2'].queryset = User.objects.filter(is_active=True)
        self.fields['performer2'].required = False
        
        # Customize performer field labels
        self.fields['performer1'].label = 'Performer 1'
        self.fields['performer2'].label = 'Performer 2 (Optional)'
        self.fields['qa_reason'].label = 'Reason for Non-scheduled QA'
        
        # Override the widget to show full names
        self.fields['performer1'].widget = forms.Select(attrs={'class': 'form-control'})
        self.fields['performer2'].widget = forms.Select(attrs={'class': 'form-control'})
        
        # Set choices with full names
        performer1_choices = [('', 'Select Performer 1')]
        performer2_choices = [('', 'Select Performer 2 (Optional)')]
        
        for user in User.objects.filter(is_active=True):
            if user.first_name or user.last_name:
                full_name = f"{user.last_name} {user.first_name}".strip()
            else:
                full_name = user.username
            performer1_choices.append((user.id, full_name))
            performer2_choices.append((user.id, full_name))
        
        self.fields['performer1'].choices = performer1_choices
        self.fields['performer2'].choices = performer2_choices
    
    def clean(self):
        cleaned_data = super().clean()
        performer1 = cleaned_data.get('performer1')
        performer2 = cleaned_data.get('performer2')
        
        if performer1 and performer2 and performer1 == performer2:
            raise forms.ValidationError("Performer 1 and Performer 2 must be different people.")
        
        return cleaned_data


# ============================================================================
# Organization Settings Forms
# ============================================================================

class OrganizationSettingsForm(forms.ModelForm):
    """
    Form for editing organization settings.
    
    Includes logo, organization name, homepage images, and report template.
    """
    
    class Meta:
        model = OrganizationSettings
        fields = ['logo', 'organization_name', 'left_side_image', 'bottom_image', 'report_template', 'service_report_template']
        widgets = {
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'organization_name': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter organization name (each line will be displayed separately)'
            }),
            'left_side_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'bottom_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'report_template': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }),
            'service_report_template': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }),
        }
        labels = {
            'logo': 'Organization Logo',
            'organization_name': 'Organization Name',
            'left_side_image': 'Left Side Image',
            'bottom_image': 'Bottom Image',
            'report_template': 'Report Template (DOCX)',
            'service_report_template': 'Service Report Template (DOCX)',
        }
        help_texts = {
            'logo': 'Upload a logo image file (PNG, JPG, etc.)',
            'organization_name': 'Enter the organization name. Each line will be displayed separately on the homepage.',
            'left_side_image': 'Upload an image file to display on the left side of the homepage (PNG, JPG, etc.)',
            'bottom_image': 'Upload an image file to display at the bottom of the homepage (PNG, JPG, etc.)',
            'report_template': 'Upload a DOCX template file for QA reports. Use placeholders like {{LINAC_NAME}}, {{DATE_PERFORMED}}, etc. See help section below for all available placeholders.',
            'service_report_template': 'Upload a DOCX template file for service reports. Use {{REPORT_PRINTING_DATE}}, {{REPORT_PRINTING_MONTH}}, {{REPORT_PRINTING_YEAR}}, and {{SERVICE_TABLE}}.',
        }


# ============================================================================
# Document Forms
# ============================================================================

class DosimeterDocumentForm(forms.ModelForm):
    """
    Form for uploading documents to Dosimeters.
    """
    class Meta:
        model = DosimeterDocument
        fields = ['file', 'file_name', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.png,.jpg,.jpeg,.tiff,.tif'
            }),
            'file_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'file': 'Select File',
            'file_name': 'File Name',
            'description': 'Description (optional)',
        }

class LinacDocumentForm(forms.ModelForm):
    """
    Form for uploading documents to LINACs.
    """
    class Meta:
        model = LinacDocument
        fields = ['file', 'file_name', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.png,.jpg,.jpeg,.tiff,.tif'
            }),
            'file_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'file': 'Select File',
            'file_name': 'File Name',
            'description': 'Description (optional)',
        }

# ============================================================================
# User Forms
# ============================================================================

class UserForm(forms.ModelForm):
    """
    Form for creating and editing users.
    
    Handles password setting and user profile role assignment.
    """
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Leave blank to keep existing password. Enter a new password to change it.'
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Confirm the new password'
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Role',
        help_text='Select the user role'
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'username': 'Username',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
            'is_staff': 'Admin (Staff)',
            'is_active': 'Active',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Don't require password for existing users
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            # Load existing role if profile exists
            try:
                profile = self.instance.profile
                self.fields['role'].initial = profile.role
            except UserProfile.DoesNotExist:
                self.fields['role'].initial = None
        else:
            # Require password for new users
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # For new users, password is required
        if not self.instance.pk and not password:
            raise forms.ValidationError("Password is required for new users.")
        
        # If password is provided, it must match confirm_password
        if password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        role = self.cleaned_data.get('role')
        
        # Set password if provided
        if password:
            user.set_password(password)
        
        if commit:
            user.save()
            # Save or update user profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            if role:
                profile.role = role
            else:
                profile.role = None
            profile.save()
        
        return user


# ============================================================================
# Device Forms
# ============================================================================

class DeviceForm(forms.ModelForm):
    """
    Form for creating and editing Devices.
    """
    class Meta:
        model = Device
        fields = '__all__'
        exclude = ['created_at', 'updated_at']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'series_number': forms.TextInput(attrs={'class': 'form-control'}),
            'certificate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'storage_location': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'category': 'Category',
            'name': 'Name',
            'brand': 'Brand',
            'date': 'Date',
            'series_number': 'Series Number',
            'certificate_number': 'Certificate Number',
            'storage_location': 'Location',
            'is_active': 'Active',
        }


class DeviceDocumentForm(forms.ModelForm):
    """
    Form for uploading device documents.
    """
    class Meta:
        model = DeviceDocument
        fields = ['file', 'file_name', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'file': 'Document File',
            'file_name': 'File Name',
            'description': 'Description',
        }


# ============================================================================
# LINAC Service Report Forms
# ============================================================================

class LinacServiceReportForm(forms.ModelForm):
    """
    Form for creating and editing LINAC Service Reports.
    
    Includes PM service, equipment breakdown, downtime, and follow-up actions.
    """
    equipment = forms.ChoiceField(
        required=True,
        label="Equipment",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = LinacServiceReport
        fields = [
            'equipment', 'date', 'pm_service', 'equipment_breakdown',
            'issue_description', 'follow_up_actions', 'downtime_hours',
            'parts_replacement', 'notes', 'status',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pm_service': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'equipment_breakdown': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'issue_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'follow_up_actions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'downtime_hours': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3, 5, 24', 'step': 'any'}),
            'parts_replacement': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'date': 'Date',
            'pm_service': 'PM Service',
            'equipment_breakdown': 'Equipment Breakdown',
            'issue_description': 'Issue Description',
            'follow_up_actions': 'Follow-up Actions',
            'downtime_hours': 'Downtime (hours)',
            'parts_replacement': 'Parts Replacement',
            'notes': 'Notes',
            'status': 'Status',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', '-- Select Equipment --')]
        for linac in Linac.objects.filter(is_active=True).order_by('name'):
            choices.append((f'linac-{linac.id}', linac.name))
        for device in Device.objects.filter(is_active=True).order_by('category', 'name'):
            choices.append((f'device-{device.id}', device.name))
        self.fields['equipment'].choices = choices

        if self.instance and self.instance.pk:
            if self.instance.linac_id:
                self.fields['equipment'].initial = f'linac-{self.instance.linac_id}'
            elif self.instance.device_id:
                self.fields['equipment'].initial = f'device-{self.instance.device_id}'

    def clean_equipment(self):
        value = self.cleaned_data.get('equipment', '')
        if '-' not in value:
            raise forms.ValidationError('Please select valid equipment.')
        equipment_type, pk = value.split('-', 1)
        if equipment_type not in ('linac', 'device') or not pk.isdigit():
            raise forms.ValidationError('Please select valid equipment.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        value = cleaned_data.get('equipment')
        if value and '-' in value:
            equipment_type, pk = value.split('-', 1)
            if equipment_type == 'linac':
                self.instance.linac_id = int(pk)
                self.instance.device = None
            elif equipment_type == 'device':
                self.instance.device_id = int(pk)
                self.instance.linac = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        equipment_type, pk = self.cleaned_data['equipment'].split('-', 1)
        if equipment_type == 'linac':
            instance.linac_id = int(pk)
            instance.device = None
        else:
            instance.device_id = int(pk)
            instance.linac = None
        if commit:
            instance.save()
        return instance

# ============================================================================
# Statistics Forms
# ============================================================================

class StatisticsFilterForm(forms.Form):
    """Filter form for Statistics module view modes."""

    VIEW_MODE_CHOICES = [
        ('overview', 'Overview'),
        ('single_test', 'Single Test Trend'),
        ('linac_all_tests', 'All Tests for Selected LINAC'),
        ('category_trends', 'Category Trends'),
        ('beam_energy', 'Beam Energy Trends'),
    ]
    DATE_PRESET_CHOICES = [
        ('last_3_months', 'Last 3 months'),
        ('last_6_months', 'Last 6 months'),
        ('last_12_months', 'Last 12 months'),
        ('year_to_date', 'Year to date'),
        ('previous_year', 'Previous year'),
        ('custom', 'Custom'),
    ]
    CATEGORY_CHOICES = [
        ('all', 'All'),
        ('mechanical', 'Mechanical'),
        ('beam', 'Beam / Dose'),
        ('film', 'Film'),
        ('isocenter', 'Isocenter'),
    ]

    view_mode = forms.ChoiceField(choices=VIEW_MODE_CHOICES, initial='overview')
    date_preset = forms.ChoiceField(choices=DATE_PRESET_CHOICES, initial='last_12_months')
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)
    linac_ids = forms.MultipleChoiceField(required=False)
    test_category = forms.ChoiceField(choices=CATEGORY_CHOICES, initial='all', required=False)
    qa_test_id = forms.IntegerField(required=False)
    energy = forms.CharField(required=False)
    beam_test_group = forms.CharField(required=False, initial='all')
    result_status = forms.ChoiceField(
        choices=[('all', 'All'), ('normal', 'Normal'), ('warning', 'Warning'), ('failed', 'Failed')],
        initial='all',
        required=False,
    )
    include_inactive_linacs = forms.BooleanField(required=False)
    include_drafts = forms.BooleanField(required=False)
    show_only_with_data = forms.BooleanField(required=False)

    def __init__(self, *args, linac_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if linac_choices is not None:
            self.fields['linac_ids'].choices = linac_choices

    def to_filters(self):
        from .statistics_service import StatisticsFilters

        cleaned = self.cleaned_data
        linac_ids = []
        for val in cleaned.get('linac_ids') or []:
            try:
                linac_ids.append(int(val))
            except (TypeError, ValueError):
                pass
        return StatisticsFilters(
            view_mode=cleaned.get('view_mode', 'overview'),
            date_preset=cleaned.get('date_preset', 'last_12_months'),
            date_from=cleaned.get('date_from'),
            date_to=cleaned.get('date_to'),
            linac_ids=linac_ids,
            test_category=cleaned.get('test_category') or 'all',
            qa_test_id=cleaned.get('qa_test_id'),
            energy=cleaned.get('energy') or None,
            beam_test_group=cleaned.get('beam_test_group') or 'all',
            result_status=cleaned.get('result_status') or 'all',
            include_inactive_linacs=cleaned.get('include_inactive_linacs', False),
            include_drafts=cleaned.get('include_drafts', False),
            show_only_with_data=cleaned.get('show_only_with_data', False),
        )
