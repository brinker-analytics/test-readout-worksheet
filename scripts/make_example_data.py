#!/usr/bin/env python3
"""Seeded generator for the made-up example: a 6-week geo holdout after 16 weeks of history.

Not from any store, client or ad account. The true lift and noise are settings below.
"""
import csv
import datetime as dt
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "example_data"
random.seed(20261113)
START = dt.date(2026, 5, 4)      # a Monday
PRE_DAYS = 16 * 7
TEST_DAYS = 6 * 7
AOV = 80.0
TREAT_BASE = 9000.0             # treatment cell daily revenue with media on
CTRL_BASE = 6000.0              # control cell daily revenue with media on
MEDIA_SHARE_CTRL = 0.12         # share of control revenue that goes away when it goes dark
NOISE = 0.06
DAILY_SPEND_TREAT = 800.0       # media kept on in the treatment cell during the test


def main():
    OUT.mkdir(exist_ok=True)
    with open(OUT / "EXAMPLE_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "cell", "revenue", "orders", "spend"])
        for i in range(PRE_DAYS + TEST_DAYS):
            d = START + dt.timedelta(days=i)
            season = 1 + 0.08 * math.sin(i / 14)
            weekday = 1.1 if d.weekday() >= 5 else 0.96
            common = season * weekday * random.gauss(1, 0.03)
            t = TREAT_BASE * common * random.gauss(1, NOISE)
            c = CTRL_BASE * common * random.gauss(1, NOISE)
            in_test = i >= PRE_DAYS
            if in_test:
                c *= 1 - MEDIA_SHARE_CTRL
            to = max(0, round(t / AOV * random.gauss(1, 0.03)))
            co = max(0, round(c / AOV * random.gauss(1, 0.03)))
            w.writerow([d.isoformat(), "treatment", f"{t:.2f}", to, f"{DAILY_SPEND_TREAT:.2f}" if in_test else ""])
            w.writerow([d.isoformat(), "control", f"{c:.2f}", co, ""])


if __name__ == "__main__":
    main()
