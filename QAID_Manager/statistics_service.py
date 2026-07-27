"""
Statistics service for QAID Manager v1.3.

Read-only analysis of QA records: overview, trends, classifications, exports.
"""
from __future__ import annotations

import csv
import io
import math
import statistics as stats_module
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from .models import Linac, QARecord, QATest, QATestNote
from .qa_test_mapping import (
    CATEGORY_FILTER_MAP,
    CATEGORY_SECTION_LABELS,
    CATEGORY_SECTION_ORDER,
    DISPLAY_GROUP_LABELS,
    beam_test_in_group,
    get_display_group,
    get_storage_field,
    get_storage_field_index,
    is_beam_test,
)
from .services import QAService

ACTION_DELTA = 0.5
MINI_SERIES_MAX = 24
REVIEW_LIST_LIMIT = 50

VIEW_MODES = (
    "overview",
    "single_test",
    "linac_all_tests",
    "category_trends",
    "beam_energy",
)

CLASSIFICATION_NORMAL = "normal"
CLASSIFICATION_WARNING = "warning"
CLASSIFICATION_FAILED = "failed"
CLASSIFICATION_MISSING = "missing"

TREND_STABLE = "Stable"
TREND_WATCH = "Watch"
TREND_ACTION = "Action"
TREND_INSUFFICIENT = "Insufficient data"
TREND_NO_DATA = "No data"


@dataclass
class StatisticsFilters:
    view_mode: str = "overview"
    date_preset: str = "last_12_months"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    linac_ids: List[int] = field(default_factory=list)
    test_category: str = "all"
    qa_test_id: Optional[int] = None
    energy: Optional[str] = None
    beam_test_group: str = "all"
    result_status: str = "all"
    include_inactive_linacs: bool = False
    include_drafts: bool = False
    show_only_with_data: bool = False

    @classmethod
    def from_request(cls, request) -> "StatisticsFilters":
        get = request.GET
        linac_raw = get.getlist("linac_ids") or get.getlist("linac_ids[]")
        linac_ids = []
        for x in linac_raw:
            try:
                linac_ids.append(int(x))
            except (TypeError, ValueError):
                pass
        qa_test_id = get.get("qa_test_id")
        return cls(
            view_mode=get.get("view_mode", "overview"),
            date_preset=get.get("date_preset", "last_12_months"),
            date_from=_parse_date(get.get("date_from")),
            date_to=_parse_date(get.get("date_to")),
            linac_ids=linac_ids,
            test_category=get.get("test_category", "all"),
            qa_test_id=int(qa_test_id) if qa_test_id else None,
            energy=get.get("energy") or None,
            beam_test_group=get.get("beam_test_group", "all"),
            result_status=get.get("result_status", "all"),
            include_inactive_linacs=get.get("include_inactive_linacs") == "1",
            include_drafts=get.get("include_drafts") == "1",
            show_only_with_data=get.get("show_only_with_data") == "1",
        )

    def resolved_dates(self) -> Tuple[date, date]:
        if self.date_from and self.date_to:
            return self.date_from, self.date_to
        return resolve_date_preset(self.date_preset)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        parts = value.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def resolve_date_preset(preset: str) -> Tuple[date, date]:
    today = timezone.now().date()
    if preset == "last_3_months":
        return subtract_months(today, 3), today
    if preset == "last_6_months":
        return subtract_months(today, 6), today
    if preset == "year_to_date":
        return date(today.year, 1, 1), today
    if preset == "previous_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if preset == "custom":
        return subtract_months(today, 12), today
    # default last_12_months
    return subtract_months(today, 12), today


def subtract_months(from_date: date, months: int) -> date:
    month = from_date.month - months
    year = from_date.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(from_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class StatisticsService:
    """Read-only QA statistics and trend analysis."""

    @staticmethod
    def validate_filters(filters: StatisticsFilters) -> Optional[str]:
        if filters.view_mode not in VIEW_MODES:
            return f"Invalid view_mode: {filters.view_mode}"
        if filters.view_mode == "single_test" and not filters.qa_test_id:
            return "QA test is required for Single Test Trend mode."
        if filters.view_mode == "linac_all_tests" and len(filters.linac_ids) != 1:
            return "Exactly one LINAC is required for All Tests mode."
        if filters.view_mode == "category_trends" and filters.test_category in ("all", ""):
            return "Test category is required for Category Trends mode."
        if filters.view_mode == "beam_energy" and not filters.energy:
            return "Energy is required for Beam Energy Trends mode."
        if filters.view_mode == "single_test":
            test = QATest.objects.filter(pk=filters.qa_test_id).first()
            if test and is_beam_test(test) and not filters.energy:
                return "Energy is required for beam-related tests."
        return None

    @staticmethod
    def get_linacs(filters: StatisticsFilters) -> List[Linac]:
        qs = Linac.objects.all().order_by("name")
        if not filters.include_inactive_linacs:
            qs = qs.filter(is_active=True)
        if filters.linac_ids:
            qs = qs.filter(pk__in=filters.linac_ids)
        return list(qs)

    @staticmethod
    def get_active_tests(category: str = "all") -> List[QATest]:
        qs = QATest.objects.filter(is_active=True).order_by("test_type", "order_index")
        cat = CATEGORY_FILTER_MAP.get(category)
        if cat:
            qs = qs.filter(test_type=cat)
        return list(qs)

    @staticmethod
    def build_queryset(filters: StatisticsFilters):
        date_from, date_to = filters.resolved_dates()
        linacs = StatisticsService.get_linacs(filters)
        linac_ids = [l.id for l in linacs]
        if not linac_ids:
            return QARecord.objects.none()
        qs = QARecord.objects.filter(
            date_performed__gte=date_from,
            date_performed__lte=date_to,
            linac_id__in=linac_ids,
        ).select_related("linac", "status", "performed_by").prefetch_related(
            "test_notes", "film_analyses", "dose_calculations"
        )
        if not filters.include_drafts:
            qs = qs.filter(is_draft=False)
        return qs.order_by("date_performed")

    @staticmethod
    def get_threshold_meta(qa_test: QATest) -> Tuple[float, str, float, float]:
        configured_tolerance, tol_unit = QAService.get_tolerance_for_test(
            qa_test.order_index
        )
        if qa_test.tolerance_value is not None:
            configured_tolerance = float(qa_test.tolerance_value)
        if qa_test.tolerance_unit:
            tol_unit = qa_test.tolerance_unit
        warning = configured_tolerance
        action = configured_tolerance + ACTION_DELTA
        return configured_tolerance, tol_unit, warning, action

    @staticmethod
    def classify_value(
        value: float,
        warning_threshold: float,
        order_index: int,
        baseline: float = 0.0,
        action_threshold: Optional[float] = None,
    ) -> str:
        if order_index == 19:
            return CLASSIFICATION_FAILED if value <= 0.99 else CLASSIFICATION_NORMAL
        if action_threshold is None:
            action_threshold = warning_threshold + ACTION_DELTA
        abs_dev = abs(value - baseline)
        if abs_dev > action_threshold:
            return CLASSIFICATION_FAILED
        if abs_dev > warning_threshold:
            return CLASSIFICATION_WARNING
        return CLASSIFICATION_NORMAL

    @staticmethod
    def extract_point(
        qa_record: QARecord,
        qa_test: QATest,
        energy: Optional[str] = None,
        test_notes_cache: Optional[dict] = None,
    ) -> Optional[Dict[str, Any]]:
        order_index = qa_test.order_index
        value = None
        source_type = "scalar"
        point_energy = energy

        if is_beam_test(qa_test):
            beam = qa_record.beam_test_results or {}
            if not energy:
                return None
            energy_data = beam.get(energy) or beam.get(str(energy))
            if not energy_data:
                return None
            key = f"test_{order_index:02d}"
            raw = energy_data.get(key)
            if raw is None:
                return None
            source_type = "beam_json"
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return None
        else:
            field = get_storage_field(order_index)
            raw = getattr(qa_record, field, None)
            if raw is None:
                return None
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return None
            if qa_test.test_type == "film":
                source_type = "film"
            elif qa_test.test_type == "isocenter":
                source_type = "scalar"

        configured_tolerance, unit, warning, action = (
            StatisticsService.get_threshold_meta(qa_test)
        )
        classification = StatisticsService.classify_value(
            value,
            warning,
            order_index,
            action_threshold=action,
        )
        note = ""
        if test_notes_cache is not None:
            note = test_notes_cache.get(get_storage_field_index(order_index), "")
        else:
            tn = qa_record.test_notes.filter(
                test_number=get_storage_field_index(order_index)
            ).first()
            note = tn.note_text if tn else ""

        performer = ""
        if qa_record.performed_by:
            u = qa_record.performed_by
            performer = f"{u.last_name} {u.first_name}".strip() or u.username

        return {
            "qa_record_id": qa_record.id,
            "date": qa_record.date_performed.isoformat(),
            "linac_id": qa_record.linac_id,
            "linac_name": qa_record.linac.name if qa_record.linac else "",
            "test_id": qa_test.id,
            "test_name": qa_test.name,
            "order_index": order_index,
            "category": qa_test.test_type,
            "energy": point_energy,
            "value": value,
            "unit": unit,
            "source_type": source_type,
            "status_name": qa_record.status.name if qa_record.status else "",
            "note": note,
            "performer": performer,
            "configured_tolerance": configured_tolerance,
            "warning_threshold": warning,
            "action_threshold": action,
            "baseline": 0.0,
            "classification": classification,
        }

    @staticmethod
    def _notes_cache(qa_record: QARecord) -> dict:
        return {n.test_number: n.note_text for n in qa_record.test_notes.all()}

    @staticmethod
    def collect_points(
        queryset,
        tests: List[QATest],
        energy: Optional[str] = None,
        linac_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        points = []
        for record in queryset:
            if linac_id and record.linac_id != linac_id:
                continue
            notes = StatisticsService._notes_cache(record)
            for test in tests:
                energies_to_try = [energy] if energy else [None]
                if is_beam_test(test) and not energy:
                    beam = record.beam_test_results or {}
                    energies_to_try = list(beam.keys()) if beam else []
                for en in energies_to_try:
                    pt = StatisticsService.extract_point(
                        record, test, energy=en, test_notes_cache=notes
                    )
                    if pt:
                        points.append(pt)
        return points

    @staticmethod
    def compute_trend_label(points: List[Dict[str, Any]]) -> str:
        if not points:
            return TREND_NO_DATA
        if len(points) < 3:
            return TREND_INSUFFICIENT
        failures = sum(
            1 for p in points if p["classification"] == CLASSIFICATION_FAILED
        )
        warnings = sum(
            1 for p in points if p["classification"] == CLASSIFICATION_WARNING
        )
        if failures > 0:
            return TREND_ACTION
        if warnings >= 3:
            return TREND_ACTION
        if warnings > 0:
            return TREND_WATCH
        values = [p["value"] for p in points]
        dates = [p["date"] for p in points]
        try:
            base = date.fromisoformat(dates[0])
            xs = [(date.fromisoformat(d) - base).days for d in dates]
            slope = _linear_slope(xs, values)
            warning = points[0].get("warning_threshold", 1.0) or 1.0
            if abs(slope) > warning * 0.05:
                return TREND_WATCH
        except (ValueError, TypeError):
            pass
        return TREND_STABLE

    @staticmethod
    def consecutive_warnings(points: List[Dict[str, Any]]) -> int:
        sorted_pts = sorted(points, key=lambda p: p["date"])
        max_run = run = 0
        for p in sorted_pts:
            if p["classification"] == CLASSIFICATION_WARNING:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
        return max_run

    @staticmethod
    def build_trend_summary(
        points: List[Dict[str, Any]],
        qa_test: QATest,
        energy: Optional[str] = None,
        linac_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        group_key, group_label = get_display_group(qa_test)
        display_name = qa_test.name
        if energy:
            display_name = f"{qa_test.name} {energy}"

        if not points:
            return {
                "test_id": qa_test.id,
                "test_name": display_name,
                "base_test_name": qa_test.name,
                "order_index": qa_test.order_index,
                "category": qa_test.test_type,
                "display_group": group_key,
                "display_group_label": group_label,
                "energy": energy,
                "unit": qa_test.tolerance_unit,
                "configured_tolerance": qa_test.tolerance_value,
                "warning_threshold": float(qa_test.tolerance_value or 0.0),
                "action_threshold": float(qa_test.tolerance_value or 0.0) + ACTION_DELTA,
                "latest_value": None,
                "latest_date": None,
                "latest_classification": CLASSIFICATION_MISSING,
                "warning_count": 0,
                "failure_count": 0,
                "point_count": 0,
                "trend_label": TREND_NO_DATA,
                "last_qa_date": None,
                "has_data": False,
                "mini_series": [],
                "linac_summaries": [],
            }

        configured_tolerance, unit, warning, action = (
            StatisticsService.get_threshold_meta(qa_test)
        )
        sorted_pts = sorted(points, key=lambda p: p["date"])
        latest = sorted_pts[-1]
        values = [p["value"] for p in points]
        mini = sorted_pts[-MINI_SERIES_MAX:]
        mini_series = [{"date": p["date"], "value": p["value"]} for p in mini]

        summary = {
            "test_id": qa_test.id,
            "test_name": display_name,
            "base_test_name": qa_test.name,
            "order_index": qa_test.order_index,
            "category": qa_test.test_type,
            "display_group": group_key,
            "display_group_label": group_label,
            "energy": energy,
            "unit": unit,
            "configured_tolerance": configured_tolerance,
            "warning_threshold": warning,
            "action_threshold": action,
            "latest_value": latest["value"],
            "latest_date": latest["date"],
            "latest_classification": latest["classification"],
            "warning_count": sum(
                1 for p in points if p["classification"] == CLASSIFICATION_WARNING
            ),
            "failure_count": sum(
                1 for p in points if p["classification"] == CLASSIFICATION_FAILED
            ),
            "point_count": len(points),
            "trend_label": StatisticsService.compute_trend_label(points),
            "last_qa_date": latest["date"],
            "has_data": True,
            "mini_series": mini_series,
            "linac_summaries": [],
        }

        if linac_ids and len(linac_ids) > 1:
            by_linac = defaultdict(list)
            for p in points:
                by_linac[p["linac_id"]].append(p)
            for lid, lpts in by_linac.items():
                llatest = sorted(lpts, key=lambda x: x["date"])[-1]
                summary["linac_summaries"].append({
                    "linac_id": lid,
                    "linac_name": llatest["linac_name"],
                    "latest_value": llatest["value"],
                    "trend_label": StatisticsService.compute_trend_label(lpts),
                    "warning_count": sum(
                        1 for p in lpts
                        if p["classification"] == CLASSIFICATION_WARNING
                    ),
                    "failure_count": sum(
                        1 for p in lpts
                        if p["classification"] == CLASSIFICATION_FAILED
                    ),
                })
        return summary

    @staticmethod
    def count_missing_months(
        linacs: List[Linac], date_from: date, date_to: date, include_drafts: bool
    ) -> int:
        missing = 0
        months = _iter_months(date_from, date_to)
        for linac in linacs:
            for y, m in months:
                start = date(y, m, 1)
                end = date(y, m, monthrange(y, m)[1])
                qs = QARecord.objects.filter(
                    linac=linac,
                    date_performed__gte=start,
                    date_performed__lte=end,
                )
                if not include_drafts:
                    qs = qs.filter(is_draft=False)
                if not qs.exists():
                    missing += 1
        return missing

    @staticmethod
    def build_overview(filters: StatisticsFilters) -> Dict[str, Any]:
        date_from, date_to = filters.resolved_dates()
        linacs = StatisticsService.get_linacs(filters)
        tests = StatisticsService.get_active_tests(filters.test_category)
        queryset = StatisticsService.build_queryset(filters)
        all_points = StatisticsService.collect_points(queryset, tests)

        records_count = queryset.count()
        linac_count = len({p["linac_id"] for p in all_points}) or len(linacs)

        warning_tests = set()
        failed_tests = set()
        for p in all_points:
            key = (p["test_id"], p["linac_id"], p.get("energy"))
            if p["classification"] == CLASSIFICATION_WARNING:
                warning_tests.add(key)
            elif p["classification"] == CLASSIFICATION_FAILED:
                failed_tests.add(key)

        linac_scores = defaultdict(lambda: {"warnings": 0, "failures": 0})
        test_scores = defaultdict(lambda: {"warnings": 0, "failures": 0})
        for p in all_points:
            if p["classification"] == CLASSIFICATION_WARNING:
                linac_scores[p["linac_id"]]["warnings"] += 1
                test_scores[p["test_id"]]["warnings"] += 1
            elif p["classification"] == CLASSIFICATION_FAILED:
                linac_scores[p["linac_id"]]["failures"] += 1
                test_scores[p["test_id"]]["failures"] += 1

        most_unstable_linac = ""
        if linac_scores:
            best_id = max(
                linac_scores,
                key=lambda k: linac_scores[k]["warnings"]
                + linac_scores[k]["failures"],
            )
            most_unstable_linac = next(
                (l.name for l in linacs if l.id == best_id), ""
            )

        most_unstable_test = ""
        if test_scores:
            best_tid = max(
                test_scores,
                key=lambda k: test_scores[k]["warnings"]
                + test_scores[k]["failures"],
            )
            t = QATest.objects.filter(pk=best_tid).first()
            most_unstable_test = t.name if t else ""

        matrix = StatisticsService._build_matrix(
            all_points, tests, linacs
        )
        review_list = StatisticsService._build_review_list(all_points)
        charts = StatisticsService._build_overview_charts(
            matrix,
            all_points,
            linacs,
            date_from,
            date_to,
            filters.include_drafts,
            review_list,
        )

        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "cards": {
                "records_included": records_count,
                "linacs_included": linac_count,
                "tests_with_warnings": len(warning_tests),
                "tests_with_failures": len(failed_tests),
                "missing_qa_periods": StatisticsService.count_missing_months(
                    linacs, date_from, date_to, filters.include_drafts
                ),
                "most_unstable_linac": most_unstable_linac or "—",
                "most_unstable_test": most_unstable_test or "—",
            },
            "matrix": matrix,
            "review_list": review_list,
            "charts": charts,
        }

    @staticmethod
    def _build_matrix(
        points: List[Dict],
        tests: List[QATest],
        linacs: List[Linac],
    ) -> Dict[str, Any]:
        cell_map = {}
        for p in points:
            key = (p["test_id"], p["linac_id"])
            prev = cell_map.get(key)
            rank = _classification_rank(p["classification"])
            if prev is None or rank > prev[0]:
                cell_map[key] = (rank, p["classification"])

        rows = []
        for test in tests:
            cells = []
            for linac in linacs:
                key = (test.id, linac.id)
                if key not in cell_map:
                    status = "gray"
                    classification = CLASSIFICATION_MISSING
                else:
                    _, classification = cell_map[key]
                    status = _classification_to_color(classification)
                cells.append({
                    "linac_id": linac.id,
                    "linac_name": linac.name,
                    "test_id": test.id,
                    "test_name": test.name,
                    "status": status,
                    "classification": classification,
                })
            rows.append({
                "test_id": test.id,
                "test_name": test.name,
                "order_index": test.order_index,
                "category": test.test_type,
                "cells": cells,
            })

        sections = []
        rows_by_category = defaultdict(list)
        for row in rows:
            rows_by_category[row["category"]].append(row)
        for cat in CATEGORY_SECTION_ORDER:
            cat_rows = rows_by_category.get(cat, [])
            if cat_rows:
                sections.append({
                    "category": cat,
                    "label": CATEGORY_SECTION_LABELS.get(cat, cat.title()),
                    "rows": cat_rows,
                })
        for cat, cat_rows in rows_by_category.items():
            if cat not in CATEGORY_SECTION_ORDER and cat_rows:
                sections.append({
                    "category": cat,
                    "label": cat.replace("_", " ").title(),
                    "rows": cat_rows,
                })

        return {
            "linacs": [{"id": l.id, "name": l.name} for l in linacs],
            "sections": sections,
            "rows": rows,
        }

    @staticmethod
    def _month_has_qa(linac: Linac, year: int, month: int, include_drafts: bool) -> bool:
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        qs = QARecord.objects.filter(
            linac=linac,
            date_performed__gte=start,
            date_performed__lte=end,
        )
        if not include_drafts:
            qs = qs.filter(is_draft=False)
        return qs.exists()

    @staticmethod
    def _build_management_dashboard(
        matrix: Dict[str, Any],
        points: List[Dict],
        linacs: List[Linac],
        date_from: date,
        date_to: date,
        include_drafts: bool,
        review_list: List[Dict],
    ) -> Dict[str, Any]:
        months = list(_iter_months(date_from, date_to))
        month_labels = [f"{y}-{m:02d}" for y, m in months]
        total_months = len(months) or 1

        linac_completion = []
        heatmap_rows = []
        linacs_missing_qa = []
        linacs_with_failures = []
        failure_counts = defaultdict(int)

        for linac in linacs:
            completed = 0
            month_cells = []
            for y, m in months:
                has_qa = StatisticsService._month_has_qa(
                    linac, y, m, include_drafts
                )
                if has_qa:
                    completed += 1
                month_cells.append({
                    "year": y,
                    "month": m,
                    "label": f"{y}-{m:02d}",
                    "has_qa": has_qa,
                })
            missing_count = total_months - completed
            pct = round(100.0 * completed / total_months, 1)
            if pct >= 100:
                status = "complete"
            elif pct >= 50:
                status = "at_risk"
            else:
                status = "critical"
            entry = {
                "linac_id": linac.id,
                "linac_name": linac.name,
                "completed_months": completed,
                "total_months": total_months,
                "missing_months": missing_count,
                "completion_pct": pct,
                "status": status,
            }
            linac_completion.append(entry)
            heatmap_rows.append({
                "linac_id": linac.id,
                "linac_name": linac.name,
                "months": month_cells,
            })
            if missing_count > 0:
                linacs_missing_qa.append({
                    "linac_id": linac.id,
                    "linac_name": linac.name,
                    "missing_months": missing_count,
                    "completion_pct": pct,
                })
            failures = sum(
                1
                for p in points
                if p["linac_id"] == linac.id
                and p["classification"] == CLASSIFICATION_FAILED
            )
            failure_counts[linac.id] = failures
            if failures > 0:
                linacs_with_failures.append({
                    "linac_id": linac.id,
                    "linac_name": linac.name,
                    "failures": failures,
                })

        linacs_missing_qa.sort(
            key=lambda x: (-x["missing_months"], x["linac_name"])
        )
        linacs_with_failures.sort(key=lambda x: (-x["failures"], x["linac_name"]))

        linac_attention = []
        for linac in linacs:
            warnings = sum(
                1
                for p in points
                if p["linac_id"] == linac.id
                and p["classification"] == CLASSIFICATION_WARNING
            )
            failures = failure_counts[linac.id]
            missing = next(
                (c["missing_months"] for c in linac_completion if c["linac_id"] == linac.id),
                0,
            )
            score = max(
                0,
                100
                - (warnings * 2)
                - (failures * 6)
                - (missing * 4),
            )
            linac_attention.append({
                "linac_id": linac.id,
                "linac_name": linac.name,
                "warnings": warnings,
                "failures": failures,
                "missing_months": missing,
                "reliability_score": round(score, 1),
            })
        linac_attention.sort(key=lambda x: x["reliability_score"])

        status_counts = {"green": 0, "yellow": 0, "red": 0, "gray": 0}
        for section in matrix.get("sections", []):
            for row in section.get("rows", []):
                for cell in row.get("cells", []):
                    status = cell.get("status", "gray")
                    if status in status_counts:
                        status_counts[status] += 1

        total_cells = sum(status_counts.values()) or 1
        overall_completion = (
            round(
                sum(c["completion_pct"] for c in linac_completion)
                / max(len(linac_completion), 1),
                1,
            )
            if linac_completion
            else 0.0
        )
        health_score = round(
            (
                status_counts["green"] * 100
                + status_counts["yellow"] * 50
                + status_counts["red"] * 0
            )
            / total_cells,
            1,
        )
        if health_score >= 85 and overall_completion >= 90:
            health_label = "Good"
        elif health_score >= 60 or overall_completion >= 70:
            health_label = "Watch"
        else:
            health_label = "Action"

        from collections import Counter

        warning_keys = Counter()
        for p in points:
            if p["classification"] == CLASSIFICATION_WARNING:
                key = (p["test_id"], p["linac_id"], p.get("energy") or "")
                warning_keys[key] += 1

        top_failed = [
            {
                "title": f"{r['test_name']}" + (f" ({r['energy']})" if r.get("energy") else ""),
                "linac_name": r["linac_name"],
                "date": r["date"],
                "value": r["value"],
                "unit": r.get("unit", ""),
                "test_id": r["test_id"],
                "linac_id": r["linac_id"],
                "energy": r.get("energy") or "",
            }
            for r in review_list
            if r.get("classification") == CLASSIFICATION_FAILED
        ][:6]

        top_missing = []
        for row in heatmap_rows:
            for cell in row["months"]:
                if not cell["has_qa"]:
                    top_missing.append({
                        "title": f"{row['linac_name']} — {cell['label']}",
                        "linac_name": row["linac_name"],
                        "month": cell["label"],
                        "linac_id": row["linac_id"],
                    })
        top_missing = top_missing[:8]

        top_repeated_warnings = []
        for (test_id, linac_id, energy), count in warning_keys.most_common(6):
            if count < 2:
                continue
            sample = next(
                (
                    p
                    for p in points
                    if p["test_id"] == test_id
                    and p["linac_id"] == linac_id
                    and (p.get("energy") or "") == energy
                ),
                None,
            )
            if not sample:
                continue
            title = sample["test_name"]
            if energy:
                title = f"{title} ({energy})"
            top_repeated_warnings.append({
                "title": title,
                "linac_name": sample["linac_name"],
                "count": count,
                "test_id": test_id,
                "linac_id": linac_id,
                "energy": energy,
            })

        top_attention = (
            linac_attention[0] if linac_attention else None
        )
        all_complete = bool(linac_completion) and all(
            c["completion_pct"] >= 100 for c in linac_completion
        )

        return {
            "summary": {
                "all_linacs_qa_complete": all_complete,
                "linacs_missing_qa": linacs_missing_qa,
                "linacs_with_failures": linacs_with_failures,
                "pending_review_count": len(review_list),
                "top_attention_linac": top_attention,
                "overall_completion_pct": overall_completion,
            },
            "department_health": {
                "status_counts": status_counts,
                "health_score": health_score,
                "health_label": health_label,
                "overall_completion_pct": overall_completion,
            },
            "linac_completion": linac_completion,
            "missing_qa_heatmap": {
                "month_labels": month_labels,
                "rows": heatmap_rows,
            },
            "linac_attention": linac_attention,
            "pending_review": {
                "count": len(review_list),
                "preview": review_list[:6],
            },
            "top_issues": {
                "failed": top_failed,
                "missing": top_missing,
                "repeated_warnings": top_repeated_warnings,
            },
        }

    @staticmethod
    def _build_overview_charts(
        matrix: Dict[str, Any],
        points: List[Dict],
        linacs: List[Linac],
        date_from: date,
        date_to: date,
        include_drafts: bool,
        review_list: List[Dict],
    ) -> Dict[str, Any]:
        status_counts = {"green": 0, "yellow": 0, "red": 0, "gray": 0}
        for section in matrix.get("sections", []):
            for row in section.get("rows", []):
                for cell in row.get("cells", []):
                    status = cell.get("status", "gray")
                    if status in status_counts:
                        status_counts[status] += 1

        linac_attention = []
        for linac in linacs:
            warnings = sum(
                1
                for p in points
                if p["linac_id"] == linac.id
                and p["classification"] == CLASSIFICATION_WARNING
            )
            failures = sum(
                1
                for p in points
                if p["linac_id"] == linac.id
                and p["classification"] == CLASSIFICATION_FAILED
            )
            linac_attention.append({
                "linac_id": linac.id,
                "linac_name": linac.name,
                "warnings": warnings,
                "failures": failures,
            })

        category_attention = []
        for cat in CATEGORY_SECTION_ORDER:
            label = CATEGORY_SECTION_LABELS.get(cat, cat.title())
            warnings = sum(
                1 for p in points
                if p.get("category") == cat
                and p["classification"] == CLASSIFICATION_WARNING
            )
            failures = sum(
                1 for p in points
                if p.get("category") == cat
                and p["classification"] == CLASSIFICATION_FAILED
            )
            category_attention.append({
                "category": cat,
                "label": label,
                "warnings": warnings,
                "failures": failures,
            })

        trend_sparklines = StatisticsService._build_overview_sparklines(points, linacs)
        management = StatisticsService._build_management_dashboard(
            matrix,
            points,
            linacs,
            date_from,
            date_to,
            include_drafts,
            review_list,
        )

        return {
            "status_counts": status_counts,
            "linac_attention": linac_attention,
            "category_attention": category_attention,
            "trend_sparklines": trend_sparklines,
            "management": management,
        }

    @staticmethod
    def _build_overview_sparklines(
        points: List[Dict], linacs: List[Linac], max_series: int = 6
    ) -> List[Dict[str, Any]]:
        """Top attention items with mini time series for overview charts panel."""
        from collections import Counter

        key_counts = Counter()
        for p in points:
            if p["classification"] in (CLASSIFICATION_WARNING, CLASSIFICATION_FAILED):
                key = (p["test_id"], p["linac_id"], p.get("energy") or "")
                key_counts[key] += 1

        series_list = []
        seen = set()
        for (test_id, linac_id, energy), _ in key_counts.most_common(max_series * 2):
            if len(series_list) >= max_series:
                break
            key = (test_id, linac_id, energy)
            if key in seen:
                continue
            seen.add(key)
            pts = [
                p for p in points
                if p["test_id"] == test_id
                and p["linac_id"] == linac_id
                and (p.get("energy") or "") == energy
            ]
            if not pts:
                continue
            pts.sort(key=lambda x: x["date"])
            latest = pts[-1]
            mini = pts[-MINI_SERIES_MAX:]
            title = latest["test_name"]
            if energy:
                title = f"{title} ({energy})"
            series_list.append({
                "title": title,
                "linac_name": latest["linac_name"],
                "classification": latest["classification"],
                "unit": latest.get("unit", ""),
                "mini_series": [
                    {"date": p["date"], "value": p["value"]} for p in mini
                ],
                "test_id": test_id,
                "linac_id": linac_id,
                "energy": energy or None,
            })
        return series_list

    @staticmethod
    def _build_review_list(points: List[Dict]) -> List[Dict]:
        flagged = [
            p
            for p in points
            if p["classification"] in (
                CLASSIFICATION_WARNING,
                CLASSIFICATION_FAILED,
            )
        ]
        flagged.sort(key=lambda p: p["date"], reverse=True)
        result = []
        for p in flagged[:REVIEW_LIST_LIMIT]:
            reason = (
                "Failed"
                if p["classification"] == CLASSIFICATION_FAILED
                else "Warning"
            )
            result.append({
                "date": p["date"],
                "linac_id": p["linac_id"],
                "linac_name": p["linac_name"],
                "test_id": p["test_id"],
                "test_name": p["test_name"],
                "energy": p.get("energy") or "",
                "value": p["value"],
                "unit": p["unit"],
                "reason": reason,
                "qa_record_id": p["qa_record_id"],
                "classification": p["classification"],
            })
        return result

    @staticmethod
    def build_single_test_trend(filters: StatisticsFilters) -> Dict[str, Any]:
        qa_test = QATest.objects.get(pk=filters.qa_test_id)
        queryset = StatisticsService.build_queryset(filters)
        points = StatisticsService.collect_points(
            queryset, [qa_test], energy=filters.energy
        )
        if filters.result_status != "all":
            status_map = {
                "normal": CLASSIFICATION_NORMAL,
                "warning": CLASSIFICATION_WARNING,
                "failed": CLASSIFICATION_FAILED,
            }
            want = status_map.get(filters.result_status)
            if want:
                points = [p for p in points if p["classification"] == want]

        linac_ids = filters.linac_ids or [
            l.id for l in StatisticsService.get_linacs(filters)
        ]
        series_map = defaultdict(list)
        for p in points:
            series_map[p["linac_id"]].append(p)

        series = []
        for lid, pts in series_map.items():
            pts.sort(key=lambda x: x["date"])
            series.append({
                "linac_id": lid,
                "label": pts[0]["linac_name"] if pts else "",
                "points": [
                    {"x": p["date"], "y": p["value"], "meta": p} for p in pts
                ],
            })

        configured_tolerance, unit, warning, action = (
            StatisticsService.get_threshold_meta(qa_test)
        )
        global_summary = StatisticsService._numeric_summary(points)
        per_linac = []
        for lid, pts in series_map.items():
            s = StatisticsService._numeric_summary(pts)
            s["linac_id"] = lid
            s["linac_name"] = pts[0]["linac_name"] if pts else ""
            s["trend_label"] = StatisticsService.compute_trend_label(pts)
            per_linac.append(s)

        table_rows = sorted(points, key=lambda p: p["date"], reverse=True)

        return {
            "test": {
                "id": qa_test.id,
                "name": qa_test.name,
                "order_index": qa_test.order_index,
                "unit": unit,
            },
            "series": series,
            "reference_lines": {
                "baseline": 0.0,
                "upper_warning": warning,
                "lower_warning": -warning,
                "upper_action": action,
                "lower_action": -action,
                "configured_tolerance": configured_tolerance,
                "unit": unit,
                "source": "qa_test_settings",
            },
            "summary": {"global": global_summary, "per_linac": per_linac},
            "table_rows": table_rows,
            "trend_label": StatisticsService.compute_trend_label(points),
        }

    @staticmethod
    def _numeric_summary(points: List[Dict]) -> Dict[str, Any]:
        if not points:
            return {
                "count": 0,
                "latest": None,
                "mean": None,
                "median": None,
                "min": None,
                "max": None,
                "range": None,
                "stdev": None,
                "warning_count": 0,
                "failure_count": 0,
                "consecutive_warnings": 0,
                "days_since_last_qa": None,
                "trend_label": TREND_NO_DATA,
            }
        values = [p["value"] for p in points]
        sorted_pts = sorted(points, key=lambda p: p["date"])
        latest = sorted_pts[-1]
        today = timezone.now().date()
        try:
            last_date = date.fromisoformat(latest["date"])
            days_since = (today - last_date).days
        except ValueError:
            days_since = None
        stdev = stats_module.stdev(values) if len(values) > 1 else 0.0
        return {
            "count": len(points),
            "latest": latest["value"],
            "mean": round(stats_module.mean(values), 4),
            "median": round(stats_module.median(values), 4),
            "min": min(values),
            "max": max(values),
            "range": round(max(values) - min(values), 4),
            "stdev": round(stdev, 4),
            "warning_count": sum(
                1 for p in points if p["classification"] == CLASSIFICATION_WARNING
            ),
            "failure_count": sum(
                1 for p in points if p["classification"] == CLASSIFICATION_FAILED
            ),
            "consecutive_warnings": StatisticsService.consecutive_warnings(points),
            "days_since_last_qa": days_since,
            "trend_label": StatisticsService.compute_trend_label(points),
        }

    @staticmethod
    def build_linac_all_tests_summary(
        filters: StatisticsFilters,
    ) -> Dict[str, Any]:
        linac_id = filters.linac_ids[0]
        linac = Linac.objects.get(pk=linac_id)
        tests = StatisticsService.get_active_tests(filters.test_category)
        queryset = StatisticsService.build_queryset(filters)
        queryset = queryset.filter(linac_id=linac_id)

        summaries = []
        for test in tests:
            if is_beam_test(test):
                energies = _linac_energies(linac)
                for en in energies:
                    pts = StatisticsService.collect_points(
                        queryset, [test], energy=en
                    )
                    s = StatisticsService.build_trend_summary(pts, test, energy=en)
                    summaries.append(s)
            else:
                pts = StatisticsService.collect_points(queryset, [test])
                s = StatisticsService.build_trend_summary(pts, test)
                summaries.append(s)

        if filters.show_only_with_data:
            summaries = [s for s in summaries if s["has_data"]]

        return StatisticsService._group_summaries(summaries, linac.name)

    @staticmethod
    def build_category_trends_summary(
        filters: StatisticsFilters,
    ) -> Dict[str, Any]:
        tests = StatisticsService.get_active_tests(filters.test_category)
        queryset = StatisticsService.build_queryset(filters)
        linac_ids = [l.id for l in StatisticsService.get_linacs(filters)]
        summaries = []

        for test in tests:
            if is_beam_test(test) and filters.energy:
                pts = StatisticsService.collect_points(
                    queryset, [test], energy=filters.energy
                )
                summaries.append(
                    StatisticsService.build_trend_summary(
                        pts, test, energy=filters.energy, linac_ids=linac_ids
                    )
                )
            elif is_beam_test(test):
                linacs = StatisticsService.get_linacs(filters)
                seen_energy = set()
                for linac in linacs:
                    for en in _linac_energies(linac):
                        if en in seen_energy:
                            continue
                        seen_energy.add(en)
                        pts = StatisticsService.collect_points(
                            queryset, [test], energy=en
                        )
                        summaries.append(
                            StatisticsService.build_trend_summary(
                                pts, test, energy=en, linac_ids=linac_ids
                            )
                        )
            else:
                pts = StatisticsService.collect_points(queryset, [test])
                summaries.append(
                    StatisticsService.build_trend_summary(
                        pts, test, linac_ids=linac_ids
                    )
                )

        if filters.show_only_with_data:
            summaries = [s for s in summaries if s["has_data"]]

        cat_label = DISPLAY_GROUP_LABELS.get(
            filters.test_category,
            filters.test_category.replace("_", " ").title(),
        )
        return StatisticsService._group_summaries(summaries, cat_label)

    @staticmethod
    def build_beam_energy_summary(filters: StatisticsFilters) -> Dict[str, Any]:
        tests = StatisticsService.get_active_tests("beam")
        tests = [
            t
            for t in tests
            if beam_test_in_group(t.order_index, filters.beam_test_group)
        ]
        queryset = StatisticsService.build_queryset(filters)
        linac_ids = [l.id for l in StatisticsService.get_linacs(filters)]
        summaries = []
        for test in tests:
            pts = StatisticsService.collect_points(
                queryset, [test], energy=filters.energy
            )
            summaries.append(
                StatisticsService.build_trend_summary(
                    pts,
                    test,
                    energy=filters.energy,
                    linac_ids=linac_ids,
                )
            )
        if filters.show_only_with_data:
            summaries = [s for s in summaries if s["has_data"]]
        title = f"Beam Energy Trends — {filters.energy}"
        return StatisticsService._group_summaries(summaries, title)

    @staticmethod
    def _group_summaries(
        summaries: List[Dict], title: str
    ) -> Dict[str, Any]:
        groups_dict = defaultdict(list)
        for s in summaries:
            groups_dict[s["display_group"]].append(s)
        groups = []
        for key in sorted(
            groups_dict.keys(),
            key=lambda k: list(DISPLAY_GROUP_LABELS.keys()).index(k)
            if k in DISPLAY_GROUP_LABELS
            else 99,
        ):
            label = DISPLAY_GROUP_LABELS.get(key, key)
            groups.append({
                "group_key": key,
                "group_label": label,
                "cards": groups_dict[key],
            })
        table_rows = []
        for s in summaries:
            table_rows.append({
                "test_id": s["test_id"],
                "test_name": s["test_name"],
                "category": s["category"],
                "energy": s.get("energy") or "",
                "latest": s["latest_value"],
                "unit": s["unit"],
                "trend_label": s["trend_label"],
                "warning_count": s["warning_count"],
                "failure_count": s["failure_count"],
                "last_qa_date": s["last_qa_date"],
                "has_data": s["has_data"],
            })
        return {
            "title": title,
            "groups": groups,
            "summary_table": table_rows,
        }

    @staticmethod
    def build_point_detail(
        qa_record_id: int,
        test_id: int,
        energy: Optional[str] = None,
    ) -> Dict[str, Any]:
        from django.urls import reverse

        record = QARecord.objects.select_related(
            "linac", "status", "performed_by"
        ).prefetch_related("film_analyses", "dose_calculations").get(
            pk=qa_record_id
        )
        qa_test = QATest.objects.get(pk=test_id)
        pt = StatisticsService.extract_point(record, qa_test, energy=energy)
        if not pt:
            return {"error": "No data for this test on the selected record."}

        film_url = None
        film_map = {
            "film": "fieldsize",
            12: "gantry_isocenter",
            13: "collimator_isocenter",
            14: "fieldsize",
        }
        analysis_type = film_map.get(qa_test.test_type) or film_map.get(
            qa_test.order_index
        )
        if analysis_type:
            fa = record.film_analyses.filter(
                analysis_type=analysis_type
            ).order_by("-created_at").first()
            if fa and fa.result_image:
                film_url = fa.result_image.url

        dose_info = None
        dc = record.dose_calculations.order_by("-created_at").first()
        if dc:
            dose_info = {
                "id": dc.id,
                "energy": dc.energy,
                "phantom": dc.phantom,
            }

        return {
            **pt,
            "qa_detail_url": reverse("qa_detail", args=[record.id]),
            "film_image_url": film_url,
            "dose_calculation": dose_info,
        }

    @staticmethod
    def build_csv(filters: StatisticsFilters) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "qa_record_id",
            "date_performed",
            "linac",
            "category",
            "test_name",
            "test_order_index",
            "energy",
            "value",
            "unit",
            "warning_threshold",
            "action_threshold",
            "classification",
            "qa_status",
            "source_type",
            "note",
            "performer",
        ])

        rows = StatisticsService._csv_rows(filters)
        for r in rows:
            writer.writerow([
                r.get("qa_record_id", ""),
                r.get("date", ""),
                r.get("linac_name", ""),
                r.get("category", ""),
                r.get("test_name", ""),
                r.get("order_index", ""),
                r.get("energy") or "",
                r.get("value", ""),
                r.get("unit", ""),
                r.get("warning_threshold", ""),
                r.get("action_threshold", ""),
                r.get("classification", ""),
                r.get("status_name", ""),
                r.get("source_type", ""),
                r.get("note", ""),
                r.get("performer", ""),
            ])
        return output.getvalue()

    @staticmethod
    def _csv_rows(filters: StatisticsFilters) -> List[Dict]:
        if filters.view_mode == "overview":
            queryset = StatisticsService.build_queryset(filters)
            tests = StatisticsService.get_active_tests(filters.test_category)
            points = StatisticsService.collect_points(queryset, tests)
            return [
                p
                for p in points
                if p["classification"]
                in (CLASSIFICATION_WARNING, CLASSIFICATION_FAILED)
            ]
        if filters.view_mode == "single_test":
            qa_test = QATest.objects.get(pk=filters.qa_test_id)
            queryset = StatisticsService.build_queryset(filters)
            return StatisticsService.collect_points(
                queryset, [qa_test], energy=filters.energy
            )
        if filters.view_mode == "linac_all_tests":
            data = StatisticsService.build_linac_all_tests_summary(filters)
            return StatisticsService._points_from_grouped(data, filters)
        if filters.view_mode == "category_trends":
            data = StatisticsService.build_category_trends_summary(filters)
            return StatisticsService._points_from_grouped(data, filters)
        if filters.view_mode == "beam_energy":
            data = StatisticsService.build_beam_energy_summary(filters)
            return StatisticsService._points_from_grouped(data, filters)
        return []

    @staticmethod
    def _points_from_grouped(
        data: Dict, filters: StatisticsFilters
    ) -> List[Dict]:
        queryset = StatisticsService.build_queryset(filters)
        tests = StatisticsService.get_active_tests(
            filters.test_category if filters.test_category != "all" else "all"
        )
        if filters.view_mode == "beam_energy":
            tests = [
                t
                for t in tests
                if is_beam_test(t)
                and beam_test_in_group(t.order_index, filters.beam_test_group)
            ]
        return StatisticsService.collect_points(
            queryset,
            tests,
            energy=filters.energy if filters.view_mode == "beam_energy" else None,
        )


def _linac_energies(linac: Linac) -> List[str]:
    raw = linac.energy or []
    if isinstance(raw, list):
        return [str(e) for e in raw if e]
    return []


def _iter_months(date_from: date, date_to: date):
    y, m = date_from.year, date_from.month
    end_y, end_m = date_to.year, date_to.month
    while (y, m) <= (end_y, end_m):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def _classification_rank(c: str) -> int:
    return {
        CLASSIFICATION_MISSING: 0,
        CLASSIFICATION_NORMAL: 1,
        CLASSIFICATION_WARNING: 2,
        CLASSIFICATION_FAILED: 3,
    }.get(c, 0)


def _classification_to_color(c: str) -> str:
    return {
        CLASSIFICATION_NORMAL: "green",
        CLASSIFICATION_WARNING: "yellow",
        CLASSIFICATION_FAILED: "red",
        CLASSIFICATION_MISSING: "gray",
    }.get(c, "gray")


def _linear_slope(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den
