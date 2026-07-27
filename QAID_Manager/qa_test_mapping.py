"""
QA test field mapping and display grouping for Statistics and schedule views.

Film tests store values in test_12/13/14 with semantics that do not match
QATest.order_index. This module centralizes that mapping.
"""
from __future__ import annotations

from typing import Optional

from .models import QATest

# Storage field index (1-20) -> QATest order_index used for display/tolerance name
FILM_FIELD_TO_ORDER_INDEX = {12: 14, 13: 13, 14: 12}

# QATest order_index -> storage field name on QARecord
ORDER_INDEX_TO_STORAGE_FIELD = {
    12: "test_14",
    13: "test_13",
    14: "test_12",
}

BEAM_ORDER_INDICES = frozenset(range(15, 21))

BEAM_TEST_GROUPS = {
    "output": {15, 20},
    "symmetry": {17},
    "flatness": {18},
    "quality": {16},
    "mu_linearity": {19},
}

DISPLAY_GROUP_LABELS = {
    "mechanical": "Mechanical QA",
    "film": "Film QA",
    "isocenter": "Isocenter QA",
    "beam_output": "Beam Output",
    "beam_symmetry_flatness": "Symmetry / Flatness",
    "beam_quality": "Beam Quality",
    "beam_mu_linearity": "MU Linearity",
    "dose_calculation": "Dose Calculation",
    "other": "Other QA Tests",
}

CATEGORY_FILTER_MAP = {
    "all": None,
    "mechanical": "mechanical",
    "beam": "beam",
    "film": "film",
    "isocenter": "isocenter",
}

CATEGORY_SECTION_LABELS = {
    "mechanical": "Mechanical QA",
    "film": "Film QA",
    "isocenter": "Isocenter QA",
    "beam": "Beam / Dose QA",
}

CATEGORY_SECTION_ORDER = ["mechanical", "isocenter", "film", "beam"]


def get_storage_field(order_index: int) -> str:
    """Return QARecord field name for a QATest order_index."""
    return ORDER_INDEX_TO_STORAGE_FIELD.get(order_index, f"test_{order_index:02d}")


def get_storage_field_index(order_index: int) -> int:
    """Return numeric test field index (1-20) for notes/tolerance lookup."""
    field = get_storage_field(order_index)
    return int(field.split("_")[1])


def get_display_order_index(field_index: int) -> int:
    """Map storage field index to QATest order_index for naming."""
    return FILM_FIELD_TO_ORDER_INDEX.get(field_index, field_index)


def get_test_name_for_field(field_index: int, ordered_tests: Optional[list] = None) -> str:
    """Resolve display name for a storage field index."""
    display_oi = get_display_order_index(field_index)
    if ordered_tests is None:
        test = QATest.objects.filter(order_index=display_oi, is_active=True).first()
        return test.name if test else f"Test {field_index:02d}"
    match = next((t for t in ordered_tests if t.order_index == display_oi), None)
    return match.name if match else f"Test {field_index:02d}"


def get_display_group(qa_test: QATest) -> tuple[str, str]:
    """Return (group_key, clinical_label) for UI grouping."""
    oi = qa_test.order_index
    if qa_test.test_type == "mechanical":
        return "mechanical", DISPLAY_GROUP_LABELS["mechanical"]
    if qa_test.test_type == "film":
        return "film", DISPLAY_GROUP_LABELS["film"]
    if qa_test.test_type == "isocenter":
        return "isocenter", DISPLAY_GROUP_LABELS["isocenter"]
    if qa_test.test_type == "beam":
        if oi in BEAM_TEST_GROUPS["output"]:
            return "beam_output", DISPLAY_GROUP_LABELS["beam_output"]
        if oi in BEAM_TEST_GROUPS["symmetry"] or oi in BEAM_TEST_GROUPS["flatness"]:
            return "beam_symmetry_flatness", DISPLAY_GROUP_LABELS["beam_symmetry_flatness"]
        if oi in BEAM_TEST_GROUPS["quality"]:
            return "beam_quality", DISPLAY_GROUP_LABELS["beam_quality"]
        if oi in BEAM_TEST_GROUPS["mu_linearity"]:
            return "beam_mu_linearity", DISPLAY_GROUP_LABELS["beam_mu_linearity"]
    return "other", DISPLAY_GROUP_LABELS["other"]


def beam_test_in_group(order_index: int, group: str) -> bool:
    """Check if beam test order_index belongs to a beam_test_group filter."""
    if group in ("", "all", None):
        return True
    allowed = BEAM_TEST_GROUPS.get(group, set())
    return order_index in allowed


def is_beam_test(qa_test: QATest) -> bool:
    return qa_test.test_type == "beam" or qa_test.order_index in BEAM_ORDER_INDICES
