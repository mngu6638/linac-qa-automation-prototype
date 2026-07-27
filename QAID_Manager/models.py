"""
Django models for QAID Manager application.

This module contains all database models including:
- LINAC (Linear Accelerator) machine configurations
- QA Records, Schedules, and Tests
- Dosimeters and Devices
- Film Analysis results
- Dose Calculations
- User profiles and activities
- Organization settings
"""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
import os
import datetime


# ============================================================================
# File Upload Path Functions
# ============================================================================

def fieldsize_film_upload_path(instance, filename):
    """Generate upload path for field size film images"""
    ext = filename.split('.')[-1]
    return f'film_uploads/Fieldsize_film.{ext}'

def collimator_film_upload_path(instance, filename):
    """Generate upload path for collimator film images"""
    ext = filename.split('.')[-1]
    return f'film_uploads/Colli_film.{ext}'

def gantry_film_upload_path(instance, filename):
    """Generate upload path for gantry film images"""
    ext = filename.split('.')[-1]
    return f'film_uploads/Gantry_film.{ext}'


# ============================================================================
# LINAC (Linear Accelerator) Model
# ============================================================================
class Linac(models.Model):
    # Basic Information
    name = models.CharField(max_length=100, verbose_name="Tên máy")
    series_number = models.CharField(max_length=100, blank=True, verbose_name="Series Number")
    
    # Installation and Certification Dates
    installation_date = models.DateField(null=True, blank=True, verbose_name="Ngày lắp đặt")
    certification_due_date = models.DateField(null=True, blank=True, verbose_name="Ngày đến hạn Kiểm định")
    
    # Energy Options - Multiple choice
    ENERGY_CHOICES = [
        ('6MV', '6MV'),
        ('6MV_FFF', '6MV FFF'),
        ('10MV', '10MV'),
        ('10MV_FFF', '10MV FFF'),
        ('15MV', '15MV'),
        ('15MV_FFF', '15MV FFF'),
        ('4MeV', '4MeV'),
        ('5MeV', '5MeV'),
        ('6MeV', '6MeV'),
        ('7MeV', '7MeV'),
        ('8MeV', '8MeV'),
        ('9MeV', '9MeV'),
        ('10MeV', '10MeV'),
        ('11MeV', '11MeV'),
        ('12MeV', '12MeV'),
        ('13MeV', '13MeV'),
        ('14MeV', '14MeV'),
        ('15MeV', '15MeV'),
        ('16MeV', '16MeV'),
        ('17MeV', '17MeV'),
        ('18MeV', '18MeV'),
    ]
    energy = models.JSONField(default=list, blank=True, verbose_name="Năng lượng")
    
    # Dosimetry Method
    DOSIMETRY_CHOICES = [
        ('SAD_TRS398', 'SAD (TRS398)'),
        ('SSD_TG51', 'SSD (TG51)'),
    ]
    dosimetry_method = models.CharField(max_length=20, choices=DOSIMETRY_CHOICES, blank=True, verbose_name="Phương pháp chuẩn liều")
    
    # Commissioning and Beam Modelling Information
    cat_info = models.TextField(blank=True, verbose_name="CAT Information")
    beam_modelling_info = models.TextField(blank=True, verbose_name="Beam Modelling Information")
    
    # Beam Modelling Information - Dose Reference Depth
    beam_dose_ref_depth_6mv = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 6 MV")
    beam_dose_ref_depth_10mv = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 10 MV")
    beam_dose_ref_depth_15mv = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 15 MV")
    beam_dose_ref_depth_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 6 MV FFF")
    beam_dose_ref_depth_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 10 MV FFF")
    beam_dose_ref_depth_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 15 MV FFF")
    beam_dose_ref_depth_4mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 4 MeV")
    beam_dose_ref_depth_5mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 5 MeV")
    beam_dose_ref_depth_6mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 6 MeV")
    beam_dose_ref_depth_7mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 7 MeV")
    beam_dose_ref_depth_8mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 8 MeV")
    beam_dose_ref_depth_9mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 9 MeV")
    beam_dose_ref_depth_10mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 10 MeV")
    beam_dose_ref_depth_11mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 11 MeV")
    beam_dose_ref_depth_12mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 12 MeV")
    beam_dose_ref_depth_13mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 13 MeV")
    beam_dose_ref_depth_14mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 14 MeV")
    beam_dose_ref_depth_15mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 15 MeV")
    beam_dose_ref_depth_16mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 16 MeV")
    beam_dose_ref_depth_17mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 17 MeV")
    beam_dose_ref_depth_18mev = models.FloatField(null=True, blank=True, verbose_name="Dose Reference Depth - 18 MeV")
    
    # Beam Modelling Information - TPR or TMR (Zreff)
    beam_tpr_zreff_6mv = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 6 MV")
    beam_tpr_zreff_10mv = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 10 MV")
    beam_tpr_zreff_15mv = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 15 MV")
    beam_tpr_zreff_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 6 MV FFF")
    beam_tpr_zreff_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 10 MV FFF")
    beam_tpr_zreff_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR or TMR (Zreff) - 15 MV FFF")
    # R50 fields for electron beams (MeV energies) - removed TPR/TMR fields for electrons
    
    # Beam Modelling Information - PDD20/10
    beam_pdd_20_10_6mv = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 6 MV")
    beam_pdd_20_10_10mv = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 10 MV")
    beam_pdd_20_10_15mv = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 15 MV")
    beam_pdd_20_10_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 6 MV FFF")
    beam_pdd_20_10_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 10 MV FFF")
    beam_pdd_20_10_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD20/10 - 15 MV FFF")
    # Removed PDD20/10 fields for electron beams (MeV energies)
    
    # Beam Modelling Information - TPR (calculated from PDD20/10)
    beam_tpr_calculated_6mv = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 6 MV")
    beam_tpr_calculated_10mv = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 10 MV")
    beam_tpr_calculated_15mv = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 15 MV")
    beam_tpr_calculated_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 6 MV FFF")
    beam_tpr_calculated_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 10 MV FFF")
    beam_tpr_calculated_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="TPR (calculated) - 15 MV FFF")
    # Removed TPR (calculated) fields for electron beams (MeV energies)
    
    # Beam Modelling Information - R50 (for electron beams only)
    beam_r50_4mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 4 MeV")
    beam_r50_5mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 5 MeV")
    beam_r50_6mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 6 MeV")
    beam_r50_7mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 7 MeV")
    beam_r50_8mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 8 MeV")
    beam_r50_9mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 9 MeV")
    beam_r50_10mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 10 MeV")
    beam_r50_11mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 11 MeV")
    beam_r50_12mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 12 MeV")
    beam_r50_13mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 13 MeV")
    beam_r50_14mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 14 MeV")
    beam_r50_15mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 15 MeV")
    beam_r50_16mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 16 MeV")
    beam_r50_17mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 17 MeV")
    beam_r50_18mev = models.FloatField(null=True, blank=True, verbose_name="R50 - 18 MeV")
    
    # CAT Test Results - Mechanical Tests
    cat_gantry_isocenter = models.FloatField(null=True, blank=True, verbose_name="Gantry Iso (± 2mm)")
    cat_collimator_isocenter = models.FloatField(null=True, blank=True, verbose_name="Collimator Iso (± 1mm)")
    cat_field_size_12x12 = models.FloatField(null=True, blank=True, verbose_name="Field-size (12x12cm) (± 1mm)")
    cat_table_isocenter = models.FloatField(null=True, blank=True, verbose_name="Table Iso")
    cat_table_rotation = models.FloatField(null=True, blank=True, verbose_name="Table rotation")
    cat_table_height_isocenter = models.FloatField(null=True, blank=True, verbose_name="Table height Iso")
    cat_table_height = models.FloatField(null=True, blank=True, verbose_name="Table height")
    cat_table_long = models.FloatField(null=True, blank=True, verbose_name="Table long")
    cat_table_lateral = models.FloatField(null=True, blank=True, verbose_name="Table lateral")
    
    # CAT Test Results - Photon Beam Tests
    cat_d10_6mv = models.FloatField(null=True, blank=True, verbose_name="D10 - 6 MV (± 1%)")
    cat_d10_10mv = models.FloatField(null=True, blank=True, verbose_name="D10 - 10 MV (± 1%)")
    cat_d10_15mv = models.FloatField(null=True, blank=True, verbose_name="D10 - 15 MV (± 1%)")
    
    # CAT Test Results - Photon Symmetry Tests
    cat_symmetry_6mv_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 6 MV - Inline (≤ 3%)")
    cat_symmetry_6mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 6 MV - Crossline (≤ 3%)")
    cat_symmetry_10mv_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 10 MV - Inline (≤ 3%)")
    cat_symmetry_10mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 10 MV - Crossline (≤ 3%)")
    cat_symmetry_15mv_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 15 MV - Inline (≤ 3%)")
    cat_symmetry_15mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 15 MV - Crossline (≤ 3%)")
    
    # CAT Test Results - Photon Flatness Tests
    cat_flatness_6mv_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 6 MV - Inline (≤ 5%)")
    cat_flatness_6mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 6 MV - Crossline (≤ 5%)")
    cat_flatness_10mv_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 10 MV - Inline (≤ 5%)")
    cat_flatness_10mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 10 MV - Crossline (≤ 5%)")
    cat_flatness_15mv_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 15 MV - Inline (≤ 5%)")
    cat_flatness_15mv_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 15 MV - Crossline (≤ 5%)")
    
    # CAT Test Results - Electron Beam Tests
    cat_r80_4mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 4 MeV (± 1%)")
    cat_r80_5mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 5 MeV (± 1%)")
    cat_r80_6mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 6 MeV (± 1%)")
    cat_r80_7mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 7 MeV (± 1%)")
    cat_r80_8mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 8 MeV (± 1%)")
    cat_r80_9mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 9 MeV (± 1%)")
    cat_r80_10mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 10 MeV (± 1%)")
    cat_r80_11mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 11 MeV (± 1%)")
    cat_r80_12mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 12 MeV (± 1%)")
    cat_r80_13mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 13 MeV (± 1%)")
    cat_r80_14mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 14 MeV (± 1%)")
    cat_r80_15mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 15 MeV (± 1%)")
    cat_r80_16mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 16 MeV (± 1%)")
    cat_r80_17mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 17 MeV (± 1%)")
    cat_r80_18mev = models.FloatField(null=True, blank=True, verbose_name="R80 - 18 MeV (± 1%)")
    
    # CAT Test Results - Electron Symmetry Tests
    cat_symmetry_4mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 4 MeV - Inline (≤ 3%)")
    cat_symmetry_4mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 4 MeV - Crossline (≤ 3%)")
    cat_symmetry_5mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 5 MeV - Inline (≤ 3%)")
    cat_symmetry_5mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 5 MeV - Crossline (≤ 3%)")
    cat_symmetry_6mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 6 MeV - Inline (≤ 3%)")
    cat_symmetry_6mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 6 MeV - Crossline (≤ 3%)")
    cat_symmetry_7mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 7 MeV - Inline (≤ 3%)")
    cat_symmetry_7mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 7 MeV - Crossline (≤ 3%)")
    cat_symmetry_8mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 8 MeV - Inline (≤ 3%)")
    cat_symmetry_8mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 8 MeV - Crossline (≤ 3%)")
    cat_symmetry_9mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 9 MeV - Inline (≤ 3%)")
    cat_symmetry_9mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 9 MeV - Crossline (≤ 3%)")
    cat_symmetry_10mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 10 MeV - Inline (≤ 3%)")
    cat_symmetry_10mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 10 MeV - Crossline (≤ 3%)")
    cat_symmetry_11mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 11 MeV - Inline (≤ 3%)")
    cat_symmetry_11mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 11 MeV - Crossline (≤ 3%)")
    cat_symmetry_12mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 12 MeV - Inline (≤ 3%)")
    cat_symmetry_12mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 12 MeV - Crossline (≤ 3%)")
    cat_symmetry_13mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 13 MeV - Inline (≤ 3%)")
    cat_symmetry_13mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 13 MeV - Crossline (≤ 3%)")
    cat_symmetry_14mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 14 MeV - Inline (≤ 3%)")
    cat_symmetry_14mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 14 MeV - Crossline (≤ 3%)")
    cat_symmetry_15mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 15 MeV - Inline (≤ 3%)")
    cat_symmetry_15mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 15 MeV - Crossline (≤ 3%)")
    cat_symmetry_16mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 16 MeV - Inline (≤ 3%)")
    cat_symmetry_16mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 16 MeV - Crossline (≤ 3%)")
    cat_symmetry_17mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 17 MeV - Inline (≤ 3%)")
    cat_symmetry_17mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 17 MeV - Crossline (≤ 3%)")
    cat_symmetry_18mev_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 18 MeV - Inline (≤ 3%)")
    cat_symmetry_18mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry - 18 MeV - Crossline (≤ 3%)")
    
    # CAT Test Results - Electron Flatness Tests
    cat_flatness_4mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 4 MeV - Inline (≤ 5%)")
    cat_flatness_4mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 4 MeV - Crossline (≤ 5%)")
    cat_flatness_5mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 5 MeV - Inline (≤ 5%)")
    cat_flatness_5mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 5 MeV - Crossline (≤ 5%)")
    cat_flatness_6mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 6 MeV - Inline (≤ 5%)")
    cat_flatness_6mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 6 MeV - Crossline (≤ 5%)")
    cat_flatness_7mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 7 MeV - Inline (≤ 5%)")
    cat_flatness_7mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 7 MeV - Crossline (≤ 5%)")
    cat_flatness_8mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 8 MeV - Inline (≤ 5%)")
    cat_flatness_8mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 8 MeV - Crossline (≤ 5%)")
    cat_flatness_9mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 9 MeV - Inline (≤ 5%)")
    cat_flatness_9mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 9 MeV - Crossline (≤ 5%)")
    cat_flatness_10mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 10 MeV - Inline (≤ 5%)")
    cat_flatness_10mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 10 MeV - Crossline (≤ 5%)")
    cat_flatness_11mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 11 MeV - Inline (≤ 5%)")
    cat_flatness_11mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 11 MeV - Crossline (≤ 5%)")
    cat_flatness_12mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 12 MeV - Inline (≤ 5%)")
    cat_flatness_12mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 12 MeV - Crossline (≤ 5%)")
    cat_flatness_13mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 13 MeV - Inline (≤ 5%)")
    cat_flatness_13mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 13 MeV - Crossline (≤ 5%)")
    cat_flatness_14mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 14 MeV - Inline (≤ 5%)")
    cat_flatness_14mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 14 MeV - Crossline (≤ 5%)")
    cat_flatness_15mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 15 MeV - Inline (≤ 5%)")
    cat_flatness_15mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 15 MeV - Crossline (≤ 5%)")
    cat_flatness_16mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 16 MeV - Inline (≤ 5%)")
    cat_flatness_16mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 16 MeV - Crossline (≤ 5%)")
    cat_flatness_17mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 17 MeV - Inline (≤ 5%)")
    cat_flatness_17mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 17 MeV - Crossline (≤ 5%)")
    cat_flatness_18mev_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 18 MeV - Inline (≤ 5%)")
    cat_flatness_18mev_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness - 18 MeV - Crossline (≤ 5%)")
    
    # CAT Test Results - Output Factors
    cat_output_factor_6mv = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 6 MV (<1%)")
    cat_output_factor_10mv = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 10 MV (<1%)")
    cat_output_factor_15mv = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 15 MV (<1%)")
    cat_output_factor_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 6 MV FFF (<1%)")
    cat_output_factor_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 10 MV FFF (<1%)")
    cat_output_factor_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 15 MV FFF (<1%)")
    cat_output_factor_4mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 4 MeV (<1%)")
    cat_output_factor_5mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 5 MeV (<1%)")
    cat_output_factor_6mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 6 MeV (<1%)")
    cat_output_factor_7mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 7 MeV (<1%)")
    cat_output_factor_8mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 8 MeV (<1%)")
    cat_output_factor_9mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 9 MeV (<1%)")
    cat_output_factor_10mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 10 MeV (<1%)")
    cat_output_factor_11mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 11 MeV (<1%)")
    cat_output_factor_12mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 12 MeV (<1%)")
    cat_output_factor_13mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 13 MeV (<1%)")
    cat_output_factor_14mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 14 MeV (<1%)")
    cat_output_factor_15mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 15 MeV (<1%)")
    cat_output_factor_16mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 16 MeV (<1%)")
    cat_output_factor_17mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 17 MeV (<1%)")
    cat_output_factor_18mev = models.FloatField(null=True, blank=True, verbose_name="Output Factor - 18 MeV (<1%)")
    
    # CAT Test Results - Wedge Factors
    cat_wedge_factor_6mv = models.FloatField(null=True, blank=True, verbose_name="Wedge Factor - 6 MV (<1%)")
    cat_wedge_factor_10mv = models.FloatField(null=True, blank=True, verbose_name="Wedge Factor - 10 MV (<1%)")
    cat_wedge_factor_15mv = models.FloatField(null=True, blank=True, verbose_name="Wedge Factor - 15 MV (<1%)")
    
    # CAT Test Results - TMR Values
    cat_tmr_6mv = models.FloatField(null=True, blank=True, verbose_name="TMR - 6 MV")
    cat_tmr_10mv = models.FloatField(null=True, blank=True, verbose_name="TMR - 10 MV")
    cat_tmr_15mv = models.FloatField(null=True, blank=True, verbose_name="TMR - 15 MV")
    cat_tmr_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="TMR - 6 MV FFF")
    cat_tmr_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="TMR - 10 MV FFF")
    cat_tmr_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="TMR - 15 MV FFF")
    
    # CAT Test Results - PDD Values
    cat_pdd_20_10_6mv = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 6 MV")
    cat_pdd_20_10_10mv = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 10 MV")
    cat_pdd_20_10_15mv = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 15 MV")
    cat_pdd_20_10_6mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 6 MV FFF")
    cat_pdd_20_10_10mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 10 MV FFF")
    cat_pdd_20_10_15mv_fff = models.FloatField(null=True, blank=True, verbose_name="PDD 20/10 - 15 MV FFF")
    
    # CAT Test Results - Imaging Tests
    cat_uniformity = models.FloatField(null=True, blank=True, verbose_name="Uniformity (< 1.5%)")
    cat_low_contrast = models.FloatField(null=True, blank=True, verbose_name="Low Contrast (< 3.0%)")
    cat_high_contrast = models.CharField(max_length=10, null=True, blank=True, verbose_name="High Contrast (Spatial resolution)")
    cat_transverse_vertical_scale = models.FloatField(null=True, blank=True, verbose_name="Transverse Vertical Scale (± 1 mm)")
    cat_transverse_horizontal_scale = models.FloatField(null=True, blank=True, verbose_name="Transverse Horizontal Scale (± 1 mm)")
    cat_sagittal_geometric_scale = models.FloatField(null=True, blank=True, verbose_name="Sagittal Geometric Scale (± 1 mm)")
    cat_table_movement_accuracy = models.FloatField(null=True, blank=True, verbose_name="Table Movement Assisting Accuracy (± 1 mm)")
    
    # Status and timestamps
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "LINAC"
        verbose_name_plural = "LINACs"





# ============================================================================
# QA Protocol and Test Management Models
# ============================================================================

class QATest(models.Model):
    """
    QA Test definition model.
    
    Defines individual QA tests with their tolerance values and units.
    Used to configure which tests are available and their acceptance criteria.
    """
    TEST_TYPES = [
        ('mechanical', 'Mechanical Test'),
        ('beam', 'Beam Test'),
        ('film', 'Film Analysis'),
        ('isocenter', 'Isocenter Test'),
    ]
    
    name = models.CharField(max_length=200)
    test_type = models.CharField(max_length=20, choices=TEST_TYPES)
    description = models.TextField(blank=True)
    tolerance_value = models.FloatField()
    tolerance_unit = models.CharField(max_length=20)  # mm, %, degree, etc.
    order_index = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (±{self.tolerance_value} {self.tolerance_unit})"

    class Meta:
        ordering = ['test_type', 'order_index']
        verbose_name = "QA Test"
        verbose_name_plural = "QA Tests"


class CustomTestType(models.Model):
    """User-defined test type category (e.g. CBCT, Imaging)."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Custom Test Type"
        verbose_name_plural = "Custom Test Types"


class CustomTest(models.Model):
    """Individual test within a user-defined test type."""
    test_type = models.ForeignKey(
        CustomTestType, on_delete=models.CASCADE, related_name='tests'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    tolerance_value = models.FloatField()
    tolerance_unit = models.CharField(max_length=20)
    order_index = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (±{self.tolerance_value} {self.tolerance_unit})"

    class Meta:
        ordering = ['order_index']
        verbose_name = "Custom Test"
        verbose_name_plural = "Custom Tests"


class QAStatus(models.Model):
    """
    QA Status model for tracking QA record statuses.
    
    Statuses include: scheduled, in_progress, completed, passed, 
    passed_with_exception, minor_service, major_service, failed.
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('passed', 'QA Passed'),
        ('passed_with_exception', 'Passed with Deviation'),
        ('minor_service', 'Needs Minor Service'),
        ('major_service', 'Needs Major Service'),
        ('failed', 'QA Failed'),
    ]
    
    name = models.CharField(max_length=50, choices=STATUS_CHOICES)
    color = models.CharField(max_length=7, default='#000000')  # Hex color
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "QA Statuses"

class QARecord(models.Model):
    """
    Main QA Record model.
    
    Stores all QA test results for a specific LINAC on a specific date.
    Includes test results (test_01 through test_20), film analyses,
    dose calculations, and notes.
    """
    linac = models.ForeignKey(Linac, on_delete=models.CASCADE)
    qa_schedule = models.ForeignKey('QASchedule', on_delete=models.SET_NULL, null=True, blank=True, related_name='qa_records', verbose_name="QA Schedule")
    date_performed = models.DateField(auto_now_add=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.ForeignKey(QAStatus, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Test results - keeping original fields for backward compatibility
    test_01 = models.FloatField(null=True, blank=True)
    test_02 = models.FloatField(null=True, blank=True)
    test_03 = models.FloatField(null=True, blank=True)
    test_04 = models.FloatField(null=True, blank=True)
    test_05 = models.FloatField(null=True, blank=True)
    test_06 = models.FloatField(null=True, blank=True)
    test_07 = models.FloatField(null=True, blank=True)
    test_08 = models.FloatField(null=True, blank=True)
    test_09 = models.FloatField(null=True, blank=True)
    test_10 = models.FloatField(null=True, blank=True)
    test_11 = models.FloatField(null=True, blank=True)
    test_12 = models.FloatField(null=True, blank=True)
    test_13 = models.FloatField(null=True, blank=True)
    test_14 = models.FloatField(null=True, blank=True)
    test_15 = models.FloatField(null=True, blank=True)
    test_16 = models.FloatField(null=True, blank=True)
    test_17 = models.FloatField(null=True, blank=True)
    test_18 = models.FloatField(null=True, blank=True)
    test_19 = models.FloatField(null=True, blank=True)
    test_20 = models.FloatField(null=True, blank=True)

    # Store isocenter matrix data (individual angle values) as JSON
    # Format: {'iso_8_ab_0': value, 'iso_8_gt_0': value, 'iso_8_ab_90': value, ...}
    isocenter_matrix_data = models.JSONField(default=dict, blank=True, verbose_name="Isocenter Matrix Data")

    # Store multi-energy beam test results as JSON
    # Format: {
    #   "6MV": {
    #     "test_15": 1.000,
    #     "test_16": 0.998,
    #     "test_17": 1.02,
    #     "test_18": 1.05,
    #     "test_19": 1.001,
    #     "test_20": 0.999,
    #     "notes": "All within tolerance"
    #   },
    #   "10MV": { ... }
    # }
    beam_test_results = models.JSONField(default=dict, blank=True, verbose_name="Multi-Energy Beam Test Results")
    draft_dose_calculation_state = models.JSONField(default=dict, blank=True, verbose_name="Draft Dose Calculator State")

    custom_test_results = models.JSONField(default=dict, blank=True, verbose_name="Custom Test Results")

    notes = models.TextField(blank=True)
    is_draft = models.BooleanField(default=False, verbose_name="Draft QA Record")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date_performed} - {self.linac.name} - {self.performed_by}"
    
    def is_failed(self):
        """Check if QA failed based on status"""
        return self.status and self.status.name in ['failed', 'minor_service', 'major_service']

    class Meta:
        ordering = ['-date_performed']
        verbose_name = "QA Record"
        verbose_name_plural = "QA Records"

class QASchedule(models.Model):
    """
    QA Schedule model for planning and tracking QA sessions.
    
    Links LINACs with performers and scheduled dates. Tracks QA status,
    acceptance of failed tests, and notes.
    """
    linac = models.ForeignKey(Linac, on_delete=models.CASCADE)
    month_year = models.DateField(null=True, blank=True, verbose_name="Month/Year")
    performer1 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='qa_schedules_performer1', verbose_name="QA Performer 1")
    performer2 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='qa_schedules_performer2', verbose_name="QA Performer 2")
    status = models.ForeignKey(QAStatus, on_delete=models.SET_NULL, null=True, blank=True)
    qa_reason = models.TextField(blank=True, verbose_name="QA Reason")
    notes = models.TextField(blank=True)
    is_accepted = models.BooleanField(default=False, verbose_name="Failed QA Accepted")
    accepted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_qa_schedules', verbose_name="Accepted By")
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Accepted At")
    expected_qa_date = models.DateField(null=True, blank=True, verbose_name="Expected QA Date")
    qa_date = models.DateField(null=True, blank=True, verbose_name="Actual QA Date")
    failed_tests_data = models.JSONField(default=list, blank=True, verbose_name="Failed Tests Data")
    notes_edit_history = models.JSONField(default=list, blank=True, verbose_name="Notes Edit History")
    is_adhoc = models.BooleanField(default=False, verbose_name="Ad-hoc QA Session")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        performers = []
        if self.performer1:
            performers.append(self.performer1.get_full_name() or self.performer1.username)
        if self.performer2:
            performers.append(self.performer2.get_full_name() or self.performer2.username)
        performers_str = " & ".join(performers) if performers else "No performers assigned"
        
        if self.month_year:
            month_year_str = self.month_year.strftime('%B %Y')
        else:
            month_year_str = "No month assigned"
            
        return f"{self.linac.name} - {month_year_str} - {performers_str}"

    def get_status_color(self):
        """Get status color based on QA results"""
        if not self.status:
            return None
        
        if self.status.name == 'passed':
            return '#28a745'  # Green
        elif self.status.name in ['failed', 'minor_service', 'major_service']:
            return '#ff6b6b'  # Pale red
        else:
            return '#6c757d'  # Gray for other statuses

    def is_completed(self):
        """Check if QA is completed"""
        return self.status and self.status.name in ['passed', 'passed_with_exception', 'failed', 'minor_service', 'major_service']

    def is_failed(self):
        """Check if QA failed"""
        return self.status and self.status.name in ['failed', 'minor_service', 'major_service']

    def needs_acceptance(self):
        """Check if failed QA needs manual acceptance"""
        return self.is_failed() and not self.is_accepted

    class Meta:
        ordering = ['month_year', 'linac__name']
        verbose_name = "QA Schedule"
        verbose_name_plural = "QA Schedules"
        # Removed unique_together constraint to allow ad-hoc schedules in addition to regular monthly schedules
        # Uniqueness is now handled in the view logic (create_adhoc_qa_schedule)

class VietnameseHoliday(models.Model):
    """
    Vietnamese Holidays model for scheduling purposes.
    
    Used to exclude holidays when calculating expected QA dates.
    """
    HOLIDAY_TYPES = [
        ('national', 'National Holiday'),
        ('regional', 'Regional Holiday'),
        ('observance', 'Observance'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Holiday Name")
    date = models.DateField(verbose_name="Holiday Date")
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPES, default='national')
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.date}"

    class Meta:
        ordering = ['date']
        verbose_name = "Vietnamese Holiday"
        verbose_name_plural = "Vietnamese Holidays"
        unique_together = ['date', 'name']

class UserProfile(models.Model):
    """
    User Profile model extending Django User with additional fields.
    
    Adds role information (administrator, medical_physicist, radiation_therapist).
    """
    ROLE_CHOICES = [
        ('administrator', 'Administrator'),
        ('medical_physicist', 'Medical Physicist'),
        ('radiation_therapist', 'Radiation Therapist'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        blank=True,
        null=True,
        verbose_name="Role"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display() or 'No role assigned'}"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class UserActivity(models.Model):
    """
    User Activity Tracking model.
    
    Logs user actions such as login, QA record creation, film uploads, etc.
    """
    ACTIVITY_TYPES = [
        ('login', 'User Login'),
        ('qa_create', 'QA Record Created'),
        ('qa_update', 'QA Record Updated'),
        ('film_upload', 'Film Uploaded'),
        ('report_generated', 'Report Generated'),
        ('settings_changed', 'Settings Changed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.created_at}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "User Activities"

class FilmUpload(models.Model):
    """
    Film Upload model for field size analysis.
    
    Stores uploaded film images and extracted DPI information.
    Includes temporary storage for draggable lines used in analysis.
    """
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=fieldsize_film_upload_path)
    dpi = models.FloatField(default=70)  # Final DPI used for analysis
    extracted_dpi = models.FloatField(null=True, blank=True)  # DPI extracted from image

    # ✅ New field for temporary storage of draggable lines
    temp_lines = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.uploaded_by} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

class CollimatorFilmUpload(models.Model):
    """
    Collimator Film Upload model.
    
    Stores uploaded collimator film images for isocenter analysis.
    """
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=collimator_film_upload_path)
    dpi = models.FloatField(default=70)  # Final DPI used for analysis
    extracted_dpi = models.FloatField(null=True, blank=True)  # DPI extracted from image

    def __str__(self):
        return f"Collimator {self.uploaded_by} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

class GantryFilmUpload(models.Model):
    """
    Gantry Film Upload model.
    
    Stores uploaded gantry film images for isocenter analysis.
    """
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to=gantry_film_upload_path)
    dpi = models.FloatField(default=70)  # Final DPI used for analysis
    extracted_dpi = models.FloatField(null=True, blank=True)  # DPI extracted from image

    def __str__(self):
        return f"Gantry {self.uploaded_by} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['-uploaded_at']


class Dosimeter(models.Model):
    """
    Dosimeter (Ion Chamber) model.
    
    Stores calibration information for dosimeters used in dose calculations.
    Includes calibration factor, date, lab information, etc.
    """
    # Basic Information
    name = models.CharField(max_length=100, verbose_name="Tên buồng ion")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Hãng sản xuất")
    series_number = models.CharField(max_length=100, blank=True, verbose_name="Số series")
    certificate_number = models.CharField(max_length=100, blank=True, verbose_name="Số chứng chỉ")
    
    # Calibration Information
    calibration_factor = models.FloatField(null=True, blank=True, verbose_name="Hệ số chuẩn (N_d,w)")
    calibration_date = models.DateField(null=True, blank=True, verbose_name="Ngày chuẩn")
    calibration_radiation_source = models.CharField(max_length=100, blank=True, verbose_name="Nguồn bức xạ chuẩn")
    calibration_temperature = models.FloatField(null=True, blank=True, verbose_name="Nhiệt độ chuẩn (T₀)")
    calibration_pressure = models.FloatField(null=True, blank=True, verbose_name="Áp suất chuẩn (P₀)")
    calibration_lab = models.CharField(max_length=200, blank=True, verbose_name="Phòng thí nghiệm chuẩn")
    
    # Status and timestamps
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand} ({self.series_number})"

    class Meta:
        ordering = ['name']
        verbose_name = "Dosimeter"
        verbose_name_plural = "Dosimeters"

class QAFilmAnalysis(models.Model):
    """
    QA Film Analysis Results model.
    
    Stores results from film analysis (field size, collimator isocenter, 
    gantry isocenter) with result images.
    """
    qa_record = models.ForeignKey(QARecord, on_delete=models.CASCADE, related_name='film_analyses')
    analysis_type = models.CharField(max_length=50, choices=[
        ('fieldsize', 'Field Size Analysis'),
        ('collimator_isocenter', 'Collimator Isocenter'),
        ('gantry_isocenter', 'Gantry Isocenter'),
    ])
    result_image = models.ImageField(upload_to='qa_results/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.qa_record.linac.name} - {self.analysis_type} - {self.created_at.strftime('%Y-%m-%d')}"

    def delete(self, *args, **kwargs):
        """Safely delete the file when the record is deleted"""
        if self.result_image:
            # Delete the file from storage
            if os.path.exists(self.result_image.path):
                os.remove(self.result_image.path)
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        """Handle file replacement safely"""
        if self.pk:  # If this is an update
            try:
                old_instance = QAFilmAnalysis.objects.get(pk=self.pk)
                if old_instance.result_image and old_instance.result_image != self.result_image:
                    # Delete old file if it exists
                    if os.path.exists(old_instance.result_image.path):
                        os.remove(old_instance.result_image.path)
            except QAFilmAnalysis.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "QA Film Analyses"

class QATestNote(models.Model):
    """
    QA Test Notes model.
    
    Stores individual notes for specific tests within a QA record.
    One note per test per QA record.
    """
    qa_record = models.ForeignKey(QARecord, on_delete=models.CASCADE, related_name='test_notes')
    test_number = models.IntegerField()  # test_01 = 1, test_02 = 2, etc.
    note_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Test {self.test_number} - {self.qa_record.linac.name} - {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['test_number']
        verbose_name_plural = "QA Test Notes"
        unique_together = ['qa_record', 'test_number']  # One note per test per QA record

class OrganizationSettings(models.Model):
    """
    Organization Settings model (Singleton pattern).
    
    Stores organization-specific settings: logo, organization name, 
    homepage images, and report template. Only one instance exists.
    """
    """Organization settings for customizing homepage logo, organization name, left side image, and bottom image"""
    logo = models.ImageField(upload_to='organization/', blank=True, null=True, verbose_name="Logo")
    organization_name = models.TextField(
        default="Demo Radiotherapy Physics Department",
        verbose_name="Tên tổ chức",
        help_text="Có thể nhập nhiều dòng, mỗi dòng sẽ hiển thị trên một dòng riêng"
    )
    left_side_image = models.ImageField(upload_to='organization/', blank=True, null=True, verbose_name="Left Side Image", help_text="Image displayed on the left side of the homepage")
    bottom_image = models.ImageField(upload_to='organization/', blank=True, null=True, verbose_name="Bottom Image", help_text="Image displayed at the bottom of the homepage")
    report_template = models.FileField(
        upload_to='organization/reports/', 
        blank=True, 
        null=True, 
        verbose_name="Report Template", 
        help_text="Upload a DOCX template file for QA reports. Use placeholders like {{LINAC_NAME}}, {{DATE_PERFORMED}}, etc."
    )
    service_report_template = models.FileField(
        upload_to='organization/reports/',
        blank=True,
        null=True,
        verbose_name="Service Report Template",
        help_text="Upload a DOCX template file for service reports. Use placeholders like {{REPORT_PRINTING_DATE}}, {{REPORT_PRINTING_MONTH}}, {{REPORT_PRINTING_YEAR}}, and {{SERVICE_TABLE}}."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Settings"
        verbose_name_plural = "Organization Settings"

    def __str__(self):
        return "Organization Settings"

    @classmethod
    def get_settings(cls):
        """Get or create the singleton instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        self.pk = 1
        super().save(*args, **kwargs)

# ============================================================================
# Signal Handlers for File Cleanup
# ============================================================================

@receiver(pre_delete, sender=QARecord)
def delete_qa_record_files(sender, instance, **kwargs):
    """
    Signal handler: Delete all associated film analysis files when QA record is deleted.
    """
    for film_analysis in instance.film_analyses.all():
        if film_analysis.result_image and os.path.exists(film_analysis.result_image.path):
            os.remove(film_analysis.result_image.path)

@receiver(pre_delete, sender=QAFilmAnalysis)
def delete_film_analysis_file(sender, instance, **kwargs):
    """
    Signal handler: Delete the file when film analysis record is deleted.
    """
    if instance.result_image and os.path.exists(instance.result_image.path):
        os.remove(instance.result_image.path)

@receiver(pre_delete, sender=FilmUpload)
def delete_fieldsize_upload_file(sender, instance, **kwargs):
    """Delete fieldsize upload file when DB row is removed."""
    if instance.image and os.path.exists(instance.image.path):
        os.remove(instance.image.path)

@receiver(pre_delete, sender=CollimatorFilmUpload)
def delete_collimator_upload_file(sender, instance, **kwargs):
    """Delete collimator upload file when DB row is removed."""
    if instance.image and os.path.exists(instance.image.path):
        os.remove(instance.image.path)

@receiver(pre_delete, sender=GantryFilmUpload)
def delete_gantry_upload_file(sender, instance, **kwargs):
    """Delete gantry upload file when DB row is removed."""
    if instance.image and os.path.exists(instance.image.path):
        os.remove(instance.image.path)

class PhysicsParameters(models.Model):
    """
    Physics Parameters model for dose calculations and beam modeling.
    
    Stores physics parameters such as Ks coefficients, k_QQo values,
    and other reference data used in dose calculations.
    """
    
    # Basic Information
    name = models.CharField(max_length=200, verbose_name="Parameter Name")
    parameter_type = models.CharField(max_length=50, choices=[
        ('ks_coefficients', 'Ks Coefficients (TRS398)'),
        ('kqqo', 'k_QQo (Beam Quality Correction)'),
        ('ndw', 'N_d,w (Dosimeter Calibration Factor)'),
        ('kpol', 'Kpol (Polarity Correction)'),
        ('ktp', 'Ktp (Temperature & Pressure)'),
        ('film_analysis', 'Film Analysis Parameters'),
        ('other', 'Other Physics Parameter'),
    ], verbose_name="Parameter Type")
    
    # Energy and Beam Information
    energy = models.CharField(max_length=20, blank=True, verbose_name="Energy (MV/MeV)")
    beam_type = models.CharField(max_length=20, choices=[
        ('photon', 'Photon'),
        ('electron', 'Electron'),
        ('both', 'Both'),
    ], default='photon', verbose_name="Beam Type")
    
    # Parameter Values (JSON field for flexible storage)
    parameter_values = models.JSONField(default=dict, verbose_name="Parameter Values")
    
    # For Ks coefficients (TRS398 Table 8.1)
    voltage_ratio = models.FloatField(null=True, blank=True, verbose_name="Voltage Ratio (V1/V2)")
    a0_coefficient = models.FloatField(null=True, blank=True, verbose_name="a0 Coefficient")
    a1_coefficient = models.FloatField(null=True, blank=True, verbose_name="a1 Coefficient")
    a2_coefficient = models.FloatField(null=True, blank=True, verbose_name="a2 Coefficient")
    
    # For k_QQo values
    reference_energy = models.CharField(max_length=20, blank=True, verbose_name="Reference Energy")
    kqqo_value = models.FloatField(null=True, blank=True, verbose_name="k_QQo Value")
    
    # Chamber/Detector Information
    chamber_type = models.CharField(max_length=100, blank=True, verbose_name="Chamber Type")
    chamber_volume = models.FloatField(null=True, blank=True, verbose_name="Chamber Volume (cm³)")
    
    # Reference Information
    reference_standard = models.CharField(max_length=100, blank=True, verbose_name="Reference Standard")
    reference_table = models.CharField(max_length=100, blank=True, verbose_name="Reference Table")
    reference_page = models.CharField(max_length=20, blank=True, verbose_name="Reference Page")
    
    # Notes and Description
    description = models.TextField(blank=True, verbose_name="Description")
    notes = models.TextField(blank=True, verbose_name="Notes")
    
    # Status and timestamps
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.parameter_type}) - {self.energy}"
    
    class Meta:
        ordering = ['parameter_type', 'energy', 'name']
        verbose_name = "Physics Parameter"
        verbose_name_plural = "Physics Parameters"
        constraints = [
            models.UniqueConstraint(
                fields=['parameter_type'],
                condition=models.Q(parameter_type='film_analysis'),
                name='unique_film_analysis_physics_parameter',
            ),
        ]


class DoseCalculation(models.Model):
    """
    Dose Calculation model.
    
    Stores results from the Dose Calculator tool including absolute dose,
    relative dose measurements (symmetry, flatness, output factor),
    and beam quality parameters.
    """
    
    # Link to QA Record
    qa_record = models.ForeignKey(QARecord, on_delete=models.CASCADE, related_name='dose_calculations')
    
    # General Information
    linac = models.ForeignKey(Linac, on_delete=models.CASCADE)
    energy = models.CharField(max_length=20)
    detector = models.ForeignKey(Dosimeter, on_delete=models.CASCADE)
    phantom = models.CharField(max_length=20, choices=[
        ('solid', 'Solid Phantom'),
        ('water', 'Water Phantom'),
    ])
    
    # Absolute Dose Calculations
    raw_measurement = models.FloatField(verbose_name="Raw Measurement (nC)")
    
    # Input values for Ktp calculation
    temperature = models.FloatField(null=True, blank=True, verbose_name="Temperature (°C)")
    pressure = models.FloatField(null=True, blank=True, verbose_name="Pressure (hPa)")
    
    # Input values for Kpol calculation
    m_plus = models.FloatField(null=True, blank=True, verbose_name="M+")
    m_minus = models.FloatField(null=True, blank=True, verbose_name="M-")
    
    # Input values for Ks calculation
    m1 = models.FloatField(null=True, blank=True, verbose_name="M1")
    m2 = models.FloatField(null=True, blank=True, verbose_name="M2")
    v1 = models.FloatField(null=True, blank=True, verbose_name="V1")
    v2 = models.FloatField(null=True, blank=True, verbose_name="V2")
    v1_v2_ratio = models.FloatField(null=True, blank=True, verbose_name="V1/V2 Ratio")
    
    # Ks coefficients
    a0 = models.FloatField(null=True, blank=True, verbose_name="a0 Coefficient")
    a1 = models.FloatField(null=True, blank=True, verbose_name="a1 Coefficient")
    a2 = models.FloatField(null=True, blank=True, verbose_name="a2 Coefficient")
    
    ktp_result = models.FloatField(verbose_name="Ktp Result")
    kpol_result = models.FloatField(verbose_name="Kpol Result")
    ks_result = models.FloatField(verbose_name="Ks Result")
    solid_phantom_factor = models.FloatField(null=True, blank=True, verbose_name="Solid Phantom Factor")
    mq_result = models.FloatField(verbose_name="MQ Result (nC)")
    dwq_zref = models.FloatField(verbose_name="Dw,Q(zref) (cGy)")
    dwq_zmax = models.FloatField(verbose_name="Dw,Q(zmax) (cGy)")
    
    # SSD Setup Fields
    absolute_setup_mode = models.CharField(max_length=10, default='SAD', verbose_name="Absolute Setup Mode")
    pdd_zref = models.FloatField(null=True, blank=True, verbose_name="PDD(zref) for SSD (%)")
    pdd_zref_source = models.CharField(max_length=30, null=True, blank=True, verbose_name="PDD(zref) Source")
    
    # Beam Quality Parameters
    pdd_20_10 = models.FloatField(null=True, blank=True, verbose_name="PDD(20/10)")
    tmr = models.FloatField(null=True, blank=True, verbose_name="TMR")
    tpr_20_10 = models.FloatField(null=True, blank=True, verbose_name="TPR(20/10)")
    kq_factor = models.FloatField(null=True, blank=True, verbose_name="Kq Factor")
    
    # Relative Dose Measurements
    m_ref = models.FloatField(null=True, blank=True, verbose_name="Mref (FS10x10)")
    m_left = models.FloatField(null=True, blank=True, verbose_name="MLeft (FS20x20)")
    m_right = models.FloatField(null=True, blank=True, verbose_name="MRight (FS20x20)")
    m_gun = models.FloatField(null=True, blank=True, verbose_name="MGun (FS20x20)")
    m_tar = models.FloatField(null=True, blank=True, verbose_name="MTar (FS20x20)")
    m_mid = models.FloatField(null=True, blank=True, verbose_name="Mmid (FS20x20)")
    m_wedge = models.FloatField(null=True, blank=True, verbose_name="Mwedge (FS10x10)")
    m_dmax = models.FloatField(null=True, blank=True, verbose_name="Mdmax (FS10x10, SSD100)")
    m_d10 = models.FloatField(null=True, blank=True, verbose_name="Md10 (FS10x10, SSD100)")
    
    # Relative Dose Results
    symmetry_crossline = models.FloatField(null=True, blank=True, verbose_name="Symmetry Crossline (%)")
    symmetry_inline = models.FloatField(null=True, blank=True, verbose_name="Symmetry Inline (%)")
    flatness_crossline = models.FloatField(null=True, blank=True, verbose_name="Flatness Crossline (%)")
    flatness_inline = models.FloatField(null=True, blank=True, verbose_name="Flatness Inline (%)")
    output_factor = models.FloatField(null=True, blank=True, verbose_name="Output Factor")
    wedge_factor = models.FloatField(null=True, blank=True, verbose_name="Wedge Factor")
    beam_energy_d10 = models.FloatField(null=True, blank=True, verbose_name="Beam Energy (D10)")
    
    # MU Linearity
    mu_10 = models.FloatField(null=True, blank=True, verbose_name="MU 10")
    mu_30 = models.FloatField(null=True, blank=True, verbose_name="MU 30")
    mu_50 = models.FloatField(null=True, blank=True, verbose_name="MU 50")
    mu_100 = models.FloatField(null=True, blank=True, verbose_name="MU 100")
    mu_300 = models.FloatField(null=True, blank=True, verbose_name="MU 300")
    mu_500 = models.FloatField(null=True, blank=True, verbose_name="MU 500")
    mu_r2 = models.FloatField(null=True, blank=True, verbose_name="MU Linearity R²")
    
    # QA Entry Auto-populated Values
    absolute_dose_deviation = models.FloatField(null=True, blank=True, verbose_name="Lieu tuyet doi")
    energy_stability_d10 = models.FloatField(null=True, blank=True, verbose_name="Su on dinh cua nang luong (D10)")
    symmetry_vs_commissioning = models.FloatField(null=True, blank=True, verbose_name="Tinh doi xung so voi gia tri tai thoi diem commissioning")
    flatness_vs_commissioning = models.FloatField(null=True, blank=True, verbose_name="Tinh phang so voi gia tri tai thoi diem commissioning")
    output_factor_deviation = models.FloatField(null=True, blank=True, verbose_name="He so lieu loi ra theo kich thuoc truong chieu")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Dose Calculation for {self.linac.name} - {self.energy} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dose Calculation"
        verbose_name_plural = "Dose Calculations"


# ============================================================================
# Document File Upload Path Functions
# ============================================================================

def dosimeter_file_upload_path(instance, filename):
    """Generate upload path for dosimeter files"""
    if instance.dosimeter and instance.dosimeter.id:
        return f'dosimeter_files/{instance.dosimeter.id}/{filename}'
    return f'dosimeter_files/temp/{filename}'

def linac_file_upload_path(instance, filename):
    """Generate upload path for LINAC files"""
    if instance.linac and instance.linac.id:
        return f'linac_files/{instance.linac.id}/{filename}'
    return f'linac_files/temp/{filename}'

class DosimeterDocument(models.Model):
    """
    Dosimeter Document model.
    
    Stores document files (PDFs, images, etc.) associated with dosimeters.
    """
    dosimeter = models.ForeignKey(Dosimeter, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(
        upload_to=dosimeter_file_upload_path,
        verbose_name="Document File"
    )
    file_name = models.CharField(max_length=255, verbose_name="File Name")
    description = models.TextField(blank=True, verbose_name="Description")
    file_type = models.CharField(
        max_length=50,
        choices=[
            ('pdf', 'PDF'),
            ('doc', 'Word Document'),
            ('docx', 'Word Document (DOCX)'),
            ('png', 'PNG Image'),
            ('jpg', 'JPEG Image'),
            ('jpeg', 'JPEG Image'),
            ('tiff', 'TIFF Image'),
            ('tif', 'TIFF Image'),
            ('other', 'Other'),
        ],
        default='other',
        verbose_name="File Type"
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.dosimeter.name} - {self.file_name}"
    
    def get_file_extension(self):
        """Get file extension from filename"""
        return self.file_name.split('.')[-1].lower() if '.' in self.file_name else ''
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Dosimeter Document"
        verbose_name_plural = "Dosimeter Documents"

class LinacDocument(models.Model):
    """
    LINAC Document model.
    
    Stores document files (PDFs, images, etc.) associated with LINACs.
    """
    linac = models.ForeignKey(Linac, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(
        upload_to=linac_file_upload_path,
        verbose_name="Document File"
    )
    file_name = models.CharField(max_length=255, verbose_name="File Name")
    description = models.TextField(blank=True, verbose_name="Description")
    file_type = models.CharField(
        max_length=50,
        choices=[
            ('pdf', 'PDF'),
            ('doc', 'Word Document'),
            ('docx', 'Word Document (DOCX)'),
            ('png', 'PNG Image'),
            ('jpg', 'JPEG Image'),
            ('jpeg', 'JPEG Image'),
            ('tiff', 'TIFF Image'),
            ('tif', 'TIFF Image'),
            ('other', 'Other'),
        ],
        default='other',
        verbose_name="File Type"
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.linac.name} - {self.file_name}"
    
    def get_file_extension(self):
        """Get file extension from filename"""
        return self.file_name.split('.')[-1].lower() if '.' in self.file_name else ''
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "LINAC Document"
        verbose_name_plural = "LINAC Documents"

class Device(models.Model):
    """
    Device and Equipment model.
    
    Stores information about various devices and equipment:
    Dosimeters, Machine QA Equipment, PSQA Equipment, TPS and HIS Equipment,
    CT-Sim, Positioning Equipment, and Others.
    """
    
    CATEGORY_CHOICES = [
        ('dosimeters', 'Dosimeters'),
        ('machine_qa', 'Machine QA Equipment'),
        ('psqa', 'PSQA Equipment'),
        ('tps_his', 'TPS and HIS Equipment'),
        ('ct_sim', 'CT-Sim'),
        ('positioning', 'Positioning Equipment'),
        ('others', 'Others'),
    ]
    
    # Basic Information
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        verbose_name="Category"
    )
    name = models.CharField(max_length=200, verbose_name="Name")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Brand")
    date = models.DateField(null=True, blank=True, verbose_name="Date")
    series_number = models.CharField(max_length=100, blank=True, verbose_name="Series Number")
    certificate_number = models.CharField(max_length=100, blank=True, verbose_name="Certificate Number")
    storage_location = models.CharField(max_length=200, blank=True, verbose_name="Location")
    
    # Status and timestamps
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.name} ({self.brand})"
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Device"
        verbose_name_plural = "Devices and Equipment"


def device_file_upload_path(instance, filename):
    """Generate upload path for device files"""
    if instance.device and instance.device.id:
        return f'device_files/{instance.device.id}/{filename}'
    return f'device_files/temp/{filename}'


class DeviceDocument(models.Model):
    """
    Device Document model.
    
    Stores document files associated with devices and equipment.
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(
        upload_to=device_file_upload_path,
        verbose_name="Document File"
    )
    file_name = models.CharField(max_length=255, verbose_name="File Name")
    description = models.TextField(blank=True, verbose_name="Description")
    file_type = models.CharField(
        max_length=50,
        choices=[
            ('pdf', 'PDF'),
            ('doc', 'Word Document'),
            ('docx', 'Word Document (DOCX)'),
            ('png', 'PNG Image'),
            ('jpg', 'JPEG Image'),
            ('jpeg', 'JPEG Image'),
            ('tiff', 'TIFF Image'),
            ('tif', 'TIFF Image'),
            ('other', 'Other'),
        ],
        default='other',
        verbose_name="File Type"
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.device.name} - {self.file_name}"
    
    def get_file_extension(self):
        """Get file extension from filename"""
        return self.file_name.split('.')[-1].lower() if '.' in self.file_name else ''
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Device Document"
        verbose_name_plural = "Device Documents"


@receiver(pre_delete, sender=DosimeterDocument)
def delete_dosimeter_document_file(sender, instance, **kwargs):
    """
    Signal handler: Delete the file when dosimeter document is deleted.
    """
    if instance.file and os.path.exists(instance.file.path):
        os.remove(instance.file.path)

@receiver(pre_delete, sender=LinacDocument)
def delete_linac_document_file(sender, instance, **kwargs):
    """
    Signal handler: Delete the file when LINAC document is deleted.
    """
    if instance.file and os.path.exists(instance.file.path):
        os.remove(instance.file.path)

@receiver(pre_delete, sender=DeviceDocument)
def delete_device_document_file(sender, instance, **kwargs):
    """
    Signal handler: Delete the file when device document is deleted.
    """
    if instance.file and os.path.exists(instance.file.path):
        os.remove(instance.file.path)


class LinacServiceReport(models.Model):
    """
    LINAC Service Report model.
    
    Stores service and error reports for LINACs including PM service,
    equipment breakdown, downtime, parts replacement, and follow-up actions.
    """
    
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('temporary', 'Temporary'),
    ]
    
    linac = models.ForeignKey(
        Linac,
        on_delete=models.SET_NULL,
        related_name='service_reports',
        verbose_name="LINAC",
        null=True,
        blank=True,
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        related_name='service_reports',
        verbose_name="Device",
        null=True,
        blank=True,
    )
    date = models.DateField(default=datetime.date.today, verbose_name="Date")
    pm_service = models.BooleanField(default=False, verbose_name="PM Service")
    equipment_breakdown = models.BooleanField(default=False, verbose_name="Equipment Breakdown")
    issue_description = models.TextField(blank=True, verbose_name="Issue Description")
    follow_up_actions = models.TextField(blank=True, verbose_name="Follow-up Actions")
    downtime_hours = models.FloatField(null=True, blank=True, verbose_name="Downtime (hours)")
    parts_replacement = models.TextField(blank=True, verbose_name="Parts Replacement")
    notes = models.TextField(blank=True, verbose_name="Notes")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_service_reports')
    
    def clean(self):
        super().clean()
        if bool(self.linac) == bool(self.device):
            raise ValidationError("Exactly one equipment must be selected (LINAC or Device).")

    @property
    def equipment(self):
        return self.linac or self.device

    def get_equipment_display(self):
        if self.linac:
            return self.linac.name
        if self.device:
            return self.device.name
        return "N/A"

    def __str__(self):
        report_type = []
        if self.pm_service:
            report_type.append("PM Service")
        if self.equipment_breakdown:
            report_type.append("Equipment Breakdown")
        type_str = " / ".join(report_type) if report_type else "Service Report"
        equipment_name = self.equipment.name if self.equipment else "Unknown equipment"
        return f"{equipment_name} - {type_str} - {self.date}"
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "LINAC Service Report"
        verbose_name_plural = "LINAC Service Reports"