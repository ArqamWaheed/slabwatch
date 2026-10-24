"""Backtest entry point (same as `python -m slabwatch backtest`).

  python scripts/backtest.py --models naive,last_ratio,gbm
  python scripts/backtest.py --models naive,gbm,tabpfn_local --sample 3000
  python scripts/backtest.py --models gbm,tabpfn_api --weather clim
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slabwatch.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["backtest", *sys.argv[1:]]))
