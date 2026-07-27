#!/usr/bin/env python3
"""Initialize a demo SQLite database with obviously fake seed data.

Usage (from repository root)::

    python scripts/init_demo_db.py

Requires Django. If ``DJANGO_SECRET_KEY`` is not set, this script sets a
temporary demo-only insecure key via ``os.environ.setdefault`` for **this
process only** — never use that key outside local demo init.

Does NOT use any real hospital or departmental data.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Demo-only insecure key used ONLY when DJANGO_SECRET_KEY is missing.
# Documented intentionally — local demo bootstrap, not for shared/production use.
_DEMO_INSECURE_SECRET = "demo-only-insecure-secret-key-for-local-init-do-not-reuse"
os.environ.setdefault("DJANGO_SECRET_KEY", _DEMO_INSECURE_SECRET)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "QA_Manager.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.core.management import call_command  # noqa: E402

from QAID_Manager.bootstrap_credentials import (  # noqa: E402
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
)
from QAID_Manager.models import (  # noqa: E402
    Dosimeter,
    Linac,
    OrganizationSettings,
    QASchedule,
    QAStatus,
    QATest,
)


def _ensure_statuses() -> None:
    defaults = [
        ("scheduled", "#6c757d", "QA session is scheduled but not yet performed"),
        ("in_progress", "#ffc107", "QA session is in progress"),
        ("completed", "#17a2b8", "QA session completed"),
        ("passed", "#28a745", "QA passed"),
        ("passed_with_exception", "#20c997", "Passed with deviation"),
        ("minor_service", "#fd7e14", "Needs minor service"),
        ("major_service", "#dc3545", "Needs major service"),
        ("failed", "#dc3545", "QA failed"),
    ]
    for name, color, description in defaults:
        QAStatus.objects.get_or_create(
            name=name,
            defaults={"color": color, "description": description},
        )


def _ensure_qa_tests() -> int:
    before = QATest.objects.count()
    try:
        call_command("setup_default_tests", verbosity=0)
    except Exception:
        # Minimal fallback if management command unavailable
        samples = [
            {
                "name": "Demo Field Size Match",
                "test_type": "film",
                "description": "Synthetic demo test only",
                "tolerance_value": 1.0,
                "tolerance_unit": "mm",
                "order_index": 1,
            },
            {
                "name": "Demo Collimator Isocenter",
                "test_type": "isocenter",
                "description": "Synthetic demo test only",
                "tolerance_value": 1.0,
                "tolerance_unit": "mm",
                "order_index": 2,
            },
            {
                "name": "Demo Absolute Dose",
                "test_type": "beam",
                "description": "Synthetic demo test only",
                "tolerance_value": 2.0,
                "tolerance_unit": "%",
                "order_index": 3,
            },
        ]
        for data in samples:
            QATest.objects.get_or_create(name=data["name"], defaults=data)
    return QATest.objects.count() - before


def main() -> None:
    sample_dir = ROOT / "sample_data"
    sample_dir.mkdir(parents=True, exist_ok=True)

    if os.environ.get("DJANGO_SECRET_KEY") == _DEMO_INSECURE_SECRET:
        print(
            "NOTE: Using temporary demo-only insecure DJANGO_SECRET_KEY "
            "(setdefault for this process). Set a real key for anything beyond local demo."
        )

    print("Running migrate...")
    call_command("migrate", interactive=False, verbosity=1)

    org = OrganizationSettings.get_settings()
    org.organization_name = "Demo Radiotherapy Physics Department"
    org.save()
    print(f"OrganizationSettings: {org.organization_name!r}")

    linac_a, created_a = Linac.objects.get_or_create(
        series_number="DEMO-LINAC-001",
        defaults={
            "name": "Demo Linac A",
            "energy": ["6MV", "10MV"],
            "dosimetry_method": "SAD_TRS398",
            "cat_info": "FAKE CAT — educational demo only (values 0.5 / 1.0)",
            "cat_gantry_isocenter": 0.5,
            "cat_collimator_isocenter": 0.5,
            "cat_field_size_12x12": 1.0,
            "cat_d10_6mv": 1.0,
            "beam_pdd_20_10_6mv": 0.5,
            "is_active": True,
        },
    )
    if not created_a:
        linac_a.name = "Demo Linac A"
        linac_a.energy = ["6MV", "10MV"]
        linac_a.cat_gantry_isocenter = 0.5
        linac_a.cat_collimator_isocenter = 0.5
        linac_a.cat_field_size_12x12 = 1.0
        linac_a.save()

    linac_b, created_b = Linac.objects.get_or_create(
        series_number="DEMO-LINAC-002",
        defaults={
            "name": "Demo Linac B",
            "energy": ["6MV", "15MV"],
            "dosimetry_method": "SAD_TRS398",
            "cat_info": "FAKE CAT — educational demo only (values 0.5 / 1.0)",
            "cat_gantry_isocenter": 1.0,
            "cat_collimator_isocenter": 0.5,
            "cat_field_size_12x12": 0.5,
            "cat_d10_6mv": 0.5,
            "beam_pdd_20_10_6mv": 1.0,
            "is_active": True,
        },
    )
    if not created_b:
        linac_b.name = "Demo Linac B"
        linac_b.save()

    chamber_001, _ = Dosimeter.objects.get_or_create(
        series_number="DEMO-CHAMBER-001",
        defaults={
            "name": "Demo Chamber 001",
            "brand": "DemoBrand",
            "certificate_number": "FAKE-CERT-001",
            "calibration_factor": 0.5,
            "calibration_temperature": 20.0,
            "calibration_pressure": 1013.25,
            "calibration_lab": "Demo Calibration Lab (fake)",
            "is_active": True,
        },
    )
    chamber_002, _ = Dosimeter.objects.get_or_create(
        series_number="DEMO-CHAMBER-002",
        defaults={
            "name": "Demo Chamber 002",
            "brand": "DemoBrand",
            "certificate_number": "FAKE-CERT-002",
            "calibration_factor": 1.0,
            "calibration_temperature": 20.0,
            "calibration_pressure": 1013.25,
            "calibration_lab": "Demo Calibration Lab (fake)",
            "is_active": True,
        },
    )

    _ensure_statuses()
    created_tests = _ensure_qa_tests()

    admin, admin_created = User.objects.get_or_create(
        username=DEFAULT_ADMIN_USERNAME,
        defaults={
            "email": DEFAULT_ADMIN_EMAIL,
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if admin_created or not admin.check_password(DEFAULT_ADMIN_PASSWORD):
        admin.set_password(DEFAULT_ADMIN_PASSWORD)
        admin.is_staff = True
        admin.is_superuser = True
        admin.email = DEFAULT_ADMIN_EMAIL
        admin.save()

    scheduled = QAStatus.objects.filter(name="scheduled").first()
    today = date.today()
    month_year = today.replace(day=1)
    schedule, schedule_created = QASchedule.objects.get_or_create(
        linac=linac_a,
        month_year=month_year,
        is_adhoc=False,
        defaults={
            "performer1": admin,
            "status": scheduled,
            "qa_reason": "Demo seed schedule (fake)",
            "notes": "Educational demo only — no real hospital data.",
            "expected_qa_date": today,
        },
    )

    summary = {
        "note": "Demo seed summary — synthetic / educational data only.",
        "organization": org.organization_name,
        "linacs": [
            {"id": linac_a.id, "name": linac_a.name, "series_number": linac_a.series_number},
            {"id": linac_b.id, "name": linac_b.name, "series_number": linac_b.series_number},
        ],
        "chambers": [
            {
                "id": chamber_001.id,
                "name": chamber_001.name,
                "series_number": chamber_001.series_number,
            },
            {
                "id": chamber_002.id,
                "name": chamber_002.name,
                "series_number": chamber_002.series_number,
            },
        ],
        "qa_tests_total": QATest.objects.count(),
        "qa_tests_created_this_run": created_tests,
        "admin_username": DEFAULT_ADMIN_USERNAME,
        "admin_password_hint": "change-me-before-use",
        "admin_created": admin_created,
        "schedule": {
            "id": schedule.id,
            "linac": linac_a.name,
            "month_year": str(month_year),
            "created": schedule_created,
        },
        "secret_key_note": (
            "If DJANGO_SECRET_KEY was missing, a demo-only insecure key was set "
            "via os.environ.setdefault for this process only."
        ),
    }

    out = sample_dir / "demo_seed.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print("Demo DB init complete.")


if __name__ == "__main__":
    main()
