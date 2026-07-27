"""
Statistics module views for QAID Manager v1.3.
"""
import logging
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from ..models import Linac, QARecord, QATest
from ..qa_test_mapping import DISPLAY_GROUP_LABELS, is_beam_test
from ..statistics_service import StatisticsFilters, StatisticsService, VIEW_MODES
from ..views.qa_views import get_app_version

logger = logging.getLogger(__name__)


def _json_error(message: str, status: int = 400):
    return JsonResponse({"success": False, "error": message}, status=status)


@login_required
@require_GET
def statistics_home(request):
    """Render Statistics page with initial context."""
    linacs = Linac.objects.filter(is_active=True).order_by("name")
    tests = QATest.objects.filter(is_active=True).order_by(
        "test_type", "order_index"
    )
    tests_by_category = {}
    for test in tests:
        tests_by_category.setdefault(test.test_type, []).append({
            "id": test.id,
            "name": test.name,
            "order_index": test.order_index,
            "is_beam": is_beam_test(test),
            "unit": test.tolerance_unit,
        })

    date_from, date_to = StatisticsFilters().resolved_dates()

    return render(
        request,
        "QAID_Manager/statistics.html",
        {
            "linacs": linacs,
            "tests": tests,
            "tests_by_category": tests_by_category,
            "view_modes": [
                ("overview", "Overview"),
                ("single_test", "Single Test Trend"),
                ("linac_all_tests", "All Tests for Selected LINAC"),
                ("category_trends", "Category Trends"),
                ("beam_energy", "Beam Energy Trends"),
            ],
            "categories": [
                ("all", "All"),
                ("mechanical", "Mechanical"),
                ("beam", "Beam / Dose"),
                ("film", "Film"),
                ("isocenter", "Isocenter"),
            ],
            "display_groups": DISPLAY_GROUP_LABELS,
            "default_date_from": date_from.isoformat(),
            "default_date_to": date_to.isoformat(),
            "app_version": get_app_version(),
            "is_staff": request.user.is_staff,
        },
    )


def _parse_filters(request) -> StatisticsFilters:
    return StatisticsFilters.from_request(request)


@login_required
@require_GET
def statistics_overview_api(request):
    try:
        filters = _parse_filters(request)
        err = StatisticsService.validate_filters(filters)
        if err and filters.view_mode != "overview":
            return _json_error(err)
        data = StatisticsService.build_overview(filters)
        return JsonResponse({"success": True, "data": data})
    except Exception as exc:
        logger.exception("statistics overview error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_trend_api(request):
    try:
        filters = _parse_filters(request)
        err = StatisticsService.validate_filters(filters)
        if err:
            return _json_error(err)
        data = StatisticsService.build_single_test_trend(filters)
        return JsonResponse({"success": True, "data": data})
    except QATest.DoesNotExist:
        return _json_error("QA test not found.", 404)
    except Exception as exc:
        logger.exception("statistics trend error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_linac_all_api(request):
    try:
        filters = _parse_filters(request)
        err = StatisticsService.validate_filters(filters)
        if err:
            return _json_error(err)
        data = StatisticsService.build_linac_all_tests_summary(filters)
        return JsonResponse({"success": True, "data": data})
    except Linac.DoesNotExist:
        return _json_error("LINAC not found.", 404)
    except Exception as exc:
        logger.exception("statistics linac-all error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_category_api(request):
    try:
        filters = _parse_filters(request)
        err = StatisticsService.validate_filters(filters)
        if err:
            return _json_error(err)
        data = StatisticsService.build_category_trends_summary(filters)
        return JsonResponse({"success": True, "data": data})
    except Exception as exc:
        logger.exception("statistics category error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_beam_energy_api(request):
    try:
        filters = _parse_filters(request)
        err = StatisticsService.validate_filters(filters)
        if err:
            return _json_error(err)
        data = StatisticsService.build_beam_energy_summary(filters)
        return JsonResponse({"success": True, "data": data})
    except Exception as exc:
        logger.exception("statistics beam-energy error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_point_api(request, qa_record_id: int):
    try:
        test_id = request.GET.get("test_id")
        energy = request.GET.get("energy") or None
        if not test_id:
            return _json_error("test_id is required.")
        data = StatisticsService.build_point_detail(
            qa_record_id, int(test_id), energy=energy
        )
        if data.get("error"):
            return _json_error(data["error"], 404)
        return JsonResponse({"success": True, "data": data})
    except QARecord.DoesNotExist:
        return _json_error("QA record not found.", 404)
    except QATest.DoesNotExist:
        return _json_error("QA test not found.", 404)
    except Exception as exc:
        logger.exception("statistics point error")
        return _json_error(str(exc), 500)


@login_required
@require_GET
def statistics_export_csv(request):
    try:
        filters = _parse_filters(request)
        if filters.view_mode not in VIEW_MODES:
            return _json_error("Invalid view_mode.")
        if filters.view_mode == "single_test":
            err = StatisticsService.validate_filters(filters)
            if err:
                return _json_error(err)
        csv_content = StatisticsService.build_csv(filters)
        filename = f"qa_statistics_{filters.view_mode}_{date.today().isoformat()}.csv"
        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as exc:
        logger.exception("statistics csv export error")
        return _json_error(str(exc), 500)
