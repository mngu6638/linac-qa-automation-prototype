"""
Shared sorting helpers for equipment service reports.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Iterable, List


def _normalize_text(value: str) -> str:
    # Accent-insensitive + case-insensitive normalization for stable sorting.
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks.casefold().strip()


def _natural_tokens(value: str) -> List[object]:
    tokens = re.split(r"(\d+)", _normalize_text(value))
    result: List[object] = []
    for token in tokens:
        if not token:
            continue
        if token.isdigit():
            result.append(int(token))
        else:
            result.append(token)
    return result


def get_report_equipment_name(report) -> str:
    if getattr(report, "linac", None):
        return report.linac.name or ""
    if getattr(report, "device", None):
        return report.device.name or ""
    return "N/A"


def get_report_equipment_key(report):
    """
    Stable equipment identity for grouping/merging:
    - ('linac', <id>)
    - ('device', <id>)
    - ('none', 0)
    """
    if getattr(report, "linac_id", None):
        return ("linac", int(report.linac_id))
    if getattr(report, "device_id", None):
        return ("device", int(report.device_id))
    return ("none", 0)


def get_report_category_rank(report) -> int:
    if getattr(report, "linac", None):
        return 0  # LINAC first
    device = getattr(report, "device", None)
    if device is None:
        return 2  # Unknown treated as "Other"
    if getattr(device, "category", "") == "others":
        return 2  # Other category last
    return 1  # Other device categories in the middle


def service_report_sort_key(report):
    equipment_name = get_report_equipment_name(report)
    report_date = getattr(report, "date", None) or date.min
    report_id = getattr(report, "id", 0)
    return (
        get_report_category_rank(report),
        _natural_tokens(equipment_name),
        report_date,
        report_id,
    )


def _to_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _periodic_section_rank(report, date_from=None, date_to=None) -> int:
    """
    Section order for periodic report per equipment:
    0 = errors in selected time range
    1 = pending errors outside selected time range
    2 = temporary errors outside selected time range
    3 = fallback
    """
    start = _to_date(date_from)
    end = _to_date(date_to)
    if start and end and start > end:
        start, end = end, start

    report_date = getattr(report, "date", None)
    in_range = bool(start and end and report_date and start <= report_date <= end)
    if in_range:
        return 0

    status = getattr(report, "status", "")
    if status == "pending":
        return 1
    if status == "temporary":
        return 2
    return 3


def sort_service_reports(reports: Iterable, date_from=None, date_to=None):
    def _key(report):
        equipment_name = get_report_equipment_name(report)
        report_date = getattr(report, "date", None) or date.min
        report_id = getattr(report, "id", 0)
        created_at = getattr(report, "created_at", None) or report_date
        return (
            get_report_category_rank(report),
            _natural_tokens(equipment_name),
            _periodic_section_rank(report, date_from=date_from, date_to=date_to),
            report_date,
            created_at,
            report_id,
        )

    return sorted(reports, key=_key)

