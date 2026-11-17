# test-readout-worksheet

Turn a finished geo test's daily numbers into a one-page readout, with the checks in the order I read them, and the decision options written out at the end.

> **Built by [Brinker Analytics](https://brinkeranalytics.com).** Eric Brinker's marketing-measurement practice for DTC brands.
> **Contact:** [eric@brinkeranalytics.com](mailto:eric@brinkeranalytics.com) or the [contact page](https://brinkeranalytics.com/contact).

## What it is, and what it isn't

**It is a readout worksheet.** It assumes you already understand your baselines, their noise, and the MDE you wanted to see before the test started. It takes daily revenue and orders for a treatment cell and a control cell and writes `readout.md`.

**It isn't a design or analysis library.** It scales the control to the treatment on the pre-period and reads the gap with a normal approximation. It doesn't correct for week-to-week autocorrelation, so the interval can read too narrow. For market selection, power simulation and a full analysis, use the open-source tools built for it: [GeoLift](https://github.com/facebookincubator/GeoLift) (Meta), [Trimmed Match](https://github.com/google/trimmed_match) (Google) or [Meridian GeoX](https://developers.google.com/meridian/geox/intro-to-geox) (Google). Before a test, the [geo-test-pretest-checks](https://github.com/brinker-analytics/geo-test-pretest-checks) repo covers the go or no-go.

## The order of the checks

1. **Was the MDE reached?** The lift against the scaled control, next to the MDE the test was sized for, with a 90% interval and the one-sided 90% lower bound.
2. **All-time iROAS and rolling iROAS.** iROAS over the whole test, then over rolling windows of several weeks (4 by default), so you can see whether the result held or came from one stretch.
3. **iROAS from revenue lift beside iROAS from orders lift × the control's AOV.** Two routes to a similar number. If they're close, the read is steadier.

There are other checks, but these come first.

In a holdout, the treatment is the cell that keeps its media. The control goes dark, and the lift is what the media adds where it keeps running. For a heavy-up, the treatment is the cell that got the extra spend.

## The decision

The readout ends with the options:

- **Favorable:** launch it, or launch with a second test of a similar but different design: different treatment or control markets, or the inverse, where the channel launches nationwide and keeps a holdout control cell.
- **Against your game plan:** if you give `--expected-iroas`, the readout checks the result against a band around it (±20% by default, set with `--band`). Within the band, act on the plan. Far above or below it, make a digestible change and retest, or run a different test. If both ends of the iROAS range land in the same place, there's no need to split hairs.
- **Statistically inconclusive:** the readout says so, in these words: "We failed to prove that it was a home run, which for our strategy is as good as a loss. It doesn't mean the door is shut forever. It just means we have to move on for now." If the idea is enticing enough, retest it with a different design. Often another channel is next in line, so shelve this one and move on.

## Run it on the example data

Python 3.9 or newer, standard library only.

```bash
python readout.py --daily example_data/EXAMPLE_daily.csv \
  --pre-start 2026-05-04 --pre-end 2026-08-23 \
  --test-start 2026-08-24 --test-end 2026-10-04 \
  --target-mde 0.05 --expected-iroas 1.3 --out output
```

The example is made up (see `example_data/README.md`): 16 weeks of history and a 6-week holdout. On it, the lift is +14.5% against a 5% MDE, all-time iROAS is 1.45x (range 1.17x to 1.73x), the three rolling 4-week windows read 1.50x, 1.49x and 1.45x, and orders lift × control AOV gives 1.41x. The committed readout is in `example_output/readout.md`.

## Run it on your own data

1. Export daily revenue and orders for the treatment cell and the control cell into one file: `date`, `cell` (`treatment` or `control`), `revenue`, `orders`. Add a `spend` column on the treatment rows for the spend that differed between the cells, or pass the total with `--spend`.
2. Pick a pre-period at least as long as the test, with no changes to either cell.
3. Use whole weeks for the test.
4. Run `readout.py` with your dates, the MDE you sized the test for, and the iROAS your game plan expected.

The script stops if a day is missing, a row appears twice, or the test isn't whole weeks.

## What to do with this

- **If the MDE was reached and the rolling iROAS holds steady,** take the result to the decision maker with the game plan you agreed before launch.
- **If the rolling iROAS swings a lot from window to window,** look at what changed in those weeks before you trust the all-time number.
- **If revenue-lift iROAS and orders-lift × AOV iROAS are far apart,** find out what moved order value in the treatment cell before you scale.
- **If the result is inconclusive,** don't rerun the same test just to prove it didn't work. Retest with a different design only if the idea is still worth it, or move to the next channel on your list.
- **Whatever the result,** keep a test running or in cooldown. Almost any time of year there's something worth testing.

If you want a second opinion on your readout before you move budget on it, send me a note and we'll talk it through: [Get in touch](https://brinkeranalytics.com/contact).

Reading a finished test into a budget move? [Would It Have Sold Anyway?](https://brinkeranalytics.com/guides/would-it-have-sold-anyway) is the path from a first-channel choice to that move. It also covers the readout.

## Free reading on brinkeranalytics.com

- [One-page incrementality test readout template](https://brinkeranalytics.com/insights/test-readout-template)
- [How to run a geo holdout test, step by step](https://brinkeranalytics.com/insights/first-geo-holdout-step-by-step)
- [Ending incrementality tests too early?](https://brinkeranalytics.com/insights/lift-tests-ending-too-early)
- [Geo test power analysis: will your test see the lift?](https://brinkeranalytics.com/insights/geo-test-power-check)
- [Matched market testing vs. synthetic control for DTC](https://brinkeranalytics.com/insights/matched-market-vs-synthetic-control)
- [Incrementality testing framework for DTC brands: 7 steps](https://brinkeranalytics.com/insights/incrementality-testing-framework-dtc-brands)

## Files

```
readout.py                     the script
example_data/                  made-up example data and how it was generated
example_output/                readout.md and rolling_iroas.csv from the example
scripts/make_example_data.py   seeded generator for the example data
tests/test_readout.py          checks the order of the checks, iROAS math, inconclusive wording and input errors
```

Run the tests with `python -m unittest discover -s tests`.

## License

The code is MIT licensed (see `LICENSE`). The documentation, including this README, is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (see `LICENSE-docs`). If you reuse it, please credit Eric Brinker at [Brinker Analytics](https://www.brinkeranalytics.com).
