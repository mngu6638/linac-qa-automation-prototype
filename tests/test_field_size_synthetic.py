"""Synthetic field-size analysis tests against expected_geometry.json."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from QAID_Manager.analysis.field_size import measure_field_shifts_from_synthetic

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


def test_field_size_shifts_match_expected(expected):
    fs = expected["fieldsize"]
    image_path = FILMS / fs["filename"]
    assert image_path.exists(), f"Missing synthetic film: {image_path}"

    arr = np.asarray(Image.open(image_path).convert("L"), dtype=np.float64)
    light_lines = [{k: v for k, v in line.items() if k != "side"} for line in fs["light_lines"]]
    guides = [{k: v for k, v in line.items() if k != "side"} for line in fs["radiation_guides"]]

    result = measure_field_shifts_from_synthetic(
        image_array=arr,
        light_lines=light_lines,
        radiation_guides=guides,
        dpi=fs["dpi"],
        threshold=fs.get("analysis_threshold", 0.3),
        band_width_mm=fs.get("band_width_mm", 8.0),
    )

    tol = float(fs.get("tolerance_mm", 0.5))
    exp = fs["expected_shifts_mm"]
    assert result["A"] == pytest.approx(exp["A"], abs=tol)
    assert result["B"] == pytest.approx(exp["B"], abs=tol)
    assert result["G"] == pytest.approx(exp["G"], abs=tol)
    assert result["T"] == pytest.approx(exp["T"], abs=tol)
