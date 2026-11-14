import csv
import datetime as dt
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import readout as ro  # noqa: E402

EX = ROOT / "example_data" / "EXAMPLE_daily.csv"
D = dt.date.fromisoformat
ARGS = dict(pre_start=D("2026-05-04"), pre_end=D("2026-08-23"), test_start=D("2026-08-24"),
            test_end=D("2026-10-04"))


def write_days(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    w = csv.writer(f)
    w.writerow(["date", "cell", "revenue", "orders", "spend"])
    w.writerows(rows)
    f.close()
    return f.name


def null_test(seed=1, lift=0.0):
    """Treatment and control move together; `lift` added to treatment during the test."""
    rnd = random.Random(seed)
    rows, start = [], D("2026-05-04")
    for i in range(154):
        d = start + dt.timedelta(days=i)
        common = rnd.gauss(1, 0.03)
        t = 9000 * common * rnd.gauss(1, 0.06)
        c = 6000 * common * rnd.gauss(1, 0.06)
        if i >= 112:
            t *= 1 + lift
        rows.append([d.isoformat(), "treatment", f"{t:.2f}", round(t / 80), "800" if i >= 112 else ""])
        rows.append([d.isoformat(), "control", f"{c:.2f}", round(c / 80), ""])
    return write_days(rows)


class Example(unittest.TestCase):
    def setUp(self):
        self.r = ro.analyze(ro.load(str(EX)), spend=None, target_mde=0.05, expected_iroas=1.3, **ARGS)

    def test_order_of_checks_in_readout(self):
        text = ro.render(self.r)
        a = text.index("1. Was the MDE reached?")
        b = text.index("2. All-time and rolling iROAS")
        c = text.index("3. Revenue lift beside orders lift")
        self.assertTrue(a < b < c)

    def test_iroas_is_incremental_revenue_over_spend(self):
        self.assertAlmostEqual(self.r.iroas_all_time, self.r.lift_rev / self.r.spend)
        self.assertAlmostEqual(self.r.spend, 800 * 42)

    def test_holdout_detected(self):
        self.assertTrue(self.r.significant)
        self.assertTrue(self.r.mde_reached)

    def test_rolling_windows(self):
        self.assertEqual(len(self.r.rolling), 3)  # 6 test weeks, 4-week windows
        self.assertEqual(self.r.rolling[0]["weeks"], "1-4")

    def test_orders_x_aov_close_to_revenue_iroas(self):
        self.assertAlmostEqual(self.r.iroas_orders_x_aov, self.r.iroas_all_time, delta=0.2)


class Inconclusive(unittest.TestCase):
    def test_null_result_prints_the_rule(self):
        r = ro.analyze(ro.load(null_test(seed=3)), spend=None, target_mde=0.05, **ARGS)
        self.assertFalse(r.significant)
        text = ro.render(r)
        self.assertIn("Statistically inconclusive", text)
        self.assertIn(ro.INCONCLUSIVE_RULE, text)

    def test_rule_wording(self):
        self.assertEqual(ro.INCONCLUSIVE_RULE,
                         "We failed to prove that it was a home run, which for our strategy is as good as a loss. "
                         "It doesn't mean the door is shut forever. It just means we have to move on for now.")


class Band(unittest.TestCase):
    def test_zone(self):
        self.assertEqual(ro.zone(1.0, 1.0, 0.2), "within the band")
        self.assertEqual(ro.zone(0.7, 1.0, 0.2), "below the band")
        self.assertEqual(ro.zone(1.3, 1.0, 0.2), "above the band")
        self.assertEqual(ro.zone(None, 1.0, 0.2), "")


class InputChecks(unittest.TestCase):
    def test_duplicate_rows_rejected(self):
        p = write_days([["2026-05-04", "treatment", "1", "1", ""], ["2026-05-04", "treatment", "1", "1", ""]])
        with self.assertRaises(SystemExit):
            ro.load(p)

    def test_partial_weeks_rejected(self):
        with self.assertRaises(SystemExit):
            ro.analyze(ro.load(str(EX)), spend=None, target_mde=None, pre_start=D("2026-05-04"),
                       pre_end=D("2026-08-23"), test_start=D("2026-08-24"), test_end=D("2026-10-01"))

    def test_missing_days_rejected(self):
        days = ro.load(str(EX))
        del days[D("2026-09-01")]
        with self.assertRaises(SystemExit):
            ro.analyze(days, spend=None, target_mde=None, **ARGS)


if __name__ == "__main__":
    unittest.main()
