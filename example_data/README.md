# Example data

Everything in this folder is made up. `scripts/make_example_data.py` generated it with a fixed seed, so you can rebuild the same file. It comes from no store, client or ad account.

- `EXAMPLE_daily.csv`: daily revenue and orders for a treatment cell and a control cell, 16 weeks of history (May 4 to Aug 23, 2026) and a 6-week holdout (Aug 24 to Oct 4, 2026). In the holdout the control cell goes dark and the treatment cell keeps its media, with $800 a day of spend on the treatment rows.

How much revenue the control loses when it goes dark, and how noisy each cell is, are settings in the script. Don't read the example result as a benchmark.
