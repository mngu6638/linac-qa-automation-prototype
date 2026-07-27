"""Synthetic starshot analysis tests against expected_geometry.json."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from QAID_Manager.analysis.starshot import analyze_starshot

ROOT = Path(__file__).resolve().parents[1]
FILMS = ROOT / "sample_data" / "films"
EXPECTED_PATH = FILMS / "expected_geometry.json"


@pytest.fixture(scope="module")
def expected():
    if not EXPECTED_PATH.exists():
        pytest.skip(
            "expected_geometry.json missing — run scripts/generate_synthetic_films.py"
        )
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", ["collimator_starshot", "gantry_starshot"])
def test_starshot_displacement_within_tolerance(expected, key):
    meta = expected[key]
    image_path = FILMS / meta["filename"]
    assert image_path.exists(), f"Missing synthetic film: {image_path}"

    arr = np.asarray(Image.open(image_path).convert("L"), dtype=np.float64)
    cx, cy = meta["mechanical_center_px"]
    result = analyze_starshot(
        image_array=arr,
        center_x=float(cx),
        center_y=float(cy),
        radius=float(meta["analysis_radius_px"]),
        dpi=float(meta["dpi"]),
    )

    disp_tol = float(meta.get("tolerance_displacement_mm", 0.75))
    diam_tol = float(meta.get("tolerance_diameter_mm", 1.5))
    assert result["displacement_mm"] == pytest.approx(
        meta["expected_displacement_mm"], abs=disp_tol
    )
    assert result["circle_diameter_mm"] == pytest.approx(
        meta["expected_circle_diameter_mm"], abs=diam_tol
    )

    # Radiation isocenter should be near the ground-truth offset.
    rx, ry = meta["radiation_isocenter_px"]
    px_tol = disp_tol * meta["dpi"] / 25.4
    assert result["radiation_isocenter"][0] == pytest.approx(rx, abs=px_tol)
    assert result["radiation_isocenter"][1] == pytest.approx(ry, abs=px_tol)
