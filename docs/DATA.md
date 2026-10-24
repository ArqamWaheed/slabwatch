# Data

## PRECON (verified 2026-10-24 on houses 1-10)
- Source: Open Data Pakistan CKAN, `package_show?id=precon-pakistan-residential-electricity-consumption-dataset`.
  Licence on CKAN: **Creative Commons CCZero**. Resources listed by the API (sizes from CKAN):
  `precon-house-1-10.rar` 45.8 MB, `-11-20.rar` 45.1 MB, `-21-31.rar` 38.9 MB, `-31-42.rar` 45.3 MB, `metadata.csv` 4 KB.
  `slabwatch/data/precon.py` reads the URLs from the API at run time (none hardcoded). CKAN labels the RARs "ZIP"; they are RAR 4 (`Rar!\x1a\x07\x00`).
- Archive contents: `House1.csv` ... `House10.csv` at the archive root (15-35 MB each).
- Columns: `"Date_Time","Usage_kW",` then per-appliance columns that differ per house
  (House1: `AC_DR_kW,UPS_kW,LR_kW,Kitchen_kW,AC_DNR_kW,AC_BR_kW`; House9: `AC_LR_kW,AC_BR_kW,AC_kW,AC_kW.1,Kitchen_kW,WP_kW`).
  Only `Usage_kW` (whole house) is used.
- Timestamps: `"YYYY-MM-DD HH:MM:SS"`, local time, 1-minute steps, no duplicates. Span 2018-06-01 00:00 to 2019-05-31 23:59.
- Units: kW (average power over the minute). Daily kWh = mean(Usage_kW over the day) x 24.
- Gaps are whole days: every day present has >= 90% of minutes (3440 of 3440 house-days). House1 starts 2018-07-15
  (321 days); House6 starts 2018-11-14 (199 days); the rest have 365 days.
- Bad rows: House3 has 2 unparseable values (e.g. `0.950350.001`), House5 has 1; coerced to missing.
- Near-zero runs: House2 has 12 days < 0.5 kWh (2018-06-26..07-07), House3 79 days (2018-11-20..2019-02-06),
  House10 41 days (2019-01-05..02-15). A running fridge alone exceeds 0.5 kWh/day, so these are logger dropouts or a
  vacant house. `features.build_rows` treats days < 0.5 kWh as missing (`MIN_DAILY_KWH`); before this rule the
  ratio target reached 844,343 and broke every model.
- Median daily kWh (x30 = typical cycle): H1 12.6 (377), H2 8.4 (251), H3 42.4 (1271), H4 35.0 (1051), H5 10.2 (306),
  H6 17.5 (526), H7 14.2 (425), H8 11.1 (334), H9 7.1 (214), H10 10.4 (312). Only H2 and H9 are near 200.
- metadata.csv: 42 rows, `Website Name, Property_Area_sqft, ..., Connection_Type, No_of_People, ..., No_of_ACs, ...`
  (one header has a typo-space: `No_of _Water_Pumps`). Used: area, people, ACs, fans, fridges, floors, 3-phase flag.

### Extraction
- No `unar`/`unrar`/`7z` on the build laptop. Fallback is `libarchive-c` (pip) over the system `libarchive.so.13`.
- libarchive reports **"File CRC error"** in the last block of House3.csv (69 bytes short of 23,892,037) and
  House5.csv (189 bytes short of 25,989,309). Everything before decodes; `extract()` keeps it and trims the torn
  last line. Inferred: either the archive's final block or libarchive's RAR4 decoder; `unar` would tell (TO VERIFY).
- Install a CLI extractor for a clean run: `sudo apt install unar` (or `unrar`, `p7zip-full`).

## Training rows (`build-features`)
- 30-day windows every 15 days; a window needs all 30 days valid. Cuts at days 5, 7, 10, 14, 18, 21, 25.
- Houses 1-10: **201 windows, 1407 rows**, median ratio 0.991.
- `mean_temp_remaining` = actual Open-Meteo archive mean temperature of the remaining days (an OPTIMISTIC stand-in
  for a forecast). `mean_temp_remaining_clim` = 2008-2017 day-of-year climatology (15-day smoothing), before PRECON.
- `last_cycle_ratio` = previous 30-day window's ratio at the same cut (NaN when that window is incomplete; NaN live
  unless the previous cycle had readings). `prev_total_over_naive` = previous cycle total / current naive estimate
  (live: from the bill's history).
- Live readings are sparse; `cut_features` linearly interpolates the cumulative curve, which is exact for training
  (one point per day) and an approximation for live use (inferred, untested on real meters).

## Model choice note
GBM params (depth 3, 40 min leaf, l2 1.0, 150 iters) were picked after one comparison on the same houses 1-10 folds
(8.5% vs 9.2% MAPE for the first setting). That is a mild selection bias; re-run on houses 11-42 to confirm.

## Weather
Open-Meteo archive `archive-api.open-meteo.com/v1/archive` and forecast `api.open-meteo.com/v1/forecast`
(`past_days=14`, `forecast_days=16`), daily `temperature_2m_mean,temperature_2m_max`, timezone Asia/Karachi.
Both checked live 2026-10-24. Cached under `data/cache/weather/`.
