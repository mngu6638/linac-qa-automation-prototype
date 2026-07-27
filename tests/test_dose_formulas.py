"""Unit tests for educational TRS-398-style dose formulas."""

from __future__ import annotations

import pytest

from QAID_Manager.analysis.dose_formulas import (
    calculate_dwq_zref,
    calculate_flatness_percent,
    calculate_kpol,
    calculate_ks,
    calculate_ktp,
    calculate_mq,
    calculate_symmetry_percent,
    calculate_tpr_20_10,
    interpolate_kq,
)


def test_calculate_ktp_reference_conditions():
    assert calculate_ktp(20.0, 1013.25) == pytest.approx(1.0, rel=1e-9)


def test_calculate_ktp_known_value():
    # (273.2+22)/(273.2+20) * 1013.25/1000
    expected = ((273.2 + 22.0) / (273.2 + 20.0)) * (1013.25 / 1000.0)
    assert calculate_ktp(22.0, 1000.0) == pytest.approx(expected, rel=1e-9)


def test_calculate_kpol():
    assert calculate_kpol(1.0, -1.0) == pytest.approx(1.0)
    assert calculate_kpol(2.0, -1.0) == pytest.approx(0.75)


def test_calculate_ks():
    # a0 + a1*(M1/M2) + a2*(M1/M2)^2 with M1/M2 = 2
    assert calculate_ks(2.0, 1.0, 1.0, 0.1, 0.01) == pytest.approx(1.24)


def test_calculate_mq():
    assert calculate_mq(10.0, 1.02, 1.01, 1.005, 1.0) == pytest.approx(
        10.0 * 1.02 * 1.01 * 1.005, rel=1e-12
    )


def test_calculate_tpr_20_10():
    assert calculate_tpr_20_10(0.66) == pytest.approx(1.2661 * 0.66 - 0.0595)


def test_interpolate_kq_exact_and_midpoint():
    table = [(0.50, 1.000), (0.60, 0.990), (0.70, 0.980)]
    assert interpolate_kq(0.60, table) == pytest.approx(0.990)
    assert interpolate_kq(0.55, table) == pytest.approx(0.995)


def test_interpolate_kq_clamps_outside_range():
    table = [(0.50, 1.000), (0.70, 0.980)]
    assert interpolate_kq(0.40, table) == pytest.approx(1.000)
    assert interpolate_kq(0.80, table) == pytest.approx(0.980)


def test_calculate_dwq_zref():
    assert calculate_dwq_zref(1.5, 50.0, 0.99) == pytest.approx(1.5 * 50.0 * 0.99)


def test_calculate_symmetry_percent():
    assert calculate_symmetry_percent(100.0, 98.0) == pytest.approx(100.0 / 98.0 * 100.0)


def test_calculate_flatness_percent():
    assert calculate_flatness_percent(100.0, 95.0, 98.0) == pytest.approx(
        100.0 / 95.0 * 100.0
    )


def test_ktp_zero_pressure_raises():
    with pytest.raises(ValueError):
        calculate_ktp(20.0, 0.0)


def test_symmetry_zero_raises():
    with pytest.raises(ValueError):
        calculate_symmetry_percent(0.0, 1.0)
