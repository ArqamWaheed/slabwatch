"""Rupee estimate of a domestic bill (ex-WAPDA DISCOs and K-Electric share the uniform schedule).

The forecast is in units, which the household controls; this module only answers "what would that cost".
It is an ESTIMATE, and every number below has a source in docs/TARIFF.md.

Schedule: NEPRA "Rationalization" decision of 11 Feb 2026, notified as S.R.O. 279(I)/2026 (12 Feb 2026).
  - Protected (<=200 kWh in each of the past 6 months): "one previous slab" benefit, so
    180 units = 100 x 10.54 + 80 x 13.01.
  - Unprotected: no slab benefit; the whole month is billed at the rate of the slab the total falls in
    (210 units = 210 x 33.10). That is the cliff.
  - Fixed charge per kW of sanctioned load; we assume the row of that month's slab [unverified on a real bill].
Adjustments (per kWh): FCA (monthly, set by NEPRA, found by the tariff watcher), QTA (quarterly),
debt service surcharge (3.23 unprotected / 0.43 protected). GST 18% on everything. Lifeline, electricity
duty (removed Jul 2025) and income tax (bills >= Rs25,000, non-filers) are not modelled.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

EFFECTIVE = "2026-02-12 (S.R.O. 279(I)/2026)"
PROTECTED = [(100, 10.54, 200), (200, 13.01, 300)]                       # (upper, Rs/kWh, Rs/kW/month)
UNPROTECTED = [(100, 22.44, 275), (200, 28.91, 300), (300, 33.10, 350), (400, 36.46, 400),
               (500, 38.95, 500), (600, 40.22, 675), (700, 41.85, 675), (float("inf"), 47.20, 675)]
DSS = {"protected": 0.43, "unprotected": 3.23}
GST = 0.18
FCA_DEFAULT = 1.1086   # Aug 2026 FCA, charged on Oct 2026 bills (NEPRA decision 07 Oct 2026)
QTA_DEFAULT = 0.5194   # Q2 CY2026, on Sep-Nov 2026 bills (S.R.O. 1501(I)/2026)


@dataclass
class Estimate:
    units: float
    status: str
    energy: float
    fixed: float
    fca: float
    qta: float
    dss: float
    gst: float
    total: float
    rate_note: str

    def to_dict(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def energy_charge(units: float, status: str) -> tuple[float, float, str]:
    """(energy Rs, fixed Rs per kW, note)."""
    if status == "protected":
        if units > 200:
            raise ValueError("a protected bill cannot exceed 200 units; above 200 the month is unprotected")
        if units <= 100:
            return units * PROTECTED[0][1], PROTECTED[0][2], f"{units:g} x {PROTECTED[0][1]}"
        return (100 * PROTECTED[0][1] + (units - 100) * PROTECTED[1][1], PROTECTED[1][2],
                f"100 x {PROTECTED[0][1]} + {units - 100:g} x {PROTECTED[1][1]}")
    for upper, rate, fixed in UNPROTECTED:
        if units <= upper:
            return units * rate, fixed, f"{units:g} x {rate} (whole month at this slab's rate)"
    raise AssertionError("unreachable")


def estimate(units: float, status: str = "protected", sanctioned_kw: float = 2.0,
             fca: float = FCA_DEFAULT, qta: float = QTA_DEFAULT) -> Estimate:
    if status not in DSS:
        raise ValueError("status is 'protected' or 'unprotected'")
    units = round(max(0.0, units))
    energy, fixed_per_kw, note = energy_charge(units, status)
    fixed = fixed_per_kw * sanctioned_kw
    f, q, d = units * fca, units * qta, units * DSS[status]
    gst = GST * (energy + fixed + f + q + d)
    return Estimate(units, status, energy, fixed, f, q, d, gst, energy + fixed + f + q + d + gst, note)


def cliff_cost(units_if_under: float, units_if_over: float, typical_month: float, sanctioned_kw: float = 2.0,
               penalty_months: int = 6, fca: float = FCA_DEFAULT, qta: float = QTA_DEFAULT) -> dict:
    """What crossing 200 costs: this month, plus the next `penalty_months` months billed unprotected at a
    typical month's usage instead of protected. Same FCA/QTA assumed throughout (stated)."""
    this_under = estimate(min(units_if_under, 200), "protected", sanctioned_kw, fca, qta).total
    this_over = estimate(units_if_over, "unprotected", sanctioned_kw, fca, qta).total
    typ = min(typical_month, 200)
    later = penalty_months * (estimate(typ, "unprotected", sanctioned_kw, fca, qta).total -
                              estimate(typ, "protected", sanctioned_kw, fca, qta).total)
    return {"this_month_extra": round(this_over - this_under), "next_months_extra": round(later),
            "total_extra": round(this_over - this_under + later), "penalty_months": penalty_months,
            "assumes": f"tariff {EFFECTIVE}; FCA {fca}/kWh and QTA {qta}/kWh every month; "
                       f"{sanctioned_kw:g} kW sanctioned load; typical month {typ:g} units"}
