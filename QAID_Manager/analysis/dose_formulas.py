"""Educational TRS-398-style dose correction formulas (pure Python).

These helpers mirror the documented equations used by the prototype UI for
temperature/pressure, polarity, recombination, beam quality, and simple
symmetry/flatness ratios.

IMPORTANT: Educational / research-prototype implementations only.
They are NOT certified for clinical dosimetry or regulatory use.
"""

from __future__ import annotations

from typing import Sequence


def calculate_ktp(
    t_celsius: float,
    p_hpa: float,
    t0: float = 20.0,
    p0: float = 1013.25,
) -> float:
    """Temperature–pressure correction: k_TP = (273.2+T)/(273.2+T0) * P0/P.

    Educational implementation only — not for clinical certification.
    """
    if p_hpa == 0:
        raise ValueError("Pressure P must be non-zero")
    return ((273.2 + t_celsius) / (273.2 + t0)) * (p0 / p_hpa)


def calculate_kpol(m_plus: float, m_minus: float) -> float:
    """Polarity correction: k_pol = (|M+| + |M-|) / (2 * |M+|).

    Educational implementation only — not for clinical certification.
    """
    abs_plus = abs(m_plus)
    if abs_plus == 0:
        raise ValueError("M+ must be non-zero")
    return (abs_plus + abs(m_minus)) / (2.0 * abs_plus)


def calculate_ks(m1: float, m2: float, a0: float, a1: float, a2: float) -> float:
    """Ion recombination (two-voltage): k_s = a0 + a1*(M1/M2) + a2*(M1/M2)^2.

    Educational implementation only — not for clinical certification.
    """
    if m2 == 0:
        raise ValueError("M2 must be non-zero")
    ratio = m1 / m2
    return a0 + a1 * ratio + a2 * (ratio ** 2)


def calculate_mq(
    m_raw: float,
    ktp: float,
    kpol: float,
    ks: float,
    f_phantom: float = 1.0,
) -> float:
    """Corrected chamber reading: M_Q = M_raw * k_TP * k_pol * k_s * f_phantom.

    Educational implementation only — not for clinical certification.
    """
    return m_raw * ktp * kpol * ks * f_phantom


def calculate_tpr_20_10(pdd_20_10: float) -> float:
    """Beam quality: TPR_20,10 = 1.2661 * PDD_20,10 − 0.0595.

    Educational implementation only — not for clinical certification.
    """
    return 1.2661 * pdd_20_10 - 0.0595


def interpolate_kq(tpr: float, table_points: Sequence[tuple[float, float]]) -> float:
    """Linearly interpolate k_Q from sorted (TPR, k_Q) table points.

    Extrapolates by clamping to the nearest endpoint when TPR is outside
    the tabulated range.

    Educational implementation only — not for clinical certification.
    """
    if not table_points:
        raise ValueError("table_points must not be empty")

    points = sorted((float(t), float(k)) for t, k in table_points)
    if tpr <= points[0][0]:
        return points[0][1]
    if tpr >= points[-1][0]:
        return points[-1][1]

    for i in range(len(points) - 1):
        t1, k1 = points[i]
        t2, k2 = points[i + 1]
        if t1 <= tpr <= t2:
            if t2 == t1:
                return k1
            return k1 + (k2 - k1) * (tpr - t1) / (t2 - t1)

    return points[-1][1]


def calculate_dwq_zref(mq: float, ndw: float, kq: float) -> float:
    """Absorbed dose to water at z_ref: D_w,Q = M_Q * N_D,w * k_Q.

    Educational implementation only — not for clinical certification.
    """
    return mq * ndw * kq


def calculate_symmetry_percent(m_a: float, m_b: float) -> float:
    """Symmetry ratio as percent: max(|Ma|,|Mb|) / min(|Ma|,|Mb|) * 100.

    Educational implementation only — not for clinical certification.
    """
    a = abs(m_a)
    b = abs(m_b)
    lo = min(a, b)
    if lo == 0:
        raise ValueError("Both readings must be non-zero for symmetry")
    return (max(a, b) / lo) * 100.0


def calculate_flatness_percent(m1: float, m2: float, m_mid: float) -> float:
    """Flatness as percent: max(m1,m2,m_mid) / min(m1,m2,m_mid) * 100.

    Educational implementation only — not for clinical certification.
    """
    vals = (abs(m1), abs(m2), abs(m_mid))
    lo = min(vals)
    if lo == 0:
        raise ValueError("All readings must be non-zero for flatness")
    return (max(vals) / lo) * 100.0
