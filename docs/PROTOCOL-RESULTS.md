# Protocol results (dev/test, see PROTOCOL.md)

Test run 2026-10-24T13:28:23+00:00 · weather `clim` · dev homes 20 (3122 rows) · test homes 21 (3066 rows). Generated; do not edit.

## Chosen on dev (mean pinball loss of the ratio, out-of-fold)

| candidate | dev pinball |
|---|---|
| blend | 0.03605 |
| tabpfn_ratio | 0.03707 |
| tabpfn_logratio | 0.03761 |
| gbm_B | 0.03879 |
| gbm_A | 0.03908 |
| gbm_C | 0.04056 |

Chosen: {'gbm': 'gbm_B', 'tabpfn': 'tabpfn_ratio', 'blend': 'blend'}

## Test homes, scored once

| model | calibration | pinball | MAPE | P10-P90 coverage (80%) | Brier | precision | recall |
|---|---|---|---|---|---|---|---|
| naive | - | 0.0590 | 11.0% | 0.0% | 0.0780 | 90.8% | 93.3% |
| gbm | raw | 0.0327 | 8.2% | 69.3% | 0.0455 | 93.3% | 93.6% |
| gbm | calibrated | 0.0326 | 8.2% | 82.0% | 0.0444 | 93.8% | 93.2% |
| tabpfn | raw | 0.0347 | 8.7% | 89.6% | 0.0441 | 93.0% | 94.2% |
| tabpfn | calibrated | 0.0342 | 8.7% | 81.8% | 0.0441 | 93.2% | 94.0% |
| blend | raw | 0.0319 | 8.1% | 84.9% | 0.0429 | 92.8% | 94.4% |
| blend | calibrated | 0.0319 | 8.1% | 82.4% | 0.0427 | 93.4% | 94.1% |

## Test MAPE by cut day (calibrated)

| model | day 5 | day 7 | day 10 | day 14 | day 18 | day 21 | day 25 |
|---|---|---|---|---|---|---|---|
| naive | 18.1% | 16.3% | 13.7% | 10.7% | 7.9% | 6.2% | 3.7% |
| gbm | 13.4% | 11.4% | 9.8% | 8.0% | 6.2% | 5.0% | 3.7% |
| tabpfn | 16.4% | 14.2% | 10.5% | 8.0% | 5.6% | 4.1% | 2.3% |
| blend | 14.1% | 12.2% | 9.8% | 7.8% | 5.7% | 4.4% | 2.8% |
