"""Field-size edge detection helpers (NumPy / SciPy only).

Ported/adapted from the prototype film-analysis logic for educational use
on synthetic dark-field / bright-background images.

Educational / research-prototype implementations only — not for clinical use.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter1d


def find_edge_position_improved(profile: Sequence[float], target_ratio: float = 0.3) -> int:
    """Find edge index by target crossing (default 30% of range above min).

    Uses crossing interpolation and prefers the crossing nearest the profile
    center. Educational implementation only — not for clinical use.
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
    crossings: List[float] = []
    for i in range(len(smoothed) - 1):
        y1 = smoothed[i] - target
        y2 = smoothed[i + 1] - target
        if y1 == 0:
            crossings.append(float(i))
        elif y1 * y2 < 0:
            denom = smoothed[i + 1] - smoothed[i]
            frac = (target - smoothed[i]) / denom if abs(denom) > 1e-8 else 0.0
            crossings.append(i + float(frac))

    if crossings:
        center = (len(smoothed) - 1) / 2.0
        return int(round(min(crossings, key=lambda c: abs(c - center))))

    differences = np.abs(smoothed - target)
    return int(np.argmin(differences))


def _normalize(v: np.ndarray) -> Optional[np.ndarray]:
    vec = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(vec))
    if n < 1e-8:
        return None
    return vec / n


def fit_line_total_least_squares(points: Sequence[Sequence[float]]) -> Optional[Dict[str, Any]]:
    """Fit a line using PCA / total least squares from 2D points.

    Educational implementation only — not for clinical use.
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] != 2:
        return None
    center = np.mean(pts, axis=0)
    centered = pts - center
    cov = centered.T @ centered
    vals, vecs = np.linalg.eigh(cov)
    direction = _normalize(vecs[:, np.argmax(vals)])
    if direction is None:
        return None
    normal = np.array([-direction[1], direction[0]], dtype=float)
    return {
        "point": center,
        "center": center,
        "direction": direction,
        "normal": normal,
        "edge_points": pts,
    }


def build_line_model_from_segment(line: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Build a stable line model from segment endpoints."""
    p1 = np.array([line["x1"], line["y1"]], dtype=float)
    p2 = np.array([line["x2"], line["y2"]], dtype=float)
    direction = _normalize(p2 - p1)
    if direction is None:
        return None
    normal = np.array([-direction[1], direction[0]], dtype=float)
    center = (p1 + p2) / 2.0
    return {
        "p1": p1,
        "p2": p2,
        "point": center,
        "direction": direction,
        "normal": normal,
        "center": center,
    }


def sample_profile_along_segment(
    image_array: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    sample_count: int = 260,
) -> Tuple[np.ndarray, np.ndarray]:
    """Sample grayscale values along a segment."""
    ts = np.linspace(0.0, 1.0, max(sample_count, 20))
    pts = p1[None, :] + (p2 - p1)[None, :] * ts[:, None]
    xs = np.clip(np.round(pts[:, 0]).astype(int), 0, image_array.shape[1] - 1)
    ys = np.clip(np.round(pts[:, 1]).astype(int), 0, image_array.shape[0] - 1)
    return image_array[ys, xs].astype(float), ts


def signed_line_distance(line_model: Dict[str, Any], point: Sequence[float]) -> float:
    """Signed perpendicular distance from point to line (pixels)."""
    return float(
        np.dot(
            (np.asarray(point, dtype=float) - line_model["point"]),
            line_model["normal"],
        )
    )


def classify_side_from_line(line_model: Dict[str, Any], image_center: np.ndarray) -> str:
    """Classify a line into left/right/top/bottom using orientation + position."""
    d = line_model["direction"]
    c = line_model["center"]
    if abs(d[0]) >= abs(d[1]):  # mostly horizontal
        return "top" if c[1] < image_center[1] else "bottom"
    return "left" if c[0] < image_center[0] else "right"


def _detect_edge_along_guide(
    image_array: np.ndarray,
    guide_model: Dict[str, Any],
    band_width_px: float,
    station_count: int,
    target_ratio: float,
) -> Optional[Dict[str, Any]]:
    """Detect a radiation border by sampling stations along a guide line."""
    guide_len = float(np.linalg.norm(guide_model["p2"] - guide_model["p1"]))
    if guide_len < 10.0:
        return None

    half_band = float(band_width_px) / 2.0
    offsets = np.linspace(-half_band, half_band, max(3, station_count))
    edge_points: List[np.ndarray] = []

    for off in offsets:
        p1 = guide_model["p1"] + guide_model["normal"] * float(off)
        p2 = guide_model["p2"] + guide_model["normal"] * float(off)
        profile, ts = sample_profile_along_segment(image_array, p1, p2, sample_count=260)
        if len(profile) < 8:
            continue
        edge_idx = find_edge_position_improved(profile, target_ratio=target_ratio)
        t = float(ts[max(0, min(edge_idx, len(ts) - 1))])
        edge_points.append(p1 + (p2 - p1) * t)

    if len(edge_points) < 3:
        return None

    model = fit_line_total_least_squares(edge_points)
    if model is None:
        return None

    # Snap to nearest axis for stable side classification on synthetic squares.
    direction = model["direction"]
    if abs(direction[0]) >= abs(direction[1]):
        direction = np.array([1.0 if direction[0] >= 0 else -1.0, 0.0], dtype=float)
    else:
        direction = np.array([0.0, 1.0 if direction[1] >= 0 else -1.0], dtype=float)
    model["direction"] = direction
    model["normal"] = np.array([-direction[1], direction[0]], dtype=float)
    model["edge_points"] = np.asarray(edge_points, dtype=float)
    return model


def _edge_coord_from_perpendicular_profile(
    image_array: np.ndarray,
    light_model: Dict[str, Any],
    guide_model: Dict[str, Any],
    side: str,
    band_width_px: float,
    target_ratio: float,
    n_stations: int = 9,
) -> float:
    """Locate radiation edge by sampling profiles perpendicular to a light edge.

    Returns the edge coordinate in pixels (x for left/right, y for top/bottom).
    """
    half = max(band_width_px / 2.0, 20.0)
    # Prefer guide center as search origin (near radiation border); fall back to light.
    origin = guide_model["center"]
    light_c = light_model["center"]

    coords: List[float] = []
    # Stations along the light edge direction.
    direction = light_model["direction"]
    span = float(np.linalg.norm(light_model["p2"] - light_model["p1"]))
    along = np.linspace(-0.35 * span, 0.35 * span, max(3, n_stations))

    for off in along:
        station = origin + direction * float(off)
        if side in ("left", "right"):
            # Horizontal profile crossing the vertical edge.
            x0 = station[0] - half
            x1 = station[0] + half
            y = int(round(station[1]))
            y = max(0, min(y, image_array.shape[0] - 1))
            p1 = np.array([x0, float(y)], dtype=float)
            p2 = np.array([x1, float(y)], dtype=float)
            profile, ts = sample_profile_along_segment(image_array, p1, p2, sample_count=260)
            if len(profile) < 8:
                continue
            idx = find_edge_position_improved(profile, target_ratio=target_ratio)
            t = float(ts[max(0, min(idx, len(ts) - 1))])
            edge_x = float(p1[0] + (p2[0] - p1[0]) * t)
            coords.append(edge_x)
        else:
            # Vertical profile crossing the horizontal edge.
            y0 = station[1] - half
            y1 = station[1] + half
            x = int(round(station[0]))
            x = max(0, min(x, image_array.shape[1] - 1))
            p1 = np.array([float(x), y0], dtype=float)
            p2 = np.array([float(x), y1], dtype=float)
            profile, ts = sample_profile_along_segment(image_array, p1, p2, sample_count=260)
            if len(profile) < 8:
                continue
            idx = find_edge_position_improved(profile, target_ratio=target_ratio)
            t = float(ts[max(0, min(idx, len(ts) - 1))])
            edge_y = float(p1[1] + (p2[1] - p1[1]) * t)
            coords.append(edge_y)

    if not coords:
        # Last resort: single profile through light center.
        if side in ("left", "right"):
            return float(light_c[0])
        return float(light_c[1])
    return float(np.median(coords))


def measure_field_shifts_from_synthetic(
    image_array: np.ndarray,
    light_lines: Sequence[Dict[str, float]],
    radiation_guides: Sequence[Dict[str, float]],
    dpi: float,
    threshold: float = 0.3,
    band_width_mm: float = 8.0,
) -> Dict[str, float]:
    """Measure A/B/G/T light–radiation shifts (mm) for a synthetic field image.

    Convention (matching the prototype UI labels):
      A = left, B = right, G = top (gantry), T = bottom (table).

    Samples intensity profiles perpendicular to each light-field edge (guided by
    ``radiation_guides``) and compares detected radiation borders to light
    lines. Educational use only — not clinical.
    """
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    px_per_mm = float(dpi) / 25.4
    band_width_px = float(band_width_mm) * px_per_mm

    light_models = [build_line_model_from_segment(line) for line in light_lines]
    guide_models = [build_line_model_from_segment(line) for line in radiation_guides]
    if any(m is None for m in light_models) or any(m is None for m in guide_models):
        raise ValueError("Invalid light or guide line geometry")

    h, w = image_array.shape[:2]
    image_center = np.array([w / 2.0, h / 2.0], dtype=float)

    light_by_side: Dict[str, Dict[str, Any]] = {}
    for model in light_models:
        assert model is not None
        light_by_side[classify_side_from_line(model, image_center)] = model

    guide_by_side: Dict[str, Dict[str, Any]] = {}
    for model in guide_models:
        assert model is not None
        guide_by_side[classify_side_from_line(model, image_center)] = model

    shifts_px: Dict[str, float] = {}
    for side in ("left", "right", "top", "bottom"):
        if side not in light_by_side or side not in guide_by_side:
            raise ValueError(f"Missing light/guide line for side: {side}")
        light_model = light_by_side[side]
        edge_coord = _edge_coord_from_perpendicular_profile(
            image_array=image_array,
            light_model=light_model,
            guide_model=guide_by_side[side],
            side=side,
            band_width_px=band_width_px,
            target_ratio=threshold,
        )
        if side in ("left", "right"):
            light_coord = float(light_model["center"][0])
        else:
            light_coord = float(light_model["center"][1])
        shifts_px[side] = abs(edge_coord - light_coord)

    return {
        "A": shifts_px["left"] / px_per_mm,
        "B": shifts_px["right"] / px_per_mm,
        "G": shifts_px["top"] / px_per_mm,
        "T": shifts_px["bottom"] / px_per_mm,
        "left": shifts_px["left"] / px_per_mm,
        "right": shifts_px["right"] / px_per_mm,
        "top": shifts_px["top"] / px_per_mm,
        "bottom": shifts_px["bottom"] / px_per_mm,
        "match_mm": max(shifts_px.values()) / px_per_mm,
    }
