"""Centralized constants for film workflow filenames and cleanup patterns."""

FILM_UPLOAD_SUBDIR = 'film_uploads'
SESSION_LATEST_PATHS_KEY = 'latest_film_analysis_paths'

FIELD_SIZE_CROPPED_FILENAME = 'fieldsize_film_cropped.png'
COLLIMATOR_CROPPED_FILENAME = 'colli_film_cropped.png'
GANTRY_CROPPED_FILENAME = 'gantry_film_cropped.png'

FIELD_SIZE_ANALYSIS_KEY = 'fieldsize'
COLLIMATOR_ANALYSIS_KEY = 'collimator_isocenter'
GANTRY_ANALYSIS_KEY = 'gantry_isocenter'

# Raw upload artifacts + derived working images created during film workflow.
FILM_UPLOAD_CLEANUP_PATTERNS = [
    'Fieldsize_film.*',
    'Fieldsize_film_*.*',
    'Colli_film.*',
    'Colli_film_*.*',
    'Gantry_film.*',
    'Gantry_film_*.*',
    'fieldsize_film_cropped.*',
    'colli_film_cropped.*',
    'gantry_film_cropped.*',
    'radial_profile_graph.*',
    'fieldsize_analysis_result_*.png',
    'collimator_analysis_result_*.png',
    'gantry_analysis_result_*.png',
]
