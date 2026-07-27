"""
Film Analysis Views.

This module contains view functions for film upload and analysis:
- Field size analysis
- Collimator isocenter analysis
- Gantry isocenter analysis
- Image processing and edge detection
- DPI extraction and image manipulation

Uses NumPy and SciPy for image processing and mathematical operations.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from ..film_parameters_service import (
    band_width_mm_to_pixels,
    compute_station_line_count,
    get_field_size_band_width_mm,
    get_field_size_detection_threshold,
)
from ..film_constants import (
    COLLIMATOR_ANALYSIS_KEY,
    COLLIMATOR_CROPPED_FILENAME,
    FIELD_SIZE_ANALYSIS_KEY,
    FIELD_SIZE_CROPPED_FILENAME,
    FILM_UPLOAD_SUBDIR,
    GANTRY_ANALYSIS_KEY,
    GANTRY_CROPPED_FILENAME,
    SESSION_LATEST_PATHS_KEY,
)
from ..forms import FilmUploadForm
from ..models import FilmUpload
from ..services import ActivityService, QAService
from PIL import Image, ImageDraw, ImageFont
import os
import json
import logging
import uuid
import glob
import numpy as np
from scipy.ndimage import gaussian_filter1d
from datetime import datetime

logger = logging.getLogger(__name__)


def _clear_session_keys(request, *keys):
    """Remove transient film session keys if present."""
    for key in keys:
        request.session.pop(key, None)


def _drop_latest_analysis_path(request, analysis_key):
    """Remove a single analysis pointer from latest session paths."""
    latest_paths = request.session.get(SESSION_LATEST_PATHS_KEY, {})
    if isinstance(latest_paths, dict):
        latest_paths.pop(analysis_key, None)
        request.session[SESSION_LATEST_PATHS_KEY] = latest_paths


def _set_latest_analysis_path(request, analysis_key, path):
    """Persist latest analysis path for one film analysis type."""
    latest_paths = request.session.get(SESSION_LATEST_PATHS_KEY, {})
    if not isinstance(latest_paths, dict):
        latest_paths = {}
    latest_paths[analysis_key] = path
    request.session[SESSION_LATEST_PATHS_KEY] = latest_paths


def extract_dpi(image_file):
    """Extract DPI from image file"""
    try:
        img = Image.open(image_file)
        dpi = img.info.get('dpi', (0,))[0]
        # Convert to float to ensure JSON serializable
        if dpi:
            return float(dpi) if float(dpi) > 0 else None
        return None
    except Exception as e:
        logger.error(f"Error extracting DPI: {e}")
        return None

@require_POST
@login_required
def check_dpi(request):
    """Check DPI of uploaded image"""
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image = request.FILES['image']
            dpi = extract_dpi(image)
            return JsonResponse({'dpi': float(dpi) if dpi else None})
        except Exception as e:
            logger.error(f"Error checking DPI: {e}")
            return JsonResponse({'error': 'Error processing image'}, status=400)
    return JsonResponse({'error': 'No file'}, status=400)

@login_required
def upload_film(request):
    """Upload film image"""
    try:
        if request.method == 'POST':
            form = FilmUploadForm(request.POST, request.FILES)
            if form.is_valid():
                film = form.save(commit=False)
                film.uploaded_by = request.user
                uploaded_file = request.FILES['image']
                extracted_dpi = extract_dpi(uploaded_file)

                # Store the extracted DPI
                film.extracted_dpi = extracted_dpi

                if not extracted_dpi:
                    manual_dpi = form.cleaned_data.get('manual_dpi')
                    if not manual_dpi:
                        return JsonResponse({
                            'success': False,
                            'error': 'Could not extract DPI from image. Please enter DPI manually.'
                        }, status=400)
                    dpi = manual_dpi
                else:
                    dpi = extracted_dpi

                film.dpi = dpi

                # Remove old files
                FilmUpload.objects.filter(uploaded_by=request.user).delete()
                for name in [FIELD_SIZE_CROPPED_FILENAME]:
                    path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, name)
                    if os.path.exists(path):
                        os.remove(path)

                film.save()

                request.session['film_uploaded'] = True
                _clear_session_keys(request, 'lines_saved', 'film_cropped')
                _drop_latest_analysis_path(request, FIELD_SIZE_ANALYSIS_KEY)

                # Log activity
                ActivityService.log_activity(
                    user=request.user,
                    activity_type='film_upload',
                    description=f'Uploaded film image (DPI: {dpi})'
                )

                filename = os.path.basename(film.image.name)
                return JsonResponse({
                    'success': True,
                    'message': f'Field size film uploaded successfully (DPI: {dpi})',
                    'filename': filename,
                    'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}',
                    'dpi': float(dpi),
                })
            return JsonResponse({
                'success': False,
                'error': 'Invalid upload form data.',
                'form_errors': form.errors.get_json_data(),
            }, status=400)
        else:
            form = FilmUploadForm()
        
        return render(request, 'QAID_Manager/upload_film.html', {'form': form})
        
    except Exception as e:
        logger.error(f"Error in upload_film view: {e}")
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        messages.error(request, "An error occurred while uploading film.")
        return render(request, 'QAID_Manager/upload_film.html', {'form': FilmUploadForm()})

@require_POST
@login_required
def crop_fieldsize_film(request):
    """Crop fieldsize film"""
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        cropped_file = request.FILES.get('cropped_image')
        if not cropped_file:
            return JsonResponse({'success': False, 'error': 'No image received'})

        # Save to unique fixed path as PNG
        ext = 'png'
        target_path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, f'fieldsize_film_cropped.{ext}')

        if os.path.exists(target_path):
            os.remove(target_path)

        default_storage.save(f'{FILM_UPLOAD_SUBDIR}/fieldsize_film_cropped.{ext}', ContentFile(cropped_file.read()))

        # Invalidate previously saved line geometry after a new crop.
        film = FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        if film:
            film.temp_lines = {}
            film.save(update_fields=['temp_lines'])

        request.session['film_cropped'] = True
        _clear_session_keys(request, 'lines_saved')
        _drop_latest_analysis_path(request, FIELD_SIZE_ANALYSIS_KEY)
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error in crop_fieldsize_film view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def save_temp_lines(request):
    """Save temporary lines for film analysis"""
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            film = FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()

            if not film:
                return JsonResponse({'success': False, 'error': 'No uploaded film found.'})

            # Extract lines and image dimensions
            lines = data.get('lines', {})
            img_width = data.get('image_display_width')
            img_height = data.get('image_display_height')

            # Save all data into temp_lines
            full_data = {
                'radiation': lines.get('radiation', []),
                'light': lines.get('light', []),
                'image_display_width': img_width,
                'image_display_height': img_height
            }

            film.temp_lines = full_data
            film.save()

            request.session['lines_saved'] = True
            return JsonResponse({'success': True})

    except Exception as e:
        logger.error(f"Error in save_temp_lines view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method.'})

@require_POST
@login_required
def clear_temp_lines(request):
    """Clear temporary lines"""
    try:
        film = FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        if film:
            film.temp_lines = {}
            film.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Film not found.'})
    except Exception as e:
        logger.error(f"Error in clear_temp_lines view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def analyze_fieldsize(request):
    """Analyze field size from film"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        # 1. Load latest film uploaded by the current user
        film = FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        if not film or not film.temp_lines:
            return JsonResponse({'success': False, 'error': 'No TempLines data found for this session'})

        lines_data = film.temp_lines
        radiation_lines_raw = lines_data.get('radiation', [])
        light_lines_raw = lines_data.get('light', [])

        # 2. Load cropped film image
        cropped_pattern = os.path.join(settings.MEDIA_ROOT, 'film_uploads', 'fieldsize_film_cropped.*')
        matched_files = glob.glob(cropped_pattern)
        if not matched_files:
            return JsonResponse({'success': False, 'error': 'No cropped image found'})
        image_path = matched_files[0]

        original_img = Image.open(image_path)
        gray_img = original_img.convert('L')  # for analysis
        image_array = np.array(gray_img)
        overlay = original_img.convert('RGB')  # for drawing
        draw = ImageDraw.Draw(overlay)

        # 3. Scale coordinates to actual image size
        display_width = lines_data.get('image_display_width', original_img.width)
        display_height = lines_data.get('image_display_height', original_img.height)

        if not display_width or not display_height:
            return JsonResponse({'success': False, 'error': 'Invalid drawing canvas size. Please redraw lines and confirm.'})

        scale_x = original_img.width / display_width
        scale_y = original_img.height / display_height

        def scale_line_coords(line):
            return {
                'x1': int(line['x1'] * scale_x),
                'y1': int(line['y1'] * scale_y),
                'x2': int(line['x2'] * scale_x),
                'y2': int(line['y2'] * scale_y),
            }

        light_lines = [scale_line_coords(l) for l in light_lines_raw]
        radiation_guides = [scale_line_coords(r) for r in radiation_lines_raw]

        if len(light_lines) < 4 or len(radiation_guides) < 4:
            return JsonResponse({'success': False, 'error': 'Please define 4 light lines and 4 radiation guide lines before analysis.'})

        if len(light_lines) != len(radiation_guides):
            return JsonResponse({'success': False, 'error': 'Line count mismatch: number of light lines must equal radiation lines.'})

        # 4. Build light/guide models and rotate image to best-fit axis-aligned frame.
        light_line_models_raw = [build_line_model_from_segment(line) for line in light_lines]
        guide_line_models_raw = [build_line_model_from_segment(line) for line in radiation_guides]
        if any(m is None for m in light_line_models_raw) or any(m is None for m in guide_line_models_raw):
            return JsonResponse({'success': False, 'error': 'Invalid line geometry. Please redraw lines.'})

        rotation_angle_rad = compute_best_fit_axis_rotation(light_line_models_raw)
        rotation_angle_deg = float(np.degrees(rotation_angle_rad))
        image_center = np.array([original_img.width / 2.0, original_img.height / 2.0], dtype=float)

        background_fill = detect_background_mode_pixel(image_array)
        rotated_gray_img = gray_img.rotate(
            rotation_angle_deg,
            resample=Image.BICUBIC,
            expand=False,
            fillcolor=int(background_fill),
        )
        rotated_overlay = overlay.rotate(
            rotation_angle_deg,
            resample=Image.BICUBIC,
            expand=False,
            fillcolor=(int(background_fill), int(background_fill), int(background_fill)),
        )
        draw = ImageDraw.Draw(rotated_overlay)
        image_array = np.array(rotated_gray_img)

        light_lines_rot = [rotate_line_segment(line, image_center, rotation_angle_rad) for line in light_lines]
        radiation_guides_rot = [rotate_line_segment(line, image_center, rotation_angle_rad) for line in radiation_guides]

        light_line_models = [build_line_model_from_segment(line) for line in light_lines_rot]
        if any(m is None for m in light_line_models):
            return JsonResponse({'success': False, 'error': 'Invalid light line geometry. Please redraw lines.'})

        radiation_guide_models = [build_line_model_from_segment(line) for line in radiation_guides_rot]
        if any(m is None for m in radiation_guide_models):
            return JsonResponse({'success': False, 'error': 'Invalid radiation guide geometry. Please redraw guide lines.'})

        # Pair light lines with radiation guides before edge detection.
        guide_pairs = pair_line_sets(light_line_models, radiation_guide_models, image_center=image_center)
        if len(guide_pairs) != len(light_line_models):
            return JsonResponse({'success': False, 'error': 'Could not pair all lines reliably. Please redraw lines in matching order around the field.'})

        if not film or not film.dpi:
            return JsonResponse({'success': False, 'error': 'No DPI information found. Please upload the film with DPI information.'})

        film_dpi = max(75, min(1200, film.dpi))
        px_per_mm = film_dpi / 25.4
        band_width_mm = get_field_size_band_width_mm()
        band_width_px = band_width_mm_to_pixels(band_width_mm, film_dpi)
        station_line_count = compute_station_line_count(band_width_px)

        # Detect dominant background pixel value for mode-based correction.
        background_mode = detect_background_mode_pixel(image_array)
        field_size_edge_threshold = get_field_size_detection_threshold()

        radiation_models = []
        all_edge_points = []
        for light_idx, guide_idx in guide_pairs:
            light_model = light_line_models[light_idx]
            guide_line = radiation_guides_rot[guide_idx]
            model, edge_points = detect_radiation_border_line(
                image_array=image_array,
                guide_line=guide_line,
                reference_light_model=light_model,
                station_band_width_px=band_width_px,
                station_line_count=station_line_count,
                num_profiles=9,
                target_ratio=field_size_edge_threshold,
                background_mode=background_mode,
                mode_tolerance=3,
                retreat_px=50,
            )
            if model is None:
                return JsonResponse({'success': False, 'error': 'Failed to detect radiation border from one or more guide lines. Please redraw guide lines closer to field edges.'})
            radiation_models.append((light_idx, model))
            all_edge_points.extend(edge_points)

        # 5. Calculate side shifts from final rendered geometry:
        # for each light side, use the nearest same-side radiation line.
        image_center = np.array([rotated_overlay.width / 2.0, rotated_overlay.height / 2.0], dtype=float)
        shifts_by_side = {'left': [], 'right': [], 'top': [], 'bottom': []}
        radiation_only = [model for _, model in radiation_models]
        for light_model in light_line_models:
            side_key = classify_side_from_line(light_model, image_center)
            light_ang = line_angle_mod_pi(light_model)
            candidates = []
            for rad_model in radiation_only:
                if classify_side_from_line(rad_model, image_center) != side_key:
                    continue
                rad_ang = line_angle_mod_pi(rad_model)
                if angle_difference_mod_pi(light_ang, rad_ang) > np.deg2rad(25.0):
                    continue
                candidates.append(rad_model)

            # Fallback: if strict side+angle filter yields nothing, use all radiation
            # lines to avoid hard failure, but still choose nearest by geometry.
            if not candidates:
                candidates = radiation_only

            distances = [
                abs(signed_line_distance(light_model, rad_model['point']))
                for rad_model in candidates
            ]
            if distances:
                shifts_by_side[side_key].append(float(min(distances)))

        # Require all canonical sides to be present. Silent fallback can mask
        # wrong pairings (especially corner films) and corrupt match_mm.
        missing_sides = [side for side in ('left', 'right', 'top', 'bottom') if not shifts_by_side[side]]
        if missing_sides:
            return JsonResponse({
                'success': False,
                'error': f'Could not resolve all field sides reliably (missing: {", ".join(missing_sides)}). Please redraw lines closer to corresponding borders.',
            })

        # 7. Convert to mm
        shift_left = float(np.mean(shifts_by_side['left']) / px_per_mm)
        shift_right = float(np.mean(shifts_by_side['right']) / px_per_mm)
        shift_top = float(np.mean(shifts_by_side['top']) / px_per_mm)
        shift_bottom = float(np.mean(shifts_by_side['bottom']) / px_per_mm)

        # 8. Annotate text with improved font
        try:
            font_path = os.path.join(settings.BASE_DIR, 'arial.ttf')
            font = ImageFont.truetype(font_path, 32)  # Medium font
        except:
            font = ImageFont.load_default()

        # Draw light lines and detected radiation lines on overlay.
        for model in light_line_models:
            p1, p2 = project_line_to_image_bounds(model, rotated_overlay.width, rotated_overlay.height)
            if p1 and p2:
                draw.line([p1, p2], fill='green', width=2)

        for _, model in radiation_models:
            p1, p2 = project_line_to_image_bounds(model, rotated_overlay.width, rotated_overlay.height)
            if p1 and p2:
                draw.line([p1, p2], fill='red', width=2)

        # Draw detected edge points used for line fitting.
        for pt in all_edge_points:
            draw.ellipse((pt[0] - 2, pt[1] - 2, pt[0] + 2, pt[1] + 2), fill='yellow')

        draw.text((30, 30), f"A: {shift_left:.2f} mm", fill='blue', font=font)
        draw.text((30, 60), f"B: {shift_right:.2f} mm", fill='blue', font=font)
        draw.text((30, 90), f"G: {shift_top:.2f} mm", fill='blue', font=font)
        draw.text((30, 120), f"T: {shift_bottom:.2f} mm", fill='blue', font=font)
        draw.text((30, 150), f"Angle correction: {rotation_angle_deg:.2f}°", fill='blue', font=font)

        # Draw legend box in the bottom-left corner
        legend_x = 10
        legend_y = rotated_overlay.height - 100

        # White background for readability
        draw.rectangle([legend_x - 10, legend_y - 10, legend_x + 180, legend_y + 60], fill=(255, 255, 255, 220))

        # Draw colored squares
        draw.rectangle([legend_x, legend_y, legend_x + 30, legend_y + 30], fill='red')
        draw.text((legend_x + 35, legend_y), "Radiation Field", fill='black', font=font)

        draw.rectangle([legend_x, legend_y + 35, legend_x + 30, legend_y + 65], fill='green')
        draw.text((legend_x + 35, legend_y + 35), "Light Field", fill='black', font=font)

        # 9. Save result image with unique naming
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        result_filename = f'fieldsize_analysis_result_{timestamp}_{unique_id}.png'
        result_path = os.path.join(settings.MEDIA_ROOT, 'film_uploads', result_filename)
        rotated_overlay.save(result_path)

        _set_latest_analysis_path(request, FIELD_SIZE_ANALYSIS_KEY, result_path)

        max_shift = max(shift_left, shift_right, shift_top, shift_bottom)
        
        # Store the analysis result for automatic test input
        QAService.store_film_analysis_result('fieldsize', {
            'match_mm': max_shift,
            'shifts': {
                'left': shift_left,
                'right': shift_right,
                'top': shift_top,
                'bottom': shift_bottom,
            }
        })
        
        return JsonResponse({
            'success': True,
            'result_image_url': f'/media/film_uploads/{result_filename}',
            'match_mm': round(max_shift, 2),  # Send max shift only
            'shifts': {
                'left': round(shift_left, 2),
                'right': round(shift_right, 2),
                'top': round(shift_top, 2),
                'bottom': round(shift_bottom, 2),
            }
        })

    except Exception as e:
        logger.error(f"Error in field size analysis: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def upload_collimator_film(request):
    """Upload collimator film"""
    try:
        if request.method == 'POST':
            form = FilmUploadForm(request.POST, request.FILES)
            if form.is_valid():
                # Use CollimatorFilmUpload model for proper naming
                from QAID_Manager.models import CollimatorFilmUpload
                
                film = CollimatorFilmUpload()
                film.uploaded_by = request.user
                uploaded_file = request.FILES['image']
                extracted_dpi = extract_dpi(uploaded_file)

                # Store the extracted DPI
                film.extracted_dpi = extracted_dpi

                if not extracted_dpi:
                    manual_dpi = form.cleaned_data.get('manual_dpi')
                    if not manual_dpi:
                        return JsonResponse({
                            'success': False,
                            'error': 'Could not extract DPI from image. Please enter DPI manually.'
                        }, status=400)
                    dpi = manual_dpi
                else:
                    dpi = extracted_dpi

                film.dpi = dpi

                # Remove old collimator files
                CollimatorFilmUpload.objects.filter(uploaded_by=request.user).delete()
                for name in [COLLIMATOR_CROPPED_FILENAME]:
                    path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, name)
                    if os.path.exists(path):
                        os.remove(path)

                # Save the film with proper naming
                film.image = uploaded_file
                film.save()

                request.session['colli_uploaded'] = True
                _clear_session_keys(request, 'colli_cropped', 'colli_analysis_circle')
                _drop_latest_analysis_path(request, COLLIMATOR_ANALYSIS_KEY)

                # Log activity
                ActivityService.log_activity(
                    user=request.user,
                    activity_type='collimator_film_upload',
                    description=f'Uploaded collimator film image (DPI: {dpi})'
                )

                filename = os.path.basename(film.image.name)
                return JsonResponse({
                    'success': True,
                    'message': f'Collimator film uploaded successfully (DPI: {dpi})',
                    'filename': filename,
                    'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}',
                    'dpi': float(dpi),
                })
            return JsonResponse({
                'success': False,
                'error': 'Invalid upload form data.',
                'form_errors': form.errors.get_json_data(),
            }, status=400)
        else:
            form = FilmUploadForm()
        
        return render(request, 'QAID_Manager/upload_film.html', {'form': form})
        
    except Exception as e:
        logger.error(f"Error in upload_collimator_film view: {e}")
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        messages.error(request, "An error occurred while uploading film.")
        return render(request, 'QAID_Manager/upload_film.html', {'form': FilmUploadForm()})

@require_POST
@login_required
def crop_collimator_film(request):
    """Crop collimator film"""
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        cropped_file = request.FILES.get('cropped_image')
        if not cropped_file:
            return JsonResponse({'success': False, 'error': 'No image received'})

        # Save to unique fixed path as PNG
        ext = 'png'
        target_path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, f'colli_film_cropped.{ext}')

        if os.path.exists(target_path):
            os.remove(target_path)

        default_storage.save(f'{FILM_UPLOAD_SUBDIR}/colli_film_cropped.{ext}', ContentFile(cropped_file.read()))

        request.session['colli_cropped'] = True
        _clear_session_keys(request, 'colli_analysis_circle')
        _drop_latest_analysis_path(request, COLLIMATOR_ANALYSIS_KEY)
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error in crop_collimator_film view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})



@require_POST
@login_required
def analyze_collimator(request):
    """Analyze collimator isocenter using the user-defined circle"""
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        # Get the analysis circle from session
        circle_data = request.session.get('colli_analysis_circle')
        if not circle_data:
            return JsonResponse({'success': False, 'error': 'Analysis circle not defined. Please define a circle first.'})
        
        # Get film image path
        film_path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, COLLIMATOR_CROPPED_FILENAME)
        if not os.path.exists(film_path):
            return JsonResponse({'success': False, 'error': 'Collimator film image not found. Please upload and crop the film first.'})
        
        # Load image
        img = Image.open(film_path).convert('L')  # Convert to grayscale
        img_rgb = Image.open(film_path).convert('RGB')  # For drawing
        img_array = np.array(img)
        draw = ImageDraw.Draw(img_rgb)
        
        # Extract circle parameters (already scaled by JavaScript)
        center_x = int(circle_data['center_x'])
        center_y = int(circle_data['center_y'])
        user_radius = int(circle_data['radius'])
        
        # Get pixel size information for displacement calculations
        image_actual_width = circle_data.get('image_actual_width', img_array.shape[1])
        image_actual_height = circle_data.get('image_actual_height', img_array.shape[0])
        
        # Calculate pixels per mm using the film's actual DPI
        # Get the film's DPI from the uploaded film
        from QAID_Manager.models import CollimatorFilmUpload
        film = CollimatorFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        
        if not film or not film.dpi:
            return JsonResponse({'success': False, 'error': 'No DPI information found. Please upload the film with DPI information.'})
        
        film_dpi = film.dpi
        
        # Ensure DPI is within reasonable bounds (75 to 1200)
        film_dpi = max(75, min(1200, film_dpi))
        
        # Calculate pixels per mm using the film's DPI
        px_per_mm = film_dpi / 25.4  # Convert DPI to pixels per mm
        
        print(f"Film DPI: {film_dpi}")
        print(f"Pixels per mm: {px_per_mm:.2f}")
        print(f"Image dimensions: {image_actual_width}x{image_actual_height} pixels")
        print(f"Calculated film size: {image_actual_width/px_per_mm:.1f}x{image_actual_height/px_per_mm:.1f} mm")
        
        # Extract profile along the user-defined circle
        bands, debug_text, graph_path = extract_radial_bands(img_array, center_x, center_y, user_radius)
        
        if len(bands) < 6:
            return JsonResponse({'success': False, 'error': f'Expected at least 6 radiation bands, found {len(bands)}. Please check the circle position.'})
        
        # Group and refine bands
        refined_bands = group_and_refine_bands(bands, center_x, center_y)
        
        # Find opposite band pairs and calculate central lines
        central_lines = calculate_central_lines(refined_bands, center_x, center_y)
        
        # Find intersections of central lines
        intersections = find_line_intersections(central_lines)
        
        if not intersections:
            # Try to use band centers as fallback
            if refined_bands:
                # Use the center of the bands as radiation isocenter
                rad_iso_x = np.mean([band['x'] for band in refined_bands])
                rad_iso_y = np.mean([band['y'] for band in refined_bands])
                circle_diameter = 0
            else:
                return JsonResponse({'success': False, 'error': 'Could not find intersections of central lines and no bands available for fallback.'})
        else:
            # Calculate radiation isocenter as center of minimum enclosing circle
            if len(intersections) >= 2:
                rad_iso_x, rad_iso_y, circle_diameter = calculate_minimum_enclosing_circle(intersections)
            else:
                # Fallback to average if not enough intersections
                rad_iso_x = np.mean([p[0] for p in intersections])
                rad_iso_y = np.mean([p[1] for p in intersections])
                circle_diameter = 0
        
        # Calculate displacement from mechanical center
        mech_center_x = center_x
        mech_center_y = center_y
        
        displacement_x = rad_iso_x - mech_center_x
        displacement_y = rad_iso_y - mech_center_y
        total_displacement = np.sqrt(displacement_x**2 + displacement_y**2)
        
        # Convert to mm
        displacement_mm = total_displacement / px_per_mm
        circle_diameter_mm = circle_diameter / px_per_mm
        
        # Draw results on image
        draw_analysis_results(draw, center_x, center_y, user_radius, refined_bands, 
                            central_lines, intersections, rad_iso_x, rad_iso_y, 
                            mech_center_x, mech_center_y, circle_diameter, px_per_mm, film_dpi, film.extracted_dpi)
        
        # Save result image with unique naming
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        result_filename = f'collimator_analysis_result_{timestamp}_{unique_id}.png'
        result_path = os.path.join(settings.MEDIA_ROOT, 'film_uploads', result_filename)
        img_rgb.save(result_path)

        _set_latest_analysis_path(request, COLLIMATOR_ANALYSIS_KEY, result_path)
        
        # Check tolerance (circle diameter < 1.0mm)
        is_acceptable = circle_diameter_mm < 1.0
        
        # Store the analysis result for automatic test input
        QAService.store_film_analysis_result('collimator_isocenter', {
            'displacement_mm': displacement_mm,
            'circle_diameter_mm': circle_diameter_mm,
            'is_acceptable': is_acceptable,
            'radiation_isocenter': [rad_iso_x, rad_iso_y],
            'mechanical_center': [mech_center_x, mech_center_y]
        })
        
        return JsonResponse({
            'success': True,
            'result_image_url': f'/media/film_uploads/{result_filename}',
            'profile_graph_url': '/media/film_uploads/radial_profile_graph.png',
            'displacement_mm': float(round(displacement_mm, 2)),
            'circle_diameter_mm': float(round(circle_diameter_mm, 2)),
            'is_acceptable': bool(is_acceptable),
            'radiation_isocenter': [float(round(rad_iso_x, 1)), float(round(rad_iso_y, 1))],
            'mechanical_center': [float(mech_center_x), float(mech_center_y)]
        })
        
    except Exception as e:
        logger.error(f"Error in collimator analysis: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Analysis failed: {str(e)}'})



def extract_radial_bands(image_array, center_x, center_y, radius):
    """Extract radiation bands along a specific circle using circular profile"""
    # Extract circular profile around the circle
    # Start at 0° and go to 420° (360° + 60°) to avoid splitting peaks at 0°
    start_angle = 0  # Start at 0° 
    end_angle = 2 * np.pi + np.pi / 3  # 420 degrees (360° + 60°)
    num_points = int((2 * np.pi + np.pi / 3) * radius * 0.5)  # Sample every 0.5 pixels along circumference
    
    angles = np.linspace(start_angle, end_angle, num_points, endpoint=False)
    profile = []
    angle_list = []
    
    for angle in angles:
        x = int(center_x + radius * np.cos(angle))
        y = int(center_y + radius * np.sin(angle))
        
        # Ensure coordinates are within image bounds
        x = max(0, min(x, image_array.shape[1] - 1))
        y = max(0, min(y, image_array.shape[0] - 1))
        
        profile.append(image_array[y, x])
        angle_list.append(angle)
    
    # Detect bands in the circular profile
    bands, debug_text, filtered_valleys = detect_bands_in_circular_profile(profile, angle_list, center_x, center_y, radius)
    
    # Create visual graph using filtered valleys
    graph_path = create_radial_profile_graph(profile, angle_list, filtered_valleys, radius, center_x, center_y)
    
    return bands, debug_text, graph_path

def create_radial_profile_graph(profile, angles, valleys, radius, center_x, center_y):
    """Create a visual graph of the radial profile using PIL"""
    # Create a larger graph image for better visibility
    graph_width = 1000
    graph_height = 600
    margin = 60
    
    # Create image with light background
    img = Image.new('RGB', (graph_width, graph_height), '#f8f9fa')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Calculate plot area
    plot_width = graph_width - 2 * margin
    plot_height = graph_height - 2 * margin
    
    # Normalize profile data for plotting
    profile_min = min(profile)
    profile_max = max(profile)
    profile_range = profile_max - profile_min
    
    if profile_range == 0:
        profile_range = 1
    
    # Convert angles to degrees for x-axis
    angles_deg = [np.degrees(angle) for angle in angles]
    
    # Create smoothed profile for comparison
    smoothed = gaussian_filter1d(profile, sigma=2.0)
    
    # Draw title with better styling
    title = f"Radial Profile Analysis - Radius: {radius}px (420° Profile)"
    subtitle = f"Center: ({center_x}, {center_y}) | Profile Length: {len(profile)} points"
    
    # Draw title background
    draw.rectangle([(margin, 10), (graph_width - margin, 50)], fill='#e3f2fd', outline='#2196f3')
    draw.text((margin + 10, 15), title, fill='#1565c0', font=font)
    draw.text((margin + 10, 35), subtitle, fill='#1976d2', font=font)
    
    # Draw axes with better styling
    # X-axis (angles)
    draw.line([(margin, graph_height - margin), (graph_width - margin, graph_height - margin)], fill='#424242', width=3)
    # Y-axis (intensity)
    draw.line([(margin, margin), (margin, graph_height - margin)], fill='#424242', width=3)
    
    # Draw axis labels with better positioning
    draw.text((graph_width // 2 - 50, graph_height - margin + 10), "Angle (degrees)", fill='#424242', font=font)
    draw.text((margin - 40, graph_height // 2 - 20), "Intensity", fill='#424242', font=font)
    
    # Draw grid lines with better styling
    # Vertical lines (every 45 degrees, extended to 420 degrees)
    for i in range(0, 421, 45):
        x = margin + (i / 420) * plot_width
        draw.line([(x, margin), (x, graph_height - margin)], fill='#e0e0e0', width=1)
        # Add angle labels
        draw.text((x - 15, graph_height - margin + 15), f"{i}°", fill='#666', font=font)
    
    # Horizontal lines (intensity levels)
    for i in range(6):
        y = margin + (i / 5) * plot_height
        intensity = profile_max - (i / 5) * profile_range
        draw.line([(margin, y), (graph_width - margin, y)], fill='#e0e0e0', width=1)
        draw.text((margin - 45, y - 5), f"{intensity:.0f}", fill='#666', font=font)
    
    # Plot the raw profile data
    raw_points = []
    for i, (angle_deg, intensity) in enumerate(zip(angles_deg, profile)):
        x = margin + (angle_deg / 420) * plot_width
        y = margin + ((profile_max - intensity) / profile_range) * plot_height
        raw_points.append((x, y))
    
    # Draw the raw profile line with transparency
    if len(raw_points) > 1:
        # Draw raw profile in light blue
        draw.line(raw_points, fill='#90caf9', width=1)
    
    # Plot the smoothed profile data
    smooth_points = []
    for i, (angle_deg, intensity) in enumerate(zip(angles_deg, smoothed)):
        x = margin + (angle_deg / 420) * plot_width
        y = margin + ((profile_max - intensity) / profile_range) * plot_height
        smooth_points.append((x, y))
    
    # Draw the smoothed profile line (main line)
    if len(smooth_points) > 1:
        draw.line(smooth_points, fill='#1976d2', width=3)
    
    # Draw mean intensity line
    max_intensity = max(smoothed)
    min_intensity = min(smoothed)
    mean_intensity = min_intensity + (max_intensity - min_intensity) / 2
    
    # Calculate y position for mean intensity line
    mean_y = margin + ((profile_max - mean_intensity) / profile_range) * plot_height
    
    # Draw mean intensity line across the entire plot (dashed effect)
    line_start = margin
    line_end = graph_width - margin
    dash_length = 8
    gap_length = 4
    
    x = line_start
    while x < line_end:
        dash_end = min(x + dash_length, line_end)
        draw.line([(x, mean_y), (dash_end, mean_y)], fill='#ff9800', width=2)
        x = dash_end + gap_length
    
    # Add mean intensity label
    mean_label = f"Mean Intensity: {mean_intensity:.1f}"
    draw.text((margin + 10, mean_y - 20), mean_label, fill='#ff9800', font=font)
    
    # Mark detected valleys with better styling
    for i, valley_idx in enumerate(valleys):
        angle_deg = angles_deg[valley_idx]
        intensity = smoothed[valley_idx]
        x = margin + (angle_deg / 420) * plot_width
        y = margin + ((profile_max - intensity) / profile_range) * plot_height
        
        # Draw valley marker with better styling
        # Outer circle
        draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill='#ff5722', outline='#d84315', width=2)
        # Inner circle
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill='#ffffff')
        
        # Add valley label with background
        valley_text = f"V{i+1}"
        text_bbox = draw.textbbox((0, 0), valley_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # Draw label background
        label_x = x + 12
        label_y = y - text_height - 5
        draw.rectangle([(label_x - 2, label_y - 2), (label_x + text_width + 2, label_y + text_height + 2)], 
                      fill='#ff5722', outline='#d84315')
        draw.text((label_x, label_y), valley_text, fill='white', font=font)
        
        # Add angle annotation
        angle_text = f"{angle_deg:.1f}°"
        draw.text((label_x, label_y + text_height + 5), angle_text, fill='#d84315', font=font)
    
    # Add statistics panel
    stats_panel_x = graph_width - margin - 200
    stats_panel_y = margin + 10
    stats_panel_width = 190
    stats_panel_height = 120
    
    # Draw statistics background
    draw.rectangle([(stats_panel_x, stats_panel_y), 
                   (stats_panel_x + stats_panel_width, stats_panel_y + stats_panel_height)], 
                  fill='#f3e5f5', outline='#9c27b0')
    
    # Add statistics text
    stats_lines = [
        f"Profile Length: {len(profile)}",
        f"Detected Valleys: {len(valleys)}",
        f"Intensity Range: {profile_min:.1f}-{profile_max:.1f}",
        f"Mean Intensity: {sum(profile)/len(profile):.1f}",
        f"Std Deviation: {np.std(profile):.1f}",
        f"Analysis Radius: {radius}px"
    ]
    
    for i, line in enumerate(stats_lines):
        y_pos = stats_panel_y + 10 + i * 18
        draw.text((stats_panel_x + 5, y_pos), line, fill='#4a148c', font=font)
    
    # Add legend
    legend_x = margin
    legend_y = margin + 10
    legend_width = 200
    legend_height = 80
    
    # Draw legend background
    draw.rectangle([(legend_x, legend_y), 
                   (legend_x + legend_width, legend_y + legend_height)], 
                  fill='#e8f5e8', outline='#4caf50')
    
    # Add legend items
    legend_items = [
        ("Raw Profile", '#90caf9'),
        ("Smoothed Profile", '#1976d2'),
        ("Mean Intensity", '#ff9800'),
        ("Detected Valleys", '#ff5722')
    ]
    
    for i, (label, color) in enumerate(legend_items):
        y_pos = legend_y + 10 + i * 20
        # Draw color indicator
        if i < 3:  # Lines (raw, smoothed, mean intensity)
            if i == 2:  # Mean intensity line (dashed)
                # Draw dashed line for legend
                legend_line_start = legend_x + 5
                legend_line_end = legend_x + 25
                dash_length = 3
                gap_length = 2
                x = legend_line_start
                while x < legend_line_end:
                    dash_end = min(x + dash_length, legend_line_end)
                    draw.line([(x, y_pos + 8), (dash_end, y_pos + 8)], fill=color, width=2)
                    x = dash_end + gap_length
            else:  # Solid lines
                draw.line([(legend_x + 5, y_pos + 8), (legend_x + 25, y_pos + 8)], fill=color, width=3)
        else:  # Circle for valleys
            draw.ellipse([(legend_x + 5, y_pos + 2), (legend_x + 21, y_pos + 18)], fill=color)
        
        draw.text((legend_x + 30, y_pos), label, fill='#2e7d32', font=font)
    
    # Add analysis circle visualization
    circle_viz_x = graph_width - margin - 150
    circle_viz_y = margin + 150
    circle_viz_size = 120
    
    # Draw circle background
    draw.ellipse([(circle_viz_x, circle_viz_y), 
                  (circle_viz_x + circle_viz_size, circle_viz_y + circle_viz_size)], 
                 fill='#fff3e0', outline='#ff9800', width=2)
    
    # Draw center point
    center_x_viz = circle_viz_x + circle_viz_size // 2
    center_y_viz = circle_viz_y + circle_viz_size // 2
    draw.ellipse([(center_x_viz - 3, center_y_viz - 3), 
                  (center_x_viz + 3, center_y_viz + 3)], fill='#ff9800')
    
    # Draw valley positions on the circle
    for i, valley_idx in enumerate(valleys):
        angle = angles[valley_idx]
        # Scale angle to circle visualization
        viz_radius = circle_viz_size // 2 - 10
        viz_x = center_x_viz + viz_radius * np.cos(angle)
        viz_y = center_y_viz + viz_radius * np.sin(angle)
        
        draw.ellipse([(viz_x - 4, viz_y - 4), (viz_x + 4, viz_y + 4)], 
                    fill='#ff5722', outline='#d84315')
    
    # Add circle label
    draw.text((circle_viz_x, circle_viz_y + circle_viz_size + 5), 
              f"Analysis Circle (R={radius}px)", fill='#e65100', font=font)
    
    # Save the graph
    graph_path = os.path.join(settings.MEDIA_ROOT, 'film_uploads', 'radial_profile_graph.png')
    img.save(graph_path)
    
    return graph_path

def filter_valleys_by_expected_angles(valleys, angles, expected_angles_deg, tolerance_deg=15):
    """Filter valleys to only keep those near expected angles for starshot pattern"""
    # Expected angles for 8-pointed star pattern (in degrees)
    # These are the main radiation bands we want to detect
    expected_angles_rad = [np.radians(angle) for angle in expected_angles_deg]
    tolerance_rad = np.radians(tolerance_deg)
    
    filtered_valleys = []
    filtered_angles = []
    
    for valley_idx in valleys:
        valley_angle = angles[valley_idx]
        valley_angle_deg = np.degrees(valley_angle)
        
        # Find the closest expected angle
        min_distance = float('inf')
        closest_expected = None
        
        for expected_angle in expected_angles_rad:
            # Calculate angular distance
            angle_diff = abs(valley_angle - expected_angle)
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            
            if angle_diff < min_distance:
                min_distance = angle_diff
                closest_expected = expected_angle
        
        # Check if this valley is close enough to an expected angle
        if min_distance <= tolerance_rad:
            filtered_valleys.append(valley_idx)
            filtered_angles.append(valley_angle)
    
    return filtered_valleys, filtered_angles

def detect_bands_in_circular_profile(profile, angles, center_x, center_y, radius):
    """Detect bands in circular profile using simplified intensity-based method"""
    # Smooth profile to reduce noise
    smoothed = gaussian_filter1d(profile, sigma=2.0)
    
    # Use the simplified intensity-based method
    valleys = find_valleys_by_intensity_threshold(smoothed)
    
    # Filter valleys to expected angles for starshot pattern
    # Expected angles for 8-pointed star (45° intervals starting from 0°)
    expected_angles_deg = [0, 45, 90, 135, 180, 225, 270, 315]
    filtered_valleys, filtered_angles = filter_valleys_by_expected_angles(valleys, angles, expected_angles_deg, tolerance_deg=20)
    
    # If we don't have enough filtered valleys, try with more tolerance
    if len(filtered_valleys) < 6:
        filtered_valleys, filtered_angles = filter_valleys_by_expected_angles(valleys, angles, expected_angles_deg, tolerance_deg=30)
    
    bands = []
    for i, valley_idx in enumerate(filtered_valleys):
        # Convert profile index to angle
        angle = angles[valley_idx]
        
        # Convert to image coordinates
        band_x = center_x + radius * np.cos(angle)
        band_y = center_y + radius * np.sin(angle)
        
        # Calculate band depth (strength)
        band_depth = np.max(smoothed) - smoothed[valley_idx]
        
        bands.append({
            'x': band_x,
            'y': band_y,
            'angle': angle,
            'depth': band_depth,
            'radius': radius
        })
    
    return bands, "", filtered_valleys

def group_and_refine_bands(all_bands, center_x, center_y):
    """Group nearby bands and refine their positions"""
    if not all_bands:
        return []
    
    # Group bands that are close to each other (likely same radiation band)
    grouped_bands = []
    used_bands = set()
    
    for i, band1 in enumerate(all_bands):
        if i in used_bands:
            continue
        
        # Find all bands close to this one
        group = [band1]
        used_bands.add(i)
        
        for j, band2 in enumerate(all_bands):
            if j in used_bands:
                continue
            
            # Calculate angular distance between bands
            angle_diff = abs(band2['angle'] - band1['angle'])
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            
            # Group bands that are within 30 degrees of each other
            if angle_diff < np.radians(30):
                group.append(band2)
                used_bands.add(j)
        
        # Calculate refined position (weighted by depth)
        if len(group) > 1:
            total_depth = sum(band['depth'] for band in group)
            refined_x = sum(band['x'] * band['depth'] for band in group) / total_depth
            refined_y = sum(band['y'] * band['depth'] for band in group) / total_depth
            refined_angle = sum(band['angle'] * band['depth'] for band in group) / total_depth
        else:
            refined_x = group[0]['x']
            refined_y = group[0]['y']
            refined_angle = group[0]['angle']
        
        # Normalize angle to [0, 2π]
        if refined_angle < 0:
            refined_angle += 2 * np.pi
        
        grouped_bands.append({
            'x': refined_x,
            'y': refined_y,
            'angle': refined_angle,
            'depth': sum(band['depth'] for band in group)
        })
    
    # Sort by angle for consistent ordering
    grouped_bands.sort(key=lambda b: b['angle'])
    
    # Limit to top 8 bands by depth (expected for starshot pattern)
    if len(grouped_bands) > 8:
        grouped_bands.sort(key=lambda b: b['depth'], reverse=True)
        grouped_bands = grouped_bands[:8]
        # Re-sort by angle
        grouped_bands.sort(key=lambda b: b['angle'])
    
    return grouped_bands

def calculate_central_lines(bands, center_x, center_y):
    """Calculate central lines by connecting opposite bands"""
    if len(bands) < 4:
        return []
    
    # Sort bands by angle
    sorted_bands = sorted(bands, key=lambda b: b['angle'])
    
    central_lines = []
    used_bands = set()
    
    for i, band1 in enumerate(sorted_bands):
        if i in used_bands:
            continue
        
        # Find the band closest to 180° opposite
        best_opposite_idx = None
        min_angle_diff = float('inf')
        
        for j, band2 in enumerate(sorted_bands):
            if j == i or j in used_bands:
                continue
            
            angle_diff = abs(band2['angle'] - band1['angle'])
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            
            # Check if this is closer to 180° (π radians)
            if abs(angle_diff - np.pi) < min_angle_diff:
                min_angle_diff = abs(angle_diff - np.pi)
                best_opposite_idx = j
        
        if best_opposite_idx is not None:
            band2 = sorted_bands[best_opposite_idx]
            central_lines.append((band1, band2))
            used_bands.add(i)
            used_bands.add(best_opposite_idx)
    
    # If we don't have enough central lines, try to create additional lines
    if len(central_lines) < 2 and len(bands) >= 4:
        # Try to connect remaining bands to center
        remaining_bands = [b for i, b in enumerate(sorted_bands) if i not in used_bands]
        
        for band in remaining_bands[:2]:  # Use up to 2 remaining bands
            # Create a line from band to center
            center_band = {
                'x': center_x,
                'y': center_y,
                'angle': 0,  # Dummy angle
                'depth': 0
            }
            central_lines.append((band, center_band))
    
    return central_lines

def find_line_intersections(central_lines):
    """Find intersections of central lines"""
    intersections = []
    
    if len(central_lines) < 2:
        return intersections
    
    for i, line1 in enumerate(central_lines):
        for j, line2 in enumerate(central_lines[i+1:], i+1):
            intersection = calculate_line_intersection(line1, line2)
            if intersection is not None:
                intersections.append(intersection)
    
    return intersections

def calculate_line_intersection(line1, line2):
    """Calculate intersection point of two lines"""
    # Extract points from lines
    p1, p2 = line1[0], line1[1]  # First line: (x1,y1) to (x2,y2)
    p3, p4 = line2[0], line2[1]  # Second line: (x3,y3) to (x4,y4)
    
    # Line 1: (x1,y1) to (x2,y2)
    x1, y1 = p1['x'], p1['y']
    x2, y2 = p2['x'], p2['y']
    
    # Line 2: (x3,y3) to (x4,y4)
    x3, y3 = p3['x'], p3['y']
    x4, y4 = p4['x'], p4['y']
    
    # Calculate intersection using parametric line equations
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    if abs(denominator) < 1e-10:  # Lines are parallel
        return None
    
    # Calculate intersection point
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
    
    intersection_x = x1 + t * (x2 - x1)
    intersection_y = y1 + t * (y2 - y1)
    
    return (intersection_x, intersection_y)

def draw_analysis_results(draw, center_x, center_y, user_radius, bands, central_lines, 
                         intersections, rad_iso_x, rad_iso_y, mech_center_x, mech_center_y, circle_diameter, px_per_mm, film_dpi=None, extracted_dpi=None):
    """Draw analysis results on the image"""
    try:
        font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw detected bands (green dots)
    for band in bands:
        draw.ellipse([band['x'] - 2, band['y'] - 2, 
                     band['x'] + 2, band['y'] + 2], 
                    fill='green', outline='green')
    
    # Draw central lines
    for i, line in enumerate(central_lines):
        p1, p2 = line[0], line[1]
        draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], 
                 fill='red', width=1)
    
    # Draw minimum enclosing circle
    if circle_diameter > 0:
        circle_radius = circle_diameter / 2
        draw.ellipse([rad_iso_x - circle_radius, rad_iso_y - circle_radius,
                     rad_iso_x + circle_radius, rad_iso_y + circle_radius],
                    outline='orange', width=1)
    
    # Draw radiation isocenter (red dot)
    draw.ellipse([rad_iso_x - 2, rad_iso_y - 2, 
                 rad_iso_x + 2, rad_iso_y + 2], 
                fill='red', outline='red')
    
    # Draw mechanical center (blue dot)
    draw.ellipse([mech_center_x - 2, mech_center_y - 2, 
                 mech_center_x + 2, mech_center_y + 2], 
                fill='blue', outline='blue')
    
    # Calculate displacement and circle diameter in mm
    displacement_x = rad_iso_x - mech_center_x
    displacement_y = rad_iso_y - mech_center_y
    total_displacement = np.sqrt(displacement_x**2 + displacement_y**2)
    
    # Convert measurements to mm using the correct scaling factor passed from main analysis
    displacement_mm = total_displacement / px_per_mm
    circle_diameter_mm = circle_diameter / px_per_mm
    
    # Create appropriate font size for annotations
    try:
        # Try to use a smaller font if available
        large_font = ImageFont.truetype("arial.ttf", 16)
    except:
        try:
            # Try alternative font
            large_font = ImageFont.truetype("arialbd.ttf", 16)
        except:
            # Fallback to default font
            large_font = ImageFont.load_default()
    
    # Add text annotations with larger font
    draw.text((10, 10), f"Radiation Iso: ({rad_iso_x:.1f}, {rad_iso_y:.1f})", fill='red', font=large_font)
    draw.text((10, 40), f"Mech Center: ({mech_center_x:.1f}, {mech_center_y:.1f})", fill='blue', font=large_font)
    draw.text((10, 70), f"Displacement: {displacement_mm:.2f} mm", fill='purple', font=large_font)
    draw.text((10, 100), f"Enclosed Circle Diameter: {circle_diameter_mm:.2f} mm", fill='orange', font=large_font)
    

    


def calculate_minimum_enclosing_circle(points):
    """
    Calculate the center and diameter of the minimum enclosing circle for a set of points.
    Uses a simple algorithm to find the center that minimizes the maximum distance to any point.
    """
    if not points:
        return 0, 0, 0
    
    if len(points) == 1:
        return float(points[0][0]), float(points[0][1]), 0
    
    # For 2 points, the center is the midpoint
    if len(points) == 2:
        center_x = (points[0][0] + points[1][0]) / 2
        center_y = (points[0][1] + points[1][1]) / 2
        radius = np.sqrt((points[0][0] - points[1][0])**2 + (points[0][1] - points[1][1])**2) / 2
        diameter = 2 * radius
        return float(center_x), float(center_y), float(diameter)
    
    # For 3 or more points, use iterative approach
    # Start with the center of mass
    center_x = np.mean([p[0] for p in points])
    center_y = np.mean([p[1] for p in points])
    
    # Validate initial center
    if not (np.isfinite(center_x) and np.isfinite(center_y)):
        center_x, center_y = points[0][0], points[0][1]
    
    # Iteratively adjust the center to minimize the maximum distance
    max_iterations = 20  # More iterations for better convergence
    tolerance = 0.01
    
    for iteration in range(max_iterations):
        # Find the point farthest from current center
        max_distance = 0
        farthest_point = points[0]
        
        for point in points:
            distance = np.sqrt((point[0] - center_x)**2 + (point[1] - center_y)**2)
            if distance > max_distance:
                max_distance = distance
                farthest_point = point
        
        # Move center towards the farthest point (smaller step for stability)
        new_center_x = center_x + 0.3 * (farthest_point[0] - center_x)
        new_center_y = center_y + 0.3 * (farthest_point[1] - center_y)
        
        # Validate new center
        if not (np.isfinite(new_center_x) and np.isfinite(new_center_y)):
            break
        
        # Check convergence
        if abs(new_center_x - center_x) < tolerance and abs(new_center_y - center_y) < tolerance:
            break
            
        center_x, center_y = new_center_x, new_center_y
    
    # Validate final center
    if not (np.isfinite(center_x) and np.isfinite(center_y)):
        center_x = np.mean([p[0] for p in points])
        center_y = np.mean([p[1] for p in points])
    
    # Calculate final radius as maximum distance to any point
    radius = 0
    for point in points:
        distance = np.sqrt((point[0] - center_x)**2 + (point[1] - center_y)**2)
        radius = max(radius, distance)
    
    diameter = 2 * radius
    
    # Validate final results
    if not (np.isfinite(center_x) and np.isfinite(center_y) and np.isfinite(diameter)):
        center_x, center_y = points[0][0], points[0][1]
        diameter = 0
    
    return float(center_x), float(center_y), float(diameter) 

@require_POST
@login_required
def set_collimator_center(request):
    """Set collimator analysis circle"""
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            
            # Extract circle data
            center_x = float(data.get('center_x', 0))
            center_y = float(data.get('center_y', 0))
            radius = float(data.get('radius', 0))
            
            # Extract pixel size information for displacement calculations
            image_display_width = data.get('image_display_width', 0)
            image_display_height = data.get('image_display_height', 0)
            image_actual_width = data.get('image_actual_width', 0)
            image_actual_height = data.get('image_actual_height', 0)
            scale_x = data.get('scale_x', 1.0)
            scale_y = data.get('scale_y', 1.0)
            
            # Validate circle data
            if radius <= 0:
                return JsonResponse({'success': False, 'error': 'Invalid circle radius'})
            
            # Store circle data and pixel size information in session
            request.session['colli_analysis_circle'] = {
                'center_x': center_x,
                'center_y': center_y,
                'radius': radius,
                'image_display_width': image_display_width,
                'image_display_height': image_display_height,
                'image_actual_width': image_actual_width,
                'image_actual_height': image_actual_height,
                'scale_x': scale_x,
                'scale_y': scale_y
            }
            
            logger.info(f"Collimator analysis circle set: center=({center_x}, {center_y}), radius={radius}")
            logger.info(f"Image size: display=({image_display_width}x{image_display_height}), actual=({image_actual_width}x{image_actual_height})")
            return JsonResponse({'success': True})
            
    except Exception as e:
        logger.error(f"Error in set_collimator_center view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}) 



def find_valleys_by_intensity_threshold(profile):
    """
    Find valleys using the simplified intensity-based method:
    1. Find maximum and minimum intensity of the radial profile
    2. Calculate mean intensity = min + (max - min) / 2
    3. Find nearest points to mean intensity
    4. Determine if each point is up gradient or down gradient
    5. Find valleys as midpoints between adjacent up and down gradient points
    6. Filter out valleys where crossing points are too close (< 10 degrees)
    """
    profile_len = len(profile)
    valleys = []
    
    # 1. Find maximum and minimum intensity
    max_intensity = max(profile)
    min_intensity = min(profile)
    mean_intensity = min_intensity + (max_intensity - min_intensity) / 2
    
    # 2. Scan from angle 0 to end, detect both types of threshold crossings
    crossing_points = []
    threshold = mean_intensity
    was_below_threshold = True  # Start assuming we're below threshold
    
    for i in range(len(profile)):
        is_above_threshold = profile[i] >= threshold
        
        # Detect crossing from below to above threshold
        if was_below_threshold and is_above_threshold:
            # Found a crossing from below to above, add this point
            crossing_points.append({
                'index': i,
                'intensity': profile[i],
                'distance_from_mean': abs(profile[i] - mean_intensity),
                'crossing_type': 'below_to_above'
            })
        
        # Detect crossing from above to below threshold
        elif not was_below_threshold and not is_above_threshold:
            # Found a crossing from above to below, add this point
            crossing_points.append({
                'index': i,
                'intensity': profile[i],
                'distance_from_mean': abs(profile[i] - mean_intensity),
                'crossing_type': 'above_to_below'
            })
        
        was_below_threshold = not is_above_threshold
    
    # 3. Find FWHM pairs: above→below followed by below→above
    # Filter out pairs where crossing points are too close (< 10 degrees)
    valleys = []
    i = 0
    
    # Calculate degrees per point (420 degrees over profile length)
    degrees_per_point = 420.0 / profile_len
    min_separation_points = int(10.0 / degrees_per_point)  # Minimum 10 degrees separation
    
    while i < len(crossing_points) - 1:
        current_point = crossing_points[i]
        next_point = crossing_points[i + 1]
        
        # Check if we have a valid FWHM pair: above→below followed by below→above
        if (current_point['crossing_type'] == 'above_to_below' and 
            next_point['crossing_type'] == 'below_to_above'):
            
            # Calculate separation between crossing points
            separation_points = next_point['index'] - current_point['index']
            separation_degrees = separation_points * degrees_per_point
            
            # Only accept valleys if crossing points are sufficiently separated (>= 10 degrees)
            if separation_degrees >= 10.0:
                # Calculate valley center as midpoint between the two crossing points
                valley_center = (current_point['index'] + next_point['index']) // 2
                
                valleys.append({
                    'center': valley_center,
                    'above_below_point': current_point['index'],
                    'below_above_point': next_point['index'],
                    'fwhm_width': separation_points,
                    'separation_degrees': separation_degrees,
                    'intensity_at_center': profile[valley_center]
                })
            
            i += 2  # Skip both points in the pair
        else:
            i += 1  # Move to next point
    
    return [v['center'] for v in valleys]

def _normalize(v):
    vec = np.array(v, dtype=float)
    n = np.linalg.norm(vec)
    if n < 1e-8:
        return None
    return vec / n


def build_line_model_from_segment(line):
    """Build a stable line model from segment endpoints."""
    p1 = np.array([line['x1'], line['y1']], dtype=float)
    p2 = np.array([line['x2'], line['y2']], dtype=float)
    direction = _normalize(p2 - p1)
    if direction is None:
        return None
    normal = np.array([-direction[1], direction[0]], dtype=float)
    center = (p1 + p2) / 2.0
    return {
        'p1': p1,
        'p2': p2,
        'point': center,
        'direction': direction,
        'normal': normal,
        'center': center,
    }


def rotate_point(point, center, angle_rad):
    """Rotate one 2D point around image center."""
    pt = np.asarray(point, dtype=float)
    ctr = np.asarray(center, dtype=float)
    c = float(np.cos(angle_rad))
    s = float(np.sin(angle_rad))
    shifted = pt - ctr
    # Match PIL.Image.rotate(+deg) geometry in image coordinates (+Y downward).
    rotated = np.array([
        shifted[0] * c - shifted[1] * s,
        shifted[0] * s + shifted[1] * c,
    ], dtype=float)
    return rotated + ctr


def rotate_line_segment(line, center, angle_rad):
    """Rotate a line segment dictionary around center."""
    p1 = rotate_point((line['x1'], line['y1']), center, angle_rad)
    p2 = rotate_point((line['x2'], line['y2']), center, angle_rad)
    return {
        'x1': float(p1[0]),
        'y1': float(p1[1]),
        'x2': float(p2[0]),
        'y2': float(p2[1]),
    }


def compute_best_fit_axis_rotation(light_models):
    """
    Estimate global rotation that best aligns light lines to 0/90-degree axes.
    """
    if not light_models:
        return 0.0
    angles = []
    for model in light_models:
        d = model['direction']
        angles.append(float(np.arctan2(d[1], d[0])))

    def axis_deviation(theta):
        # Deviation from nearest axis in [-45, +45] degrees (radians).
        return ((theta + np.pi / 4.0) % (np.pi / 2.0)) - (np.pi / 4.0)

    # Robust coarse-to-fine search for rotation that minimizes total axis deviation.
    best_delta = 0.0
    best_cost = None
    for deg in np.linspace(-45.0, 45.0, 721):  # 0.125-degree step
        delta = np.deg2rad(float(deg))
        # With rotate_point/PIL-consistent transform, line angle increases by +delta.
        devs = np.asarray([abs(axis_deviation(a + delta)) for a in angles], dtype=float)
        # L1 objective is robust against one bad user-drawn line.
        cost = float(np.sum(devs))
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_delta = delta
    return float(best_delta)


def sample_profile_along_segment(image_array, p1, p2, sample_count=260):
    """Sample grayscale values along a segment."""
    ts = np.linspace(0.0, 1.0, max(sample_count, 20))
    pts = p1[None, :] + (p2 - p1)[None, :] * ts[:, None]
    xs = np.clip(np.round(pts[:, 0]).astype(int), 0, image_array.shape[1] - 1)
    ys = np.clip(np.round(pts[:, 1]).astype(int), 0, image_array.shape[0] - 1)
    return image_array[ys, xs].astype(float), ts


def sample_profile_along_segment_with_bounds(image_array, p1, p2, sample_count=260):
    """Sample grayscale values along a segment with explicit in-bounds mask."""
    ts = np.linspace(0.0, 1.0, max(sample_count, 20))
    pts = p1[None, :] + (p2 - p1)[None, :] * ts[:, None]
    xs = np.round(pts[:, 0]).astype(int)
    ys = np.round(pts[:, 1]).astype(int)
    h, w = image_array.shape[:2]
    in_bounds = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    values = np.full(ts.shape[0], np.nan, dtype=float)
    if np.any(in_bounds):
        values[in_bounds] = image_array[ys[in_bounds], xs[in_bounds]].astype(float)
    return values, ts, in_bounds


def robust_band_profile(image_array, p1, p2, normal, band_width_px=20, band_lines=20, sample_count=260):
    """
    Build one robust profile by aggregating multiple nearby parallel lines.
    Returns: profile, ts, station_valid_ratio
    """
    half = float(band_width_px) / 2.0
    offsets = np.linspace(-half, half, max(int(band_lines), 3))
    profiles = []
    valids = []
    ts_out = None
    for off in offsets:
        lp1 = p1 + normal * off
        lp2 = p2 + normal * off
        vals, ts, in_bounds = sample_profile_along_segment_with_bounds(
            image_array=image_array,
            p1=lp1,
            p2=lp2,
            sample_count=sample_count,
        )
        if np.mean(in_bounds.astype(float)) < 0.6:
            continue
        profiles.append(vals)
        valids.append(in_bounds.astype(float))
        ts_out = ts

    if not profiles or ts_out is None:
        return None, None, 0.0

    stacked = np.vstack(profiles)
    profile = np.nanmedian(stacked, axis=0)
    valid_stack = np.vstack(valids)
    valid_ratio = float(np.mean(np.any(valid_stack > 0.5, axis=0)))
    return profile, ts_out, valid_ratio


def interpolate_nans(profile):
    """Fill NaN samples using 1D interpolation; return None if insufficient data."""
    arr = np.asarray(profile, dtype=float)
    valid = np.isfinite(arr)
    if np.count_nonzero(valid) < 8:
        return None
    if np.all(valid):
        return arr
    x = np.arange(arr.shape[0], dtype=float)
    arr[~valid] = np.interp(x[~valid], x[valid], arr[valid])
    return arr


def detect_background_mode_pixel(image_array):
    """Return dominant grayscale value in the cropped film image."""
    flat = np.asarray(image_array, dtype=np.uint8).ravel()
    if flat.size == 0:
        return 0
    hist = np.bincount(flat, minlength=256)
    return int(np.argmax(hist))


def adjust_guide_model_from_mode_profile(
    image_array,
    guide_model,
    background_mode,
    profile_half_len=50,
    mode_tolerance=3,
    retreat_px=20,
):
    """
    Use center-perpendicular profile to detect background-mode intersection.
    If found, move guide line backward by retreat_px away from that side.
    """
    center = guide_model['center']
    normal = guide_model['normal']
    h, w = image_array.shape[:2]

    # Sample along normal through line center: -half_len ... +half_len
    offsets = np.arange(-int(profile_half_len), int(profile_half_len) + 1, dtype=float)
    points = center[None, :] + offsets[:, None] * normal[None, :]
    xs = np.round(points[:, 0]).astype(int)
    ys = np.round(points[:, 1]).astype(int)

    in_bounds = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    if not np.any(in_bounds):
        return guide_model

    values = np.full(xs.shape[0], -9999, dtype=int)
    values[in_bounds] = image_array[ys[in_bounds], xs[in_bounds]].astype(int)
    mode_hits = in_bounds & (np.abs(values - int(background_mode)) <= int(mode_tolerance))
    if not np.any(mode_hits):
        return guide_model

    center_idx = len(offsets) // 2
    hit_indices = np.where(mode_hits)[0]
    nearest = int(hit_indices[np.argmin(np.abs(hit_indices - center_idx))])

    # Determine side where background is reached.
    if nearest == center_idx:
        shift_vec = -normal * float(retreat_px)
    elif nearest > center_idx:
        # background appears in +normal direction, so move toward -normal
        shift_vec = -normal * float(retreat_px)
    else:
        # background appears in -normal direction, so move toward +normal
        shift_vec = normal * float(retreat_px)

    shifted_p1 = guide_model['p1'] + shift_vec
    shifted_p2 = guide_model['p2'] + shift_vec
    shifted = build_line_model_from_segment({
        'x1': float(shifted_p1[0]),
        'y1': float(shifted_p1[1]),
        'x2': float(shifted_p2[0]),
        'y2': float(shifted_p2[1]),
    })
    return shifted if shifted is not None else guide_model


def find_edge_position_improved(profile, target_ratio=0.3):
    """
    Find edge index by target crossing (default 30% of profile range above min).
    Uses crossing interpolation and prefers crossing nearest profile center.
    """
    if len(profile) < 8:
        return len(profile) // 2

    smoothed = gaussian_filter1d(np.asarray(profile, dtype=float), sigma=2.0)
    p_max = float(np.max(smoothed))
    p_min = float(np.min(smoothed))
    p_range = p_max - p_min
    if p_range < 1e-6:
        return len(smoothed) // 2

    target = p_min + p_range * float(target_ratio)
    crossings = []
    for i in range(len(smoothed) - 1):
        y1 = smoothed[i] - target
        y2 = smoothed[i + 1] - target
        if y1 == 0:
            crossings.append(float(i))
        elif y1 * y2 < 0:
            denom = (smoothed[i + 1] - smoothed[i])
            frac = (target - smoothed[i]) / denom if abs(denom) > 1e-8 else 0.0
            crossings.append(i + float(frac))

    if crossings:
        center = (len(smoothed) - 1) / 2.0
        return int(round(min(crossings, key=lambda c: abs(c - center))))

    differences = np.abs(smoothed - target)
    return int(np.argmin(differences))


def extract_profile(image_array, x1, y1, x2, y2, width=40):
    """
    Backward-compatible wrapper for older callers.
    Extracts mean profile from a band built by shifting segment along its normal.
    """
    model = build_line_model_from_segment({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
    if model is None:
        return np.array([])
    normal = model['normal']
    offsets = np.linspace(-width / 2.0, width / 2.0, max(int(width / 8), 5))
    profiles = []
    for off in offsets:
        p1 = model['p1'] + normal * off
        p2 = model['p2'] + normal * off
        profile, _ = sample_profile_along_segment(image_array, p1, p2)
        if len(profile) > 0:
            profiles.append(profile)
    if not profiles:
        return np.array([])
    min_len = min(len(p) for p in profiles)
    if min_len <= 0:
        return np.array([])
    stacked = np.vstack([p[:min_len] for p in profiles])
    return np.mean(stacked, axis=0)


def fit_line_total_least_squares(points):
    """Fit a line using PCA/TLS from list of 2D points."""
    pts = np.asarray(points, dtype=float)
    if pts.shape[0] < 2:
        return None
    center = np.mean(pts, axis=0)
    centered = pts - center
    cov = centered.T @ centered
    vals, vecs = np.linalg.eigh(cov)
    direction = vecs[:, np.argmax(vals)]
    direction = _normalize(direction)
    if direction is None:
        return None
    normal = np.array([-direction[1], direction[0]], dtype=float)
    return {
        'point': center,
        'center': center,
        'direction': direction,
        'normal': normal,
        'edge_points': pts,
    }


def detect_radiation_border_line(
    image_array,
    guide_line,
    reference_light_model=None,
    station_band_width_px=20,
    station_line_count=20,
    num_profiles=9,
    target_ratio=0.3,
    background_mode=None,
    mode_tolerance=3,
    retreat_px=20,
):
    """
    Build one radiation border line from one guide line and constrain it to be
    parallel with the reference light line (normal-displacement model).
    """
    guide_model = build_line_model_from_segment(guide_line)
    if guide_model is None or reference_light_model is None:
        return None, []

    # Guardrail: guide and paired light edge should be near-parallel.
    guide_ang = line_angle_mod_pi(guide_model)
    light_ang = line_angle_mod_pi(reference_light_model)
    if angle_difference_mod_pi(guide_ang, light_ang) > np.deg2rad(20.0):
        return None, []

    if background_mode is not None:
        guide_model = adjust_guide_model_from_mode_profile(
            image_array=image_array,
            guide_model=guide_model,
            background_mode=background_mode,
            profile_half_len=50,
            mode_tolerance=mode_tolerance,
            retreat_px=retreat_px,
        )

    # Parallel sampling lines offset perpendicular to the guide (as originally),
    # but confined to the user band width: guide centred, ±half_band each side.
    # Each station is a full-length profile on a shifted copy of the guide; one
    # edge point (yellow marker) is found per station.
    guide_normal = guide_model['normal']
    guide_len = float(np.linalg.norm(guide_model['p2'] - guide_model['p1']))
    if guide_len < 20.0:
        return None, []

    half_band = float(station_band_width_px) / 2.0
    station_count = max(3, int(station_line_count), int(num_profiles))
    offsets = np.linspace(-half_band, half_band, station_count)

    edge_points = []
    distances = []
    for off in offsets:
        p1 = guide_model['p1'] + guide_normal * float(off)
        p2 = guide_model['p2'] + guide_normal * float(off)
        profile, ts = sample_profile_along_segment(
            image_array=image_array,
            p1=p1,
            p2=p2,
            sample_count=260,
        )
        if len(profile) < 8:
            continue
        profile_filled = interpolate_nans(np.asarray(profile, dtype=float))
        if profile_filled is None:
            continue
        edge_idx = find_edge_position_improved(profile_filled, target_ratio=target_ratio)
        t = float(ts[max(0, min(edge_idx, len(ts) - 1))])
        edge_point = p1 + (p2 - p1) * t
        edge_points.append(edge_point)
        distances.append(signed_line_distance(reference_light_model, edge_point))

    if len(distances) < 3:
        return None, edge_points

    dist_arr = np.asarray(distances, dtype=float)
    med = float(np.median(dist_arr))
    mad = float(np.median(np.abs(dist_arr - med)))
    if mad > 1e-6:
        inlier_mask = np.abs(dist_arr - med) <= (3.0 * mad)
        if np.count_nonzero(inlier_mask) >= 3:
            dist_arr = dist_arr[inlier_mask]
    disp = float(np.median(dist_arr))
    # Final radiation line is a pure best-fit of extracted points.
    # Do not force direction from light/user guide.
    model = fit_line_total_least_squares(edge_points) if len(edge_points) >= 3 else None
    if model is not None:
        # Build finite segment from point spread for stable overlay rendering.
        pts = np.asarray(edge_points, dtype=float)
        direction = model['direction']
        # Constrain to nearest axis so the displayed radiation edge is straight
        # (horizontal/vertical) instead of slightly tilted by point noise.
        if abs(direction[0]) >= abs(direction[1]):
            direction = np.array([1.0 if direction[0] >= 0 else -1.0, 0.0], dtype=float)
        else:
            direction = np.array([0.0, 1.0 if direction[1] >= 0 else -1.0], dtype=float)
        center = model['point']
        proj = (pts - center[None, :]) @ direction
        min_proj = float(np.min(proj))
        max_proj = float(np.max(proj))
        # Add small margin so line covers full point cloud.
        margin = 8.0
        model['direction'] = direction
        model['normal'] = np.array([-direction[1], direction[0]], dtype=float)
        model['p1'] = center + direction * (min_proj - margin)
        model['p2'] = center + direction * (max_proj + margin)
        model['edge_points'] = np.asarray(edge_points, dtype=float)
        model['parallel_displacement_px'] = disp
    return model, edge_points


def line_angle_mod_pi(model):
    d = model['direction']
    angle = np.arctan2(d[1], d[0])
    if angle < 0:
        angle += np.pi
    return angle


def angle_difference_mod_pi(a, b):
    diff = abs(a - b)
    return min(diff, np.pi - diff)


def signed_line_distance(line_model, point):
    """Signed perpendicular distance from point to line (in pixels)."""
    return float(np.dot((np.asarray(point, dtype=float) - line_model['point']), line_model['normal']))


def pair_line_sets(light_models, rad_models, image_center=None):
    """Greedy one-to-one pairing by side, near-parallel angle, and center distance."""
    pairs = []
    used_rad = set()
    max_angle = np.deg2rad(20.0)
    light_sides = {}
    rad_sides = {}
    if image_center is not None:
        light_sides = {idx: classify_side_from_line(model, image_center) for idx, model in enumerate(light_models)}
        rad_sides = {idx: classify_side_from_line(model, image_center) for idx, model in enumerate(rad_models)}
    for li, lm in enumerate(light_models):
        l_ang = line_angle_mod_pi(lm)
        expected_side = light_sides.get(li)
        best_idx = None
        best_cost = None
        for pass_idx in range(2):
            for ri, rm in enumerate(rad_models):
                if ri in used_rad:
                    continue
                if pass_idx == 0 and expected_side is not None and rad_sides.get(ri) != expected_side:
                    continue
                r_ang = line_angle_mod_pi(rm)
                ang = angle_difference_mod_pi(l_ang, r_ang)
                if ang > max_angle:
                    continue
                center_dist = np.linalg.norm(lm['center'] - rm['center'])
                cost = ang * 2000.0 + center_dist
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_idx = ri
            if best_idx is not None:
                break
        if best_idx is None:
            continue
        used_rad.add(best_idx)
        pairs.append((li, best_idx))
    return pairs


def classify_side_from_line(line_model, image_center):
    """Classify a line into left/right/top/bottom using orientation + position."""
    d = line_model['direction']
    c = line_model['center']
    if abs(d[0]) >= abs(d[1]):  # mostly horizontal
        return 'top' if c[1] < image_center[1] else 'bottom'
    return 'left' if c[0] < image_center[0] else 'right'


def project_line_to_image_bounds(line_model, width, height):
    """Project an infinite line to image boundary segment for drawing."""
    p = line_model['point']
    d = line_model['direction']
    intersections = []
    eps = 1e-8
    if abs(d[0]) > eps:
        t = (0 - p[0]) / d[0]
        y = p[1] + t * d[1]
        if 0 <= y <= height - 1:
            intersections.append((0, int(round(y))))
        t = (width - 1 - p[0]) / d[0]
        y = p[1] + t * d[1]
        if 0 <= y <= height - 1:
            intersections.append((width - 1, int(round(y))))
    if abs(d[1]) > eps:
        t = (0 - p[1]) / d[1]
        x = p[0] + t * d[0]
        if 0 <= x <= width - 1:
            intersections.append((int(round(x)), 0))
        t = (height - 1 - p[1]) / d[1]
        x = p[0] + t * d[0]
        if 0 <= x <= width - 1:
            intersections.append((int(round(x)), height - 1))

    if len(intersections) < 2:
        return None, None
    unique = []
    for pt in intersections:
        if pt not in unique:
            unique.append(pt)
    if len(unique) < 2:
        return None, None
    return unique[0], unique[1]

@login_required
@user_passes_test(lambda user: user.is_staff)
def debug_collimator_files(request):
    """Debug endpoint to list available collimator files"""
    import os
    from django.conf import settings
    
    media_dir = os.path.join(settings.MEDIA_ROOT, 'film_uploads')
    files = []
    
    if os.path.exists(media_dir):
        for filename in os.listdir(media_dir):
            # Show all files, not just collimator ones
            file_path = os.path.join(media_dir, filename)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            files.append({
                'name': filename,
                'size': file_size,
                'exists': os.path.exists(file_path)
            })
    
    return JsonResponse({
        'media_dir': media_dir,
        'files': files,
        'total_files': len(files)
    })

# ==================== GANTRY FILM FUNCTIONS ====================

@login_required
def upload_gantry_film(request):
    """Upload gantry film image"""
    if request.method == 'POST':
        try:
            image_file = request.FILES.get('image')
            manual_dpi = request.POST.get('manual_dpi')
            
            if not image_file:
                return JsonResponse({'success': False, 'error': 'No image file provided'})
            
            # Extract DPI from image or use manual input
            extracted_dpi = extract_dpi(image_file)
            
            if not extracted_dpi and not manual_dpi:
                return JsonResponse({'success': False, 'error': 'Could not determine DPI. Please provide manually.'})
            
            # Use GantryFilmUpload model for proper naming and DPI storage
            from QAID_Manager.models import GantryFilmUpload
            
            # Remove old gantry files
            GantryFilmUpload.objects.filter(uploaded_by=request.user).delete()
            for name in [GANTRY_CROPPED_FILENAME]:
                path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, name)
                if os.path.exists(path):
                    os.remove(path)
            
            # Save the film with proper naming
            film = GantryFilmUpload()
            film.uploaded_by = request.user
            film.extracted_dpi = extracted_dpi
            film.dpi = manual_dpi if manual_dpi else extracted_dpi
            film.image = image_file
            film.save()
            request.session['gantry_uploaded'] = True
            _clear_session_keys(request, 'gantry_cropped', 'gantry_circle_data')
            _drop_latest_analysis_path(request, GANTRY_ANALYSIS_KEY)
            
            # Log activity
            ActivityService.log_activity(
                user=request.user,
                activity_type='gantry_film_upload',
                description=f'Uploaded gantry film image (DPI: {film.dpi})'
            )
            
            filename = os.path.basename(film.image.name)
            return JsonResponse({
                'success': True,
                'message': 'Gantry film uploaded successfully',
                'filename': filename,
                'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}',
                'dpi': film.dpi
            })
            
        except Exception as e:
            logger.error(f"Error uploading gantry film: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@require_POST
@login_required
def crop_gantry_film(request):
    """Crop gantry film"""
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        cropped_file = request.FILES.get('cropped_image')
        if not cropped_file:
            return JsonResponse({'success': False, 'error': 'No image received'})

        # Save to unique fixed path as PNG
        ext = 'png'
        target_path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, f'gantry_film_cropped.{ext}')

        if os.path.exists(target_path):
            os.remove(target_path)

        default_storage.save(f'{FILM_UPLOAD_SUBDIR}/gantry_film_cropped.{ext}', ContentFile(cropped_file.read()))

        request.session['gantry_cropped'] = True
        _clear_session_keys(request, 'gantry_circle_data')
        _drop_latest_analysis_path(request, GANTRY_ANALYSIS_KEY)
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error in crop_gantry_film view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def set_gantry_center(request):
    """Set gantry analysis circle"""
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            
            # Extract circle data
            center_x = float(data.get('center_x', 0))
            center_y = float(data.get('center_y', 0))
            radius = float(data.get('radius', 0))
            
            # Extract pixel size information for displacement calculations
            image_display_width = data.get('image_display_width', 0)
            image_display_height = data.get('image_display_height', 0)
            image_actual_width = data.get('image_actual_width', 0)
            image_actual_height = data.get('image_actual_height', 0)
            scale_x = data.get('scale_x', 1.0)
            scale_y = data.get('scale_y', 1.0)
            
            # Validate circle data
            if radius <= 0:
                return JsonResponse({'success': False, 'error': 'Invalid circle radius'})
            
            # Store circle data and pixel size information in session
            request.session['gantry_circle_data'] = {
                'center_x': center_x,
                'center_y': center_y,
                'radius': radius,
                'image_display_width': image_display_width,
                'image_display_height': image_display_height,
                'image_actual_width': image_actual_width,
                'image_actual_height': image_actual_height,
                'scale_x': scale_x,
                'scale_y': scale_y
            }
            
            logger.info(f"Gantry analysis circle set: center=({center_x}, {center_y}), radius={radius}")
            logger.info(f"Image size: display=({image_display_width}x{image_display_height}), actual=({image_actual_width}x{image_actual_height})")
            return JsonResponse({'success': True})
            
    except Exception as e:
        logger.error(f"Error in set_gantry_center view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@require_POST
@login_required
def analyze_gantry(request):
    """Analyze gantry isocenter using the user-defined circle"""
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
        # Get the analysis circle from session
        circle_data = request.session.get('gantry_circle_data')
        if not circle_data:
            return JsonResponse({'success': False, 'error': 'Analysis circle not defined. Please define a circle first.'})
        
        # Get film image path
        film_path = os.path.join(settings.MEDIA_ROOT, FILM_UPLOAD_SUBDIR, GANTRY_CROPPED_FILENAME)
        if not os.path.exists(film_path):
            return JsonResponse({'success': False, 'error': 'Gantry film image not found. Please upload and crop the film first.'})
        
        # Load image
        img = Image.open(film_path).convert('L')  # Convert to grayscale
        img_rgb = Image.open(film_path).convert('RGB')  # For drawing
        img_array = np.array(img)
        draw = ImageDraw.Draw(img_rgb)
        
        # Extract circle parameters (already scaled by JavaScript)
        center_x = int(circle_data['center_x'])
        center_y = int(circle_data['center_y'])
        user_radius = int(circle_data['radius'])
        
        # Get pixel size information for displacement calculations
        image_actual_width = circle_data.get('image_actual_width', img_array.shape[1])
        image_actual_height = circle_data.get('image_actual_height', img_array.shape[0])
        
        # Calculate pixels per mm using the film's actual DPI
        # Get the film's DPI from the uploaded film
        from QAID_Manager.models import GantryFilmUpload
        film = GantryFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at').first()
        
        if not film or not film.dpi:
            return JsonResponse({'success': False, 'error': 'No DPI information found. Please upload the film with DPI information.'})
        
        film_dpi = film.dpi
        
        # Calculate pixels per mm using the film's DPI
        px_per_mm = film_dpi / 25.4  # Convert DPI to pixels per mm
        
        print(f"Gantry Film DPI: {film_dpi}")
        print(f"Gantry Pixels per mm: {px_per_mm:.2f}")
        print(f"Gantry Image dimensions: {image_actual_width}x{image_actual_height} pixels")
        print(f"Gantry Calculated film size: {image_actual_width/px_per_mm:.1f}x{image_actual_height/px_per_mm:.1f} mm")
        
        # Extract profile along the user-defined circle
        bands, debug_text, graph_path = extract_radial_bands(img_array, center_x, center_y, user_radius)
        
        if len(bands) < 6:
            return JsonResponse({'success': False, 'error': f'Expected at least 6 radiation bands, found {len(bands)}. Please check the circle position.'})
        
        # Group and refine bands
        refined_bands = group_and_refine_bands(bands, center_x, center_y)
        
        # Find opposite band pairs and calculate central lines
        central_lines = calculate_central_lines(refined_bands, center_x, center_y)
        
        # Find intersections of central lines
        intersections = find_line_intersections(central_lines)
        
        if not intersections:
            # Try to use band centers as fallback
            if refined_bands:
                # Use the center of the bands as radiation isocenter
                rad_iso_x = np.mean([band['x'] for band in refined_bands])
                rad_iso_y = np.mean([band['y'] for band in refined_bands])
                circle_diameter = 0
            else:
                return JsonResponse({'success': False, 'error': 'Could not find intersections of central lines and no bands available for fallback.'})
        else:
            # Calculate radiation isocenter as center of minimum enclosing circle
            if len(intersections) >= 2:
                rad_iso_x, rad_iso_y, circle_diameter = calculate_minimum_enclosing_circle(intersections)
            else:
                # Fallback to average if not enough intersections
                rad_iso_x = np.mean([p[0] for p in intersections])
                rad_iso_y = np.mean([p[1] for p in intersections])
                circle_diameter = 0
        
        # Calculate displacement from mechanical center
        mech_center_x = center_x
        mech_center_y = center_y
        
        displacement_x = rad_iso_x - mech_center_x
        displacement_y = rad_iso_y - mech_center_y
        total_displacement = np.sqrt(displacement_x**2 + displacement_y**2)
        
        # Convert to mm
        displacement_mm = total_displacement / px_per_mm
        circle_diameter_mm = circle_diameter / px_per_mm
        
        # Draw results on image
        draw_analysis_results(draw, center_x, center_y, user_radius, refined_bands, 
                            central_lines, intersections, rad_iso_x, rad_iso_y, 
                            mech_center_x, mech_center_y, circle_diameter, px_per_mm, film_dpi, film.extracted_dpi)
        
        # Save result image with unique naming
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        result_filename = f'gantry_analysis_result_{timestamp}_{unique_id}.png'
        result_path = os.path.join(settings.MEDIA_ROOT, 'film_uploads', result_filename)
        img_rgb.save(result_path)

        _set_latest_analysis_path(request, GANTRY_ANALYSIS_KEY, result_path)
        
        # Check tolerance (circle diameter < 1.0mm)
        is_acceptable = circle_diameter_mm < 1.0
        
        # Store the analysis result for automatic test input
        QAService.store_film_analysis_result('gantry_isocenter', {
            'displacement_mm': displacement_mm,
            'circle_diameter_mm': circle_diameter_mm,
            'is_acceptable': is_acceptable,
            'radiation_isocenter': [rad_iso_x, rad_iso_y],
            'mechanical_center': [mech_center_x, mech_center_y]
        })
        
        return JsonResponse({
            'success': True,
            'result_image_url': f'/media/film_uploads/{result_filename}',
            'profile_graph_url': '/media/film_uploads/radial_profile_graph.png',
            'displacement_mm': float(round(displacement_mm, 2)),
            'circle_diameter_mm': float(round(circle_diameter_mm, 2)),
            'is_acceptable': bool(is_acceptable),
            'radiation_isocenter': [float(round(rad_iso_x, 1)), float(round(rad_iso_y, 1))],
            'mechanical_center': [float(mech_center_x), float(mech_center_y)]
        })
        
    except Exception as e:
        logger.error(f"Error in gantry analysis: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Analysis failed: {str(e)}'})

@login_required
@user_passes_test(lambda user: user.is_staff)
def debug_gantry_files(request):
    """Debug endpoint to list available gantry files"""
    import os
    from django.conf import settings
    
    media_dir = os.path.join(settings.MEDIA_ROOT, 'film_uploads')
    files = []
    
    if os.path.exists(media_dir):
        for filename in os.listdir(media_dir):
            file_path = os.path.join(media_dir, filename)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            files.append({
                'name': filename,
                'size': file_size,
                'exists': os.path.exists(file_path)
            })
    
    return JsonResponse({
        'media_dir': media_dir,
        'files': files,
        'total_files': len(files)
    })

@login_required
def get_latest_film_filename(request):
    """API endpoint to get the latest uploaded film filename for fieldsize"""
    try:
        film = None
        for candidate in FilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at'):
            if candidate.image and default_storage.exists(candidate.image.name):
                film = candidate
                break
        if film and film.image:
            filename = os.path.basename(film.image.name)
            return JsonResponse({
                'success': True,
                'filename': filename,
                'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No uploaded film found'
            })
    except Exception as e:
        logger.error(f"Error getting latest film filename: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def get_latest_colli_film_filename(request):
    """API endpoint to get the latest uploaded collimator film filename."""
    try:
        from QAID_Manager.models import CollimatorFilmUpload
        film = None
        for candidate in CollimatorFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at'):
            if candidate.image and default_storage.exists(candidate.image.name):
                film = candidate
                break
        if film and film.image:
            filename = os.path.basename(film.image.name)
            return JsonResponse({
                'success': True,
                'filename': filename,
                'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}'
            })
        return JsonResponse({'success': False, 'error': 'No collimator film found'})
    except Exception as e:
        logger.error(f"Error getting latest colli film filename: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_latest_gantry_film_filename(request):
    """API endpoint to get the latest uploaded gantry film filename."""
    try:
        from QAID_Manager.models import GantryFilmUpload
        film = None
        for candidate in GantryFilmUpload.objects.filter(uploaded_by=request.user).order_by('-uploaded_at'):
            if candidate.image and default_storage.exists(candidate.image.name):
                film = candidate
                break
        if film and film.image:
            filename = os.path.basename(film.image.name)
            return JsonResponse({
                'success': True,
                'filename': filename,
                'url': film.image.url if hasattr(film.image, 'url') else f'/media/{film.image.name}'
            })
        return JsonResponse({'success': False, 'error': 'No gantry film found'})
    except Exception as e:
        logger.error(f"Error getting latest gantry film filename: {e}")
        return JsonResponse({'success': False, 'error': str(e)})