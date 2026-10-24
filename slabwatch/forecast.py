"""Forecaster: predicts quantiles of the scale-free ratio, then converts to units and P(cross threshold).

Backends
  tabpfn_api    tabpfn_client.TabPFNRegressor (Prior Labs API; needs TABPFN_TOKEN). Used on Render.
  tabpfn_local  tabpfn.TabPFNRegressor (local weights; `pip install .[local]`, CPU <= 5000 rows).
  gbm           sklearn HistGradientBoostingRegressor(loss="quantile"), one model per quantile.
  naive         ratio = 1 at every quantile ("multiply it out"); a point forecast.
  last_ratio    ratio = last cycle's ratio at the same cut day (1 if unknown); a point forecast.

Both TabPFN packages: predict(X, output_type="quantiles", quantiles=[...]) -> list[np.ndarray],
one array per quantile (verified in tabpfn 9.2.0 regressor.py and tabpfn-client 0.6.1 estimator.py).

P(cross) method: the predicted quantiles q_i at levels a_i define a piecewise-linear CDF
F(v_i) = a_i. Between knots F is linear; beyond the outer knots (5% / 95%) the CDF is extended
linearly with the slope of the outermost segment and clipped to [0, 1]. P(cross T) = 1 - F(T).
We ask for 11 levels (0.05, 0.1, ..., 0.9, 0.95) so the CDF has resolution where it matters.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

QUANTILES = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
BACKENDS = ("naive", "last_ratio", "gbm", "tabpfn_local", "tabpfn_api")
# Chosen once on the houses 1-10 GroupKFold (vs max_leaf_nodes=15/300 iters: MAPE 8.5% vs 9.2%).
# That comparison used the same folds as the backtest, a mild selection bias noted in docs/DATA.md.
GBM_PARAMS = dict(loss="quantile", max_iter=150, learning_rate=0.05, max_depth=3, min_samples_leaf=40,
                  l2_regularization=1.0)


def monotone(values) -> np.ndarray:
    """Quantile crossing fix: sort each row (rearrangement, Chernozhukov et al. 2010)."""
    return np.sort(np.asarray(values, dtype=float), axis=-1)


def cdf_at(x: float, levels, values) -> float:
    """P(X <= x) from quantile knots (see module docstring)."""
    a = np.asarray(levels, float)
    v = monotone(values)
    if v[-1] - v[0] < 1e-12:            # degenerate (point forecast)
        return 1.0 if x >= v[0] else 0.0
    if x <= v[0]:
        span = v[1] - v[0]
        slope = (a[1] - a[0]) / span if span > 1e-12 else 0.0
        return float(max(0.0, a[0] - slope * (v[0] - x))) if slope else (a[0] if x == v[0] else 0.0)
    if x >= v[-1]:
        span = v[-1] - v[-2]
        slope = (a[-1] - a[-2]) / span if span > 1e-12 else 0.0
        return float(min(1.0, a[-1] + slope * (x - v[-1]))) if slope else 1.0
    i = int(np.searchsorted(v, x, side="right"))  # v[i-1] <= x < v[i]
    lo, hi = v[i - 1], v[i]
    if hi - lo < 1e-12:
        return float(a[i])
    return float(a[i - 1] + (a[i] - a[i - 1]) * (x - lo) / (hi - lo))


def p_cross(threshold: float, levels, values) -> float:
    """P(final units > threshold)."""
    return 1.0 - cdf_at(threshold, levels, values)


@dataclass
class Forecast:
    p10: float
    p50: float
    p90: float
    p_cross: float
    threshold: float
    levels: list[float]
    units: list[float]       # final-units quantiles at `levels`
    naive_units: float
    backend: str

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _value_at(level: float, levels, values) -> float:
    return float(np.interp(level, levels, monotone(values)))


class Forecaster:
    def __init__(self, backend: str = "gbm", quantiles=QUANTILES, token: str = "", seed: int = 0):
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {BACKENDS}")
        self.backend, self.q, self.token, self.seed = backend, tuple(quantiles), token, seed
        self._models = None

    # ---------------------------------------------------------------- fit
    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        if self.backend == "gbm":
            from sklearn.ensemble import HistGradientBoostingRegressor
            from threadpoolctl import threadpool_limits

            # Small data: shallow, regularised trees. One thread: with ~1-5k rows OpenMP thread
            # contention made 5-fold x 11 quantiles take 150 s instead of ~10 s on a 16-thread laptop.
            with threadpool_limits(1):
                self._models = [
                    HistGradientBoostingRegressor(**GBM_PARAMS, quantile=a, random_state=self.seed).fit(X, y)
                    for a in self.q
                ]
        elif self.backend == "tabpfn_local":
            try:
                from tabpfn import TabPFNRegressor  # type: ignore
            except ImportError:
                raise RuntimeError("tabpfn is not installed. `pip install -e .[local]` (pulls torch, ~2 GB).") \
                    from None
            if len(X) > 5000:
                raise RuntimeError(f"{len(X)} context rows > 5000 (CPU limit in the TabPFN README). Use --sample.")
            self._models = TabPFNRegressor(random_state=self.seed).fit(X, y)
        elif self.backend == "tabpfn_api":
            if not self.token:
                from slabwatch.config import MissingKey
                raise MissingKey("TABPFN_TOKEN", "tabpfn_api backend; get one at platform.priorlabs.ai")
            try:
                from tabpfn_client import TabPFNRegressor, set_access_token  # type: ignore
            except ImportError:
                raise RuntimeError("tabpfn-client is not installed. `pip install tabpfn-client`.") from None
            set_access_token(self.token)
            self._models = TabPFNRegressor(random_state=self.seed).fit(X, y)
        self._fitted = True
        return self

    # ---------------------------------------------------------------- predict
    def predict_ratio_quantiles(self, X, last_ratio=None) -> np.ndarray:
        """(n, len(q)) ratio quantiles."""
        X = np.asarray(X, float)
        n = len(X)
        if self.backend == "naive":
            return np.ones((n, len(self.q)))
        if self.backend == "last_ratio":
            lr = np.asarray(last_ratio if last_ratio is not None else np.full(n, np.nan), float)
            lr = np.clip(np.where(np.isfinite(lr), lr, 1.0), 0.25, 4.0)
            return np.repeat(lr[:, None], len(self.q), axis=1)
        if self._models is None:
            raise RuntimeError("call fit() first")
        if self.backend == "gbm":
            from threadpoolctl import threadpool_limits

            with threadpool_limits(1):
                out = np.column_stack([m.predict(X) for m in self._models])
        else:
            out = np.column_stack(self._models.predict(X, output_type="quantiles", quantiles=list(self.q)))
        return monotone(out)

    def forecast_one(self, features: dict, threshold: float, feature_names, cycle_days: int) -> Forecast:
        x = np.array([[float(features.get(k, math.nan)) for k in feature_names]])
        rq = self.predict_ratio_quantiles(x, last_ratio=[features.get("last_cycle_ratio", math.nan)])[0]
        naive = features["rate_so_far"] * cycle_days
        units = rq * naive
        so_far = features["units_so_far"]
        units = np.maximum(units, so_far)  # cannot end below what is already on the meter
        return Forecast(
            p10=_value_at(0.1, self.q, units), p50=_value_at(0.5, self.q, units),
            p90=_value_at(0.9, self.q, units), p_cross=p_cross(threshold, self.q, units),
            threshold=threshold, levels=list(self.q), units=[float(u) for u in units],
            naive_units=float(naive), backend=self.backend,
        )
