# Evaluation protocol (written and committed before the test homes were scored)

The first backtest (`docs/RESULTS.md`, GroupKFold over all 41 homes) had one weakness: the GBM settings had been picked on homes 1–10, which are inside those folds. This protocol removes that bias. Its commit timestamp is the proof that it came first.

## Split
- **Dev homes:** PRECON homes with an **odd** house number (20 homes). Every choice is made here.
- **Test homes:** **even** house numbers (21 homes). They are scored **once**, by `python -m slabwatch protocol --final`, after this file is committed. Nothing is changed after that run. If something has to change, the change and both results are reported.

## Choices made on dev only (5-fold GroupKFold by house, out-of-fold predictions)
- **Candidates:**
  - `gbm`: three settings, A (the current one), B (more depth) and C (more regularised).
  - `tabpfn_api`: target `ratio`, or target `log(ratio)`.
  - `blend`: the per-quantile mean of the best GBM and the best TabPFN.
- **Selection metric:** mean pinball loss over the 11 quantile levels of the ratio. Pinball loss is a proper scoring rule for quantiles, so this scores the whole band, not only the middle.
- **Calibration:** for each quantile level *a*, a shift *d_a* in log-ratio space is chosen so that exactly a share *a* of dev out-of-fold rows fall at or below the shifted quantile. The quantiles are then re-sorted. This is a split-conformal-style recalibration. It is fitted on dev and applied unchanged to test, and the same procedure is used for every model.

## Test (once)
- Each selected candidate is refitted on all dev rows, predicts the test rows, and has its dev calibration applied.
- **Reported:** MAPE of the final units (P50), P10–P90 coverage (nominal 80%), Brier score and precision/recall of the cliff call, and pinball loss, overall and by cut day. Calibrated and uncalibrated results are both shown.
- **Cliff event:** the same as before, final units above that home's median 30-day total (synthetic, because PRECON homes are larger than a 200-unit household).
- **Weather:** `clim` (day-of-year climatology for the remaining days), the honest no-forecast setting.

## What would count as TabPFN "winning"
A lower test pinball loss **and** a lower test MAPE than the selected GBM. Anything else is reported as a tie or a loss, in those words.
