"""Starshot-style circular-profile analysis helpers (NumPy / SciPy only).

Assumes dark radiation spokes on a bright background (synthetic films).
Educational / research-prototype implementations only — not for clinical use.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter1d


def extract_circular_profile(
    image_array: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    start_angle: float = 0.0,
    end_angle: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Sample intensity along a circle; return (profile, angles).

    Default sweep is 0 → 420° (360° + 60°) to avoid splitting spokes at 0°.
    Educational implementation only — not for clinical use.
    """
    if end_angle is None:
        end_angle = 2.0 * np.pi + np.pi / 3.0
    num_points = max(64, int((end_angle - start_angle) * radius * 0.5))
    angles = np.linspace(start_angle, end_angle, num_points, endpoint=False)
    profile = np.empty(num_points, dtype=float)
    h, w = image_array.shape[:2]
    for i, angle in enumerate(angles):
        x = int(round(cx + radius * np.cos(angle)))
        y = int(round(cy + radius * np.sin(angle)))
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        profile[i] = float(image_array[y, x])
    return profile, angles


def find_valleys_by_intensity_threshold(profile: Sequence[float]) -> List[int]:
    """Find dark-spoke valleys via mid-intensity crossings (FWHM-style).

    Educational implementation only — not for clinical use.
    """
    arr = np.asarray(profile, dtype=float)
    profile_len = len(arr)
    if profile_len < 8:
        return []

    max_intensity = float(np.max(arr))
    min_intensity = float(np.min(arr))
    mean_intensity = min_intensity + (max_intensity - min_intensity) / 2.0
    threshold = mean_intensity

    crossing_points: List[Dict[str, Any]] = []
    was_below_threshold = True
    for i in range(profile_len):
        is_above_threshold = arr[i] >= threshold
        if was_below_threshold and is_above_threshold:
            crossing_points.append({"index": i, "crossing_type": "below_to_above"})
        elif not was_below_threshold and not is_above_threshold:
            crossing_points.append({"index": i, "crossing_type": "above_to_below"})
        was_below_threshold = not is_above_threshold

    degrees_per_point = 420.0 / max(profile_len, 1)
    # Accept narrower dips on synthetic films (original clinical films are wider).
    min_sep_deg = 3.0
    valleys: List[int] = []
    i = 0
    while i < len(crossing_points) - 1:
        current = crossing_points[i]
        nxt = crossing_points[i + 1]
        if (
            current["crossing_type"] == "above_to_below"
            and nxt["crossing_type"] == "below_to_above"
        ):
            separation_degrees = (nxt["index"] - current["index"]) * degrees_per_point
            if separation_degrees >= min_sep_deg:
                valleys.append((current["index"] + nxt["index"]) // 2)
            i += 2
        else:
            i += 1

    # Fallback: local minima below mid-intensity (helps thin synthetic spokes).
    if len(valleys) < 4:
        threshold = mean_intensity
        local: List[int] = []
        for i in range(2, profile_len - 2):
            if arr[i] < threshold and arr[i] <= arr[i - 1] and arr[i] <= arr[i + 1]:
                if arr[i] <= arr[i - 2] and arr[i] <= arr[i + 2]:
                    if not local or (i - local[-1]) * degrees_per_point >= 20.0:
                        local.append(i)
        if len(local) > len(valleys):
            valleys = local
    return valleys


def filter_valleys_by_expected_angles(
    valleys: Sequence[int],
    angles: Sequence[float],
    expected_angles_deg: Sequence[float],
    tolerance_deg: float = 15.0,
) -> Tuple[List[int], List[float]]:
    """Keep valleys near expected starshot angles."""
    expected_angles_rad = [np.radians(a) for a in expected_angles_deg]
    tolerance_rad = np.radians(tolerance_deg)
    filtered_valleys: List[int] = []
    filtered_angles: List[float] = []

    for valley_idx in valleys:
        valley_angle = float(angles[valley_idx])
        min_distance = float("inf")
        for expected_angle in expected_angles_rad:
            angle_diff = abs(valley_angle - expected_angle)
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            min_distance = min(min_distance, angle_diff)
        if min_distance <= tolerance_rad:
            filtered_valleys.append(int(valley_idx))
            filtered_angles.append(valley_angle)
    return filtered_valleys, filtered_angles


def detect_bands_in_circular_profile(
    profile: Sequence[float],
    angles: Sequence[float],
    center_x: float,
    center_y: float,
    radius: float,
) -> Tuple[List[Dict[str, float]], str, List[int]]:
    """Detect dark spoke bands in a circular intensity profile.

    Educational implementation only — not for clinical use.
    """
    smoothed = gaussian_filter1d(np.asarray(profile, dtype=float), sigma=2.0)
    valleys = find_valleys_by_intensity_threshold(smoothed)

    expected_angles_deg = [0, 45, 90, 135, 180, 225, 270, 315]
    filtered_valleys, _ = filter_valleys_by_expected_angles(
        valleys, angles, expected_angles_deg, tolerance_deg=20
    )
    if len(filtered_valleys) < 6:
        filtered_valleys, _ = filter_valleys_by_expected_angles(
            valleys, angles, expected_angles_deg, tolerance_deg=30
        )

    bands: List[Dict[str, float]] = []
    for valley_idx in filtered_valleys:
        angle = float(angles[valley_idx])
        bands.append(
            {
                "x": float(center_x + radius * np.cos(angle)),
                "y": float(center_y + radius * np.sin(angle)),
                "angle": angle,
                "depth": float(np.max(smoothed) - smoothed[valley_idx]),
                "radius": float(radius),
            }
        )
    return bands, "", filtered_valleys


def group_and_refine_bands(
    all_bands: Sequence[Dict[str, float]],
    center_x: float,
    center_y: float,
) -> List[Dict[str, float]]:
    """Group nearby bands and keep up to 8 spokes."""
    del center_x, center_y  # API parity with original; unused in grouping
    if not all_bands:
        return []

    grouped: List[Dict[str, float]] = []
    used = set()
    for i, band1 in enumerate(all_bands):
        if i in used:
            continue
        group = [band1]
        used.add(i)
        for j, band2 in enumerate(all_bands):
            if j in used:
                continue
            angle_diff = abs(band2["angle"] - band1["angle"])
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            if angle_diff < np.radians(30):
                group.append(band2)
                used.add(j)
        total_depth = sum(b["depth"] for b in group) or 1.0
        refined_angle = sum(b["angle"] * b["depth"] for b in group) / total_depth
        if refined_angle < 0:
            refined_angle += 2 * np.pi
        grouped.append(
            {
                "x": sum(b["x"] * b["depth"] for b in group) / total_depth,
                "y": sum(b["y"] * b["depth"] for b in group) / total_depth,
                "angle": refined_angle,
                "depth": sum(b["depth"] for b in group),
            }
        )

    grouped.sort(key=lambda b: b["angle"])
    if len(grouped) > 8:
        grouped = sorted(grouped, key=lambda b: b["depth"], reverse=True)[:8]
        grouped.sort(key=lambda b: b["angle"])
    return grouped


def calculate_central_lines(
    bands: Sequence[Dict[str, float]],
    center_x: float,
    center_y: float,
) -> List[Tuple[Dict[str, float], Dict[str, float]]]:
    """Pair opposite bands into central spoke lines."""
    if len(bands) < 4:
        return []
    sorted_bands = sorted(bands, key=lambda b: b["angle"])
    central_lines: List[Tuple[Dict[str, float], Dict[str, float]]] = []
    used = set()
    for i, band1 in enumerate(sorted_bands):
        if i in used:
            continue
        best_opposite_idx = None
        min_angle_diff = float("inf")
        for j, band2 in enumerate(sorted_bands):
            if j == i or j in used:
                continue
            angle_diff = abs(band2["angle"] - band1["angle"])
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            if abs(angle_diff - np.pi) < min_angle_diff:
                min_angle_diff = abs(angle_diff - np.pi)
                best_opposite_idx = j
        if best_opposite_idx is not None:
            central_lines.append((band1, sorted_bands[best_opposite_idx]))
            used.add(i)
            used.add(best_opposite_idx)

    if len(central_lines) < 2 and len(bands) >= 4:
        remaining = [b for i, b in enumerate(sorted_bands) if i not in used]
        for band in remaining[:2]:
            central_lines.append(
                (band, {"x": float(center_x), "y": float(center_y), "angle": 0.0, "depth": 0.0})
            )
    return central_lines


def calculate_line_intersection(
    line1: Tuple[Dict[str, float], Dict[str, float]],
    line2: Tuple[Dict[str, float], Dict[str, float]],
) -> Optional[Tuple[float, float]]:
    """Intersection of two lines defined by endpoint band dicts."""
    p1, p2 = line1
    p3, p4 = line2
    x1, y1 = p1["x"], p1["y"]
    x2, y2 = p2["x"], p2["y"]
    x3, y3 = p3["x"], p3["y"]
    x4, y4 = p4["x"], p4["y"]
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-10:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def find_line_intersections(
    central_lines: Sequence[Tuple[Dict[str, float], Dict[str, float]]],
) -> List[Tuple[float, float]]:
    """All pairwise intersections of central lines."""
    intersections: List[Tuple[float, float]] = []
    for i, line1 in enumerate(central_lines):
        for line2 in central_lines[i + 1 :]:
            pt = calculate_line_intersection(line1, line2)
            if pt is not None:
                intersections.append(pt)
    return intersections


def calculate_minimum_enclosing_circle(
    points: Sequence[Sequence[float]],
) -> Tuple[float, float, float]:
    """Return (cx, cy, diameter) of an approximate minimum enclosing circle.

    Uses centroid + iterative pull toward farthest point (sufficient for tests).
    Educational implementation only — not for clinical use.
    """
    if not points:
        return 0.0, 0.0, 0.0
    if len(points) == 1:
        return float(points[0][0]), float(points[0][1]), 0.0
    if len(points) == 2:
        cx = (points[0][0] + points[1][0]) / 2.0
        cy = (points[0][1] + points[1][1]) / 2.0
        radius = (
            np.sqrt((points[0][0] - points[1][0]) ** 2 + (points[0][1] - points[1][1]) ** 2) / 2.0
        )
        return float(cx), float(cy), float(2.0 * radius)

    center_x = float(np.mean([p[0] for p in points]))
    center_y = float(np.mean([p[1] for p in points]))
    for _ in range(20):
        farthest = max(
            points,
            key=lambda p: (p[0] - center_x) ** 2 + (p[1] - center_y) ** 2,
        )
        new_x = center_x + 0.3 * (farthest[0] - center_x)
        new_y = center_y + 0.3 * (farthest[1] - center_y)
        if abs(new_x - center_x) < 0.01 and abs(new_y - center_y) < 0.01:
            break
        center_x, center_y = new_x, new_y

    radius = max(
        np.sqrt((p[0] - center_x) ** 2 + (p[1] - center_y) ** 2) for p in points
    )
    return float(center_x), float(center_y), float(2.0 * radius)


def analyze_starshot(
    image_array: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
    dpi: float,
) -> Dict[str, Any]:
    """Analyze a synthetic starshot film (dark spokes on bright background).

    Returns displacement_mm, circle_diameter_mm, radiation_isocenter,
    and mechanical_center. Educational use only — not clinical.
    """
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    px_per_mm = float(dpi) / 25.4

    profile, angles = extract_circular_profile(image_array, center_x, center_y, radius)
    bands, _, _ = detect_bands_in_circular_profile(
        profile, angles, center_x, center_y, radius
    )
    refined = group_and_refine_bands(bands, center_x, center_y)
    central_lines = calculate_central_lines(refined, center_x, center_y)
    intersections = find_line_intersections(central_lines)

    if intersections:
        if len(intersections) >= 2:
            rad_iso_x, rad_iso_y, circle_diameter = calculate_minimum_enclosing_circle(
                intersections
            )
        else:
            rad_iso_x = float(intersections[0][0])
            rad_iso_y = float(intersections[0][1])
            circle_diameter = 0.0
    elif refined:
        rad_iso_x = float(np.mean([b["x"] for b in refined]))
        rad_iso_y = float(np.mean([b["y"] for b in refined]))
        circle_diameter = 0.0
    else:
        rad_iso_x, rad_iso_y, circle_diameter = float(center_x), float(center_y), 0.0

    dx = rad_iso_x - center_x
    dy = rad_iso_y - center_y
    displacement_mm = float(np.sqrt(dx * dx + dy * dy) / px_per_mm)
    circle_diameter_mm = float(circle_diameter / px_per_mm)

    return {
        "displacement_mm": displacement_mm,
        "circle_diameter_mm": circle_diameter_mm,
        "radiation_isocenter": [rad_iso_x, rad_iso_y],
        "mechanical_center": [float(center_x), float(center_y)],
        "n_bands": len(refined),
        "n_intersections": len(intersections),
    }
