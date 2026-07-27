"""
Film analysis configuration stored in PhysicsParameters (type: film_analysis).
"""
from __future__ import annotations

from .models import PhysicsParameters

FILM_ANALYSIS_PARAM_NAME = 'Film Analysis Parameters'
DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD = 0.3
DEFAULT_FIELD_SIZE_BAND_WIDTH_MM = 8.0
FIELD_SIZE_THRESHOLD_MIN = 0.01
FIELD_SIZE_THRESHOLD_MAX = 0.99
FIELD_SIZE_BAND_WIDTH_MM_MIN = 0.2
FIELD_SIZE_BAND_WIDTH_MM_MAX = 20.0
STATION_LINE_COUNT_MIN = 5
STATION_LINE_COUNT_MAX = 40


def _get_film_analysis_values() -> dict:
    param = (
        PhysicsParameters.objects.filter(parameter_type='film_analysis', is_active=True)
        .order_by('-updated_at')
        .first()
    )
    if param and isinstance(param.parameter_values, dict):
        return param.parameter_values
    return {}


def _normalize_threshold(value) -> float | None:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return None
    if FIELD_SIZE_THRESHOLD_MIN <= threshold <= FIELD_SIZE_THRESHOLD_MAX:
        return threshold
    return None


def _normalize_band_width_mm(value) -> float | None:
    try:
        band_mm = float(value)
    except (TypeError, ValueError):
        return None
    if FIELD_SIZE_BAND_WIDTH_MM_MIN <= band_mm <= FIELD_SIZE_BAND_WIDTH_MM_MAX:
        return band_mm
    return None


def band_width_mm_to_pixels(band_width_mm: float, dpi: float) -> float:
    """Convert total analysis band width in mm to pixels using film DPI."""
    dpi = max(75, min(1200, float(dpi)))
    px_per_mm = dpi / 25.4
    return float(band_width_mm) * px_per_mm


def compute_station_line_count(band_width_px: float) -> int:
    """Number of parallel sample paths distributed across the band (median combined)."""
    return max(
        STATION_LINE_COUNT_MIN,
        min(STATION_LINE_COUNT_MAX, int(round(float(band_width_px)))),
    )


def deduplicate_film_analysis_parameters() -> PhysicsParameters | None:
    """
    Keep a single Film Analysis Parameters row (most recently updated).
    Remove any extras created before uniqueness was enforced.
    """
    params = list(
        PhysicsParameters.objects.filter(parameter_type='film_analysis').order_by('-updated_at', '-id')
    )
    if not params:
        return None
    keeper = params[0]
    for duplicate in params[1:]:
        duplicate.delete()
    return keeper


def get_field_size_detection_threshold() -> float:
    """Threshold ratio (0–1) for field-size edge detection along brightness profiles."""
    normalized = _normalize_threshold(
        _get_film_analysis_values().get('field_size_detection_threshold')
    )
    if normalized is not None:
        return normalized
    return DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD


def get_field_size_band_width_mm() -> float:
    """Total sampling band width in mm, centered on each radiation guide line."""
    normalized = _normalize_band_width_mm(
        _get_film_analysis_values().get('field_size_band_width_mm')
    )
    if normalized is not None:
        return normalized
    return DEFAULT_FIELD_SIZE_BAND_WIDTH_MM
