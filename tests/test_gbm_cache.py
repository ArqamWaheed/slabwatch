import numpy as np

from slabwatch import config
from slabwatch.forecast import Forecaster


def test_gbm_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    rng = np.random.default_rng(0)
    X, y = rng.normal(size=(300, 4)), rng.normal(1, 0.1, 300)
    a = Forecaster("gbm", cache=True).fit(X, y)
    assert len(list(tmp_path.glob("gbm-*.pkl.gz"))) == 1
    b = Forecaster("gbm", cache=True).fit(X, y)  # loaded, not refitted
    np.testing.assert_allclose(a.predict_ratio_quantiles(X[:5]), b.predict_ratio_quantiles(X[:5]))
    Forecaster("gbm", cache=True).fit(X, y + 0.01)  # different rows -> different key
    assert len(list(tmp_path.glob("gbm-*.pkl.gz"))) == 2


def test_gbm_no_cache_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path)
    rng = np.random.default_rng(1)
    Forecaster("gbm").fit(rng.normal(size=(200, 3)), rng.normal(size=200))
    assert not list(tmp_path.iterdir())
