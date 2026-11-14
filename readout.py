#!/usr/bin/env python3
"""Turn a finished geo test's daily numbers into a one-page readout, in a fixed order.

Standard library only. The checks come in the order I read a test: was the MDE
reached, then all-time and rolling iROAS, then iROAS from revenue lift beside
iROAS from orders lift times the control's AOV. Then it writes the decision
options. It is a readout worksheet, not an analysis library: for a full design
and analysis use GeoLift, Trimmed Match or Meridian GeoX.

By Eric Brinker, Brinker Analytics (https://brinkeranalytics.com). MIT license.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
import statistics
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

REQUIRED = ["date", "cell", "revenue", "orders"]
Z90_ONE_SIDED = statistics.NormalDist().inv_cdf(0.90)
Z90_TWO_SIDED = statistics.NormalDist().inv_cdf(0.95)

INCONCLUSIVE_RULE = (
    "We failed to prove that it was a home run, which for our strategy is as good as a loss. "
    "It doesn't mean the door is shut forever. It just means we have to move on for now."
)


@dataclass
class Day:
    date: dt.date
    treat_rev: float = 0.0
    treat_orders: float = 0.0
    ctrl_rev: float = 0.0
    ctrl_orders: float = 0.0
    spend: Optional[float] = None


def load(path: str) -> Dict[dt.date, Day]:
    days: Dict[dt.date, Day] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (r.fieldnames or [])]
        if missing:
            sys.exit(f"{path}: missing columns {missing}")
        seen = set()
        for row in r:
            d = dt.date.fromisoformat(row["date"].strip()[:10])
            cell = row["cell"].strip().lower()
            if cell not in ("treatment", "control"):
                sys.exit(f"{path}: cell must be 'treatment' or 'control', got {row['cell']!r}")
            if (d, cell) in seen:
                sys.exit(f"{path}: {d} {cell} appears twice")
            seen.add((d, cell))
            day = days.setdefault(d, Day(d))
            rev, orders = float(row["revenue"]), float(row["orders"])
            if cell == "treatment":
                day.treat_rev, day.treat_orders = rev, orders
                s = (row.get("spend") or "").strip()
                if s:
                    day.spend = float(s)
            else:
                day.ctrl_rev, day.ctrl_orders = rev, orders
    return days


def _window(days: Dict[dt.date, Day], start: dt.date, end: dt.date) -> List[Day]:
    out = [days[d] for d in sorted(days) if start <= d <= end]
    n_expected = (end - start).days + 1
    if len(out) != n_expected:
        sys.exit(f"missing days between {start} and {end}: have {len(out)} of {n_expected}")
    return out


def _weeks(rows: List[Day]) -> List[List[Day]]:
    return [rows[i:i + 7] for i in range(0, len(rows) - len(rows) % 7, 7)]


@dataclass
class Readout:
    design: str
    pre_days: int
    test_days: int
    scale_rev: float
    scale_orders: float
    actual_rev: float
    predicted_rev: float
    lift_rev: float
    lift_pct: float
    se_pct: float
    lower_one_sided_pct: float
    interval_pct: tuple
    target_mde: Optional[float]
    mde_reached: Optional[bool]
    significant: bool
    spend: float
    iroas_all_time: Optional[float]
    iroas_range: tuple
    rolling: List[dict] = field(default_factory=list)
    lift_orders: float = 0.0
    control_aov: Optional[float] = None
    iroas_orders_x_aov: Optional[float] = None
    expected_iroas: Optional[float] = None
    band: float = 0.2
    zone_low: str = ""
    zone_high: str = ""
    zone_point: str = ""


def zone(value: Optional[float], expected: Optional[float], band: float) -> str:
    if value is None or expected is None:
        return ""
    if value < expected * (1 - band):
        return "below the band"
    if value > expected * (1 + band):
        return "above the band"
    return "within the band"


def analyze(days: Dict[dt.date, Day], pre_start: dt.date, pre_end: dt.date, test_start: dt.date,
            test_end: dt.date, spend: Optional[float], target_mde: Optional[float],
            expected_iroas: Optional[float] = None, band: float = 0.2, rolling_weeks: int = 4,
            design: str = "holdout") -> Readout:
    pre = _window(days, pre_start, pre_end)
    test = _window(days, test_start, test_end)
    if len(pre) < len(test):
        sys.exit("the pre-period should be at least as long as the test")
    if len(test) % 7:
        sys.exit("test length must be whole weeks")

    k_rev = sum(d.treat_rev for d in pre) / sum(d.ctrl_rev for d in pre)
    k_ord = sum(d.treat_orders for d in pre) / sum(d.ctrl_orders for d in pre)

    # Weekly % error of the scaled control in the pre-period: the noise the result is read against.
    errs = []
    for w in _weeks(pre):
        pred = k_rev * sum(d.ctrl_rev for d in w)
        errs.append((sum(d.treat_rev for d in w) - pred) / pred)
    sd = statistics.stdev(errs) if len(errs) > 1 else 0.0
    se = sd * math.sqrt(7 / len(test) + 7 / len(pre))

    actual = sum(d.treat_rev for d in test)
    predicted = k_rev * sum(d.ctrl_rev for d in test)
    lift = actual - predicted
    lift_pct = lift / predicted
    lower = lift_pct - Z90_ONE_SIDED * se
    interval = (lift_pct - Z90_TWO_SIDED * se, lift_pct + Z90_TWO_SIDED * se)

    daily_spend = [d.spend for d in test]
    if all(s is not None for s in daily_spend):
        total_spend = float(sum(daily_spend))
    elif spend is not None:
        total_spend = spend
        daily_spend = [spend / len(test)] * len(test)
    else:
        sys.exit("give --spend, or a spend column on the treatment rows for every test day")

    def iroas_of(rev_lift: float, s: float) -> Optional[float]:
        return rev_lift / s if s > 0 else None

    iroas_all = iroas_of(lift, total_spend)
    iroas_lo = iroas_of(interval[0] * predicted, total_spend)
    iroas_hi = iroas_of(interval[1] * predicted, total_spend)

    rolling = []
    weeks = _weeks(test)
    for end in range(rolling_weeks, len(weeks) + 1):
        win = [d for w in weeks[end - rolling_weeks:end] for d in w]
        idx0 = test.index(win[0])
        s = sum(daily_spend[idx0:idx0 + len(win)])
        l = sum(d.treat_rev for d in win) - k_rev * sum(d.ctrl_rev for d in win)
        rolling.append({"weeks": f"{end - rolling_weeks + 1}-{end}", "start": win[0].date.isoformat(),
                        "end": win[-1].date.isoformat(), "incremental_revenue": round(l, 2),
                        "spend": round(s, 2), "iroas": None if s <= 0 else round(l / s, 4)})

    lift_orders = sum(d.treat_orders for d in test) - k_ord * sum(d.ctrl_orders for d in test)
    ctrl_orders = sum(d.ctrl_orders for d in test)
    aov = sum(d.ctrl_rev for d in test) / ctrl_orders if ctrl_orders > 0 else None
    iroas_ord = iroas_of(lift_orders * aov, total_spend) if aov is not None else None

    return Readout(
        design=design, pre_days=len(pre), test_days=len(test), scale_rev=k_rev, scale_orders=k_ord,
        actual_rev=actual, predicted_rev=predicted, lift_rev=lift, lift_pct=lift_pct, se_pct=se,
        lower_one_sided_pct=lower, interval_pct=interval, target_mde=target_mde,
        mde_reached=None if target_mde is None else lift_pct >= target_mde,
        significant=lower > 0, spend=total_spend, iroas_all_time=iroas_all,
        iroas_range=(iroas_lo, iroas_hi), rolling=rolling, lift_orders=lift_orders, control_aov=aov,
        iroas_orders_x_aov=iroas_ord, expected_iroas=expected_iroas, band=band,
        zone_low=zone(iroas_lo, expected_iroas, band), zone_high=zone(iroas_hi, expected_iroas, band),
        zone_point=zone(iroas_all, expected_iroas, band),
    )


def decision(r: Readout) -> List[str]:
    lines = []
    if not r.significant:
        lines.append("**Statistically inconclusive.** The 90% one-sided lower bound on lift is at or below zero.")
        lines.append(f"> {INCONCLUSIVE_RULE}")
        lines.append("If the idea is enticing enough, retest it with a different design. Often there's another "
                     "channel next in line: shelve this one to return to later and move on. There's no need to "
                     "test the same thing several times in a row just to prove it didn't work.")
        return lines
    if r.mde_reached is False:
        lines.append("The lift is above zero but below the MDE you planned for. Read it as a smaller effect than "
                     "the test was built to find, and size the next test for it.")
    if r.expected_iroas is not None:
        if r.zone_low and r.zone_low == r.zone_high:
            lines.append(f"Both ends of the iROAS range land {r.zone_low} (expected {r.expected_iroas:.2f}x, "
                         f"band ±{r.band:.0%}). They support the same action, so there's no need to split hairs.")
        else:
            lines.append(f"The iROAS range runs from {r.zone_low} to {r.zone_high}. The ends point to different "
                         "actions, so the range alone doesn't settle it.")
        if r.zone_point == "within the band":
            lines.append("Within the band you set before launch: act on the plan.")
        else:
            lines.append(f"The point estimate lands {r.zone_point}. Make a digestible change and retest, "
                         "or run a different test.")
    lines.append("To turn a favorable result into a budget decision: launch it, or launch with a second test of a "
                 "similar but different design (different treatment or control markets, or the inverse: launch "
                 "nationwide and keep a holdout control cell).")
    return lines


def _x(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.2f}x"


def render(r: Readout) -> str:
    mde = "n/a (no target given)" if r.target_mde is None else (
        f"{'Yes' if r.mde_reached else 'No'}: lift {r.lift_pct:+.1%} vs target {r.target_mde:.1%}")
    out = [
        "# Test readout",
        "",
        f"Design: {r.design}. Pre-period {r.pre_days} days, test {r.test_days} days. "
        "Treatment is the cell that kept its media; control is the cell that changed "
        "(went dark in a holdout).",
        "",
        "## 1. Was the MDE reached?",
        "",
        f"- {mde}",
        f"- Revenue: actual {r.actual_rev:,.0f} vs scaled control {r.predicted_rev:,.0f}, "
        f"incremental {r.lift_rev:,.0f}",
        f"- 90% interval on lift: {r.interval_pct[0]:+.1%} to {r.interval_pct[1]:+.1%}; "
        f"one-sided 90% lower bound {r.lower_one_sided_pct:+.1%}",
        "",
        "## 2. All-time and rolling iROAS",
        "",
        f"- All-time iROAS: {_x(r.iroas_all_time)} on {r.spend:,.0f} of spend "
        f"(range {_x(r.iroas_range[0])} to {_x(r.iroas_range[1])})",
    ]
    if r.rolling:
        out += ["", "| Weeks | From | To | Incremental revenue | Spend | iROAS |", "|---|---|---|---|---|---|"]
        for w in r.rolling:
            out.append(f"| {w['weeks']} | {w['start']} | {w['end']} | {w['incremental_revenue']:,.0f} | "
                       f"{w['spend']:,.0f} | {_x(w['iroas'])} |")
    out += [
        "",
        "## 3. Revenue lift beside orders lift × control AOV",
        "",
        f"- iROAS from revenue lift: {_x(r.iroas_all_time)}",
        f"- iROAS from orders lift × control AOV: {_x(r.iroas_orders_x_aov)} "
        f"({r.lift_orders:,.0f} incremental orders × {r.control_aov or 0:,.2f} control AOV)",
        "- A big gap between these two means the incremental orders had a different average order value "
        "than the control's.",
        "",
        "There are other checks, but these come first.",
        "",
        "## Decision",
        "",
    ]
    out += decision(r)
    out += ["", "Generated by test-readout-worksheet (Brinker Analytics). Normal approximation; "
            "confirm the result in your full analysis tool."]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--daily", required=True, help="date, cell (treatment/control), revenue, orders[, spend]")
    ap.add_argument("--pre-start", required=True)
    ap.add_argument("--pre-end", required=True)
    ap.add_argument("--test-start", required=True)
    ap.add_argument("--test-end", required=True)
    ap.add_argument("--spend", type=float, help="spend that differed between the cells over the test")
    ap.add_argument("--target-mde", type=float, help="the lift the test was sized to detect, e.g. 0.05")
    ap.add_argument("--expected-iroas", type=float, help="the iROAS your game plan expected")
    ap.add_argument("--band", type=float, default=0.2, help="act-on-it band around expected iROAS (default ±20%%)")
    ap.add_argument("--rolling-weeks", type=int, default=4)
    ap.add_argument("--design", default="holdout", choices=["holdout", "heavy-up"])
    ap.add_argument("--out", default="output")
    a = ap.parse_args(argv)
    f = dt.date.fromisoformat
    r = analyze(load(a.daily), f(a.pre_start), f(a.pre_end), f(a.test_start), f(a.test_end), a.spend,
                a.target_mde, a.expected_iroas, a.band, a.rolling_weeks, a.design)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "readout.md"), "w") as fh:
        fh.write(render(r))
    if r.rolling:
        with open(os.path.join(a.out, "rolling_iroas.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(r.rolling[0].keys()))
            w.writeheader()
            w.writerows(r.rolling)
    print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
