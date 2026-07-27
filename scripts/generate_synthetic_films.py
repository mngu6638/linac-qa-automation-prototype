#!/usr/bin/env python3
"""Generate synthetic educational film PNGs and expected geometry JSON.

Writes into sample_data/films/. No hospital / clinical data.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "sample_data" / "films"

DPI = 150
SIZE = 800
BG = 220
FIELD = 40
SPOKE = 30


def mm_to_px(mm: float, dpi: float = DPI) -> float:
    return mm * dpi / 25.4


def save_png(array: np.ndarray, path: Path, dpi: int = DPI) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(array.astype(np.uint8), mode="L")
    img.save(path, dpi=(dpi, dpi))


def generate_fieldsize() -> dict:
    """Dark radiation square on bright bg with known left-edge inset."""
    left_shift_mm = 3.0
    left_shift_px = mm_to_px(left_shift_mm)

    # Conceptual light field (not drawn): 400x400 centered box.
    light = {"left": 200.0, "right": 600.0, "top": 200.0, "bottom": 600.0}
    radiation = {
        "left": light["left"] + left_shift_px,
        "right": light["right"],
        "top": light["top"],
        "bottom": light["bottom"],
    }

    arr = np.full((SIZE, SIZE), BG, dtype=np.uint8)
    x0 = int(round(radiation["left"]))
    x1 = int(round(radiation["right"]))
    y0 = int(round(radiation["top"]))
    y1 = int(round(radiation["bottom"]))
    arr[y0:y1, x0:x1] = FIELD
    path = OUT_DIR / "fieldsize_synthetic.png"
    save_png(arr, path)

    # Guide lines slightly outside radiation edges; light lines at light box.
    light_lines = [
        {"side": "left", "x1": light["left"], "y1": 220, "x2": light["left"], "y2": 580},
        {"side": "right", "x1": light["right"], "y1": 220, "x2": light["right"], "y2": 580},
        {"side": "top", "x1": 220, "y1": light["top"], "x2": 580, "y2": light["top"]},
        {"side": "bottom", "x1": 220, "y1": light["bottom"], "x2": 580, "y2": light["bottom"]},
    ]
    # Radiation guides placed ~halfway between light and expected radiation edge
    # for left; coincident for other sides (zero shift).
    mid_left = (light["left"] + radiation["left"]) / 2.0
    radiation_guides = [
        {"side": "left", "x1": mid_left, "y1": 220, "x2": mid_left, "y2": 580},
        {"side": "right", "x1": radiation["right"], "y1": 220, "x2": radiation["right"], "y2": 580},
        {"side": "top", "x1": 220, "y1": radiation["top"], "x2": 580, "y2": radiation["top"]},
        {
            "side": "bottom",
            "x1": 220,
            "y1": radiation["bottom"],
            "x2": 580,
            "y2": radiation["bottom"],
        },
    ]

    return {
        "filename": path.name,
        "dpi": DPI,
        "size_px": [SIZE, SIZE],
        "light_field_px": light,
        "radiation_field_px": radiation,
        "expected_shifts_mm": {
            "A": left_shift_mm,
            "B": 0.0,
            "G": 0.0,
            "T": 0.0,
            "left": left_shift_mm,
            "right": 0.0,
            "top": 0.0,
            "bottom": 0.0,
        },
        "light_lines": light_lines,
        "radiation_guides": radiation_guides,
        "analysis_threshold": 0.3,
        "band_width_mm": 8.0,
        "tolerance_mm": 0.5,
    }


def _draw_spokes(
    arr: np.ndarray,
    rad_cx: float,
    rad_cy: float,
    length: float = 320.0,
    half_width_px: float = 28.0,
) -> None:
    """Draw 8 dark thick spokes through radiation isocenter at 45° intervals.

    Spokes are drawn as filled polygons wide enough (~>10°) at the analysis
    radius so intensity-threshold valley detection can resolve them.
    """
    img = Image.fromarray(arr, mode="L")
    draw = ImageDraw.Draw(img)
    for i in range(8):
        angle = math.radians(i * 45.0)
        # Unit along spoke and perpendicular (image coords, +Y down).
        ux, uy = math.cos(angle), math.sin(angle)
        px, py = -uy, ux
        # Quad corners: long thin rectangle through radiation isocenter.
        corners = [
            (rad_cx - ux * length + px * half_width_px, rad_cy - uy * length + py * half_width_px),
            (rad_cx + ux * length + px * half_width_px, rad_cy + uy * length + py * half_width_px),
            (rad_cx + ux * length - px * half_width_px, rad_cy + uy * length - py * half_width_px),
            (rad_cx - ux * length - px * half_width_px, rad_cy - uy * length - py * half_width_px),
        ]
        draw.polygon(corners, fill=SPOKE)
    arr[:, :] = np.asarray(img, dtype=np.uint8)


def generate_starshot(
    filename: str,
    offset_mm_x: float,
    offset_mm_y: float,
    mech_center: tuple[float, float] = (400.0, 400.0),
    analysis_radius_px: float = 250.0,
) -> dict:
    arr = np.full((SIZE, SIZE), BG, dtype=np.uint8)
    ox = mm_to_px(offset_mm_x)
    oy = mm_to_px(offset_mm_y)
    rad_cx = mech_center[0] + ox
    rad_cy = mech_center[1] + oy
    _draw_spokes(arr, rad_cx, rad_cy)
    path = OUT_DIR / filename
    save_png(arr, path)

    displacement_mm = math.sqrt(offset_mm_x**2 + offset_mm_y**2)
    return {
        "filename": path.name,
        "dpi": DPI,
        "size_px": [SIZE, SIZE],
        "mechanical_center_px": list(mech_center),
        "radiation_isocenter_px": [rad_cx, rad_cy],
        "offset_mm": {"x": offset_mm_x, "y": offset_mm_y},
        "expected_displacement_mm": displacement_mm,
        "expected_circle_diameter_mm": 0.0,
        "analysis_radius_px": analysis_radius_px,
        "n_spokes": 8,
        "tolerance_displacement_mm": 0.75,
        "tolerance_diameter_mm": 1.5,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    field = generate_fieldsize()
    collimator = generate_starshot(
        "collimator_starshot_synthetic.png",
        offset_mm_x=2.0,
        offset_mm_y=1.0,
    )
    gantry = generate_starshot(
        "gantry_starshot_synthetic.png",
        offset_mm_x=-1.5,
        offset_mm_y=2.5,
    )

    expected = {
        "note": "Synthetic educational films only — not clinical data.",
        "dpi": DPI,
        "fieldsize": field,
        "collimator_starshot": collimator,
        "gantry_starshot": gantry,
    }
    json_path = OUT_DIR / "expected_geometry.json"
    json_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'fieldsize_synthetic.png'}")
    print(f"Wrote {OUT_DIR / 'collimator_starshot_synthetic.png'}")
    print(f"Wrote {OUT_DIR / 'gantry_starshot_synthetic.png'}")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
