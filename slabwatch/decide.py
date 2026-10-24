"""Plain-code decision layer. The model forecasts; this file decides what (if anything) to say.

Rules (in order):
  1. units_so_far > threshold                              -> already_over
  2. P(cross) >= ACT_P                                     -> act
  3. P10..P90 spans the threshold and (P90-P10)/P50 > MAX_REL_SPREAD -> unsure (too early to tell)
  4. P(cross) >= WATCH_P                                   -> watch
  5. otherwise                                             -> safe
Only `act` and `already_over` are meant to push a notification; `watch`/`unsure` show on the page.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

ACT_P = 0.5
WATCH_P = 0.15
MAX_REL_SPREAD = 0.5
SEVERITY = {"safe": 0, "unsure": 1, "watch": 1, "act": 2, "already_over": 3}


@dataclass
class Decision:
    verdict: str
    units_so_far: float
    days_elapsed: int
    days_left: int
    threshold: float
    daily_budget: float | None     # units/day left to stay at or under the threshold
    current_rate: float
    p_cross: float
    message: str
    message_ur: str                # Roman-Urdu line (optional for the UI)
    assumptions: list[str]

    @property
    def severity(self) -> int:
        return SEVERITY[self.verdict]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity
        return d


def _f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") if abs(x) < 1000 else f"{x:.0f}"


def decide(p10: float, p50: float, p90: float, p_cross: float, units_so_far: float, days_elapsed: int,
           cycle_days: int = 30, threshold: float = 200, penalty_months: int = 6,
           backend: str = "model", weather_note: str = "Open-Meteo forecast for Lahore") -> Decision:
    if days_elapsed <= 0:
        raise ValueError("days_elapsed must be >= 1")
    days_left = max(cycle_days - days_elapsed, 0)
    rate = units_so_far / days_elapsed
    budget = (threshold - units_so_far) / days_left if days_left > 0 else None
    T, so, de = _f(threshold), _f(units_so_far), days_elapsed
    assumptions = [
        f"Protected limit {T} units per bill; going over once costs protected status for "
        f"{penalty_months} months (editable in settings; the rule may have changed).",
        f"Billing cycle of {cycle_days} days, day {de} today.",
        f"Forecast: {backend}; weather: {weather_note}.",
    ]
    band = f"Likely finish: {_f(p10)}-{_f(p90)} units (middle guess {_f(p50)})."
    spread = (p90 - p10) / p50 if p50 > 0 else float("inf")

    if units_so_far > threshold:
        verdict = "already_over"
        msg = (f"You've used {so} units in {de} days, already past {T}. This bill won't be on the "
               f"protected rate. Saving now still lowers the bill, and the next cycle starts fresh. {band}")
        ur = f"{de} din mein {so} unit ho chuke hain, {T} se upar. Ab bachat se bill phir bhi kam hoga."
    elif p_cross >= ACT_P:
        verdict = "act"
        msg = (f"You've used {so} units in {de} days. To stay under {T} you have {_f(budget or 0)} units/day "
               f"for {days_left} days; you're running at {_f(rate)}. Chance of going over: about "
               f"{round(p_cross * 100)}%. {band}")
        ur = (f"{de} din mein {so} unit. {T} se neeche rehne ke liye roz {_f(budget or 0)} unit tak, "
              f"{days_left} din. Abhi roz {_f(rate)} chal raha hai.")
    elif spread > MAX_REL_SPREAD and p10 <= threshold <= p90:
        verdict = "unsure"
        msg = (f"Too early to call: {so} units in {de} days, and the likely range still straddles {T}. "
               f"Another reading in a few days will settle it. {band}")
        ur = f"Abhi kehna mushkil hai. {de} din mein {so} unit. Kuch din baad meter ki photo bhejein."
    elif p_cross >= WATCH_P:
        verdict = "watch"
        msg = (f"Probably fine, but close: {so} units in {de} days. Staying under {T} means about "
               f"{_f(budget or 0)} units/day for the last {days_left} days (you're at {_f(rate)}). {band}")
        ur = f"Shayad theek hai, magar qareeb. Roz {_f(budget or 0)} unit tak rakhein, {days_left} din."
    else:
        verdict = "safe"
        msg = f"On track: {so} units in {de} days, comfortably under {T}. Nothing to do. {band}"
        ur = f"Sab theek: {de} din mein {so} unit, {T} se kaafi neeche."
    return Decision(verdict, units_so_far, de, days_left, threshold, budget, rate, p_cross, msg, ur, assumptions)


def escalated(previous: str | None, current: str) -> bool:
    """True if `current` is more severe than anything alerted before (alert once per escalation)."""
    return SEVERITY[current] >= 2 and SEVERITY[current] > (SEVERITY[previous] if previous else 0)
