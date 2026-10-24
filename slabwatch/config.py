"""Settings from the environment, with a stdlib .env loader (no python-dotenv dependency)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("SLABWATCH_DATA", ROOT / "data"))
RESULTS = ROOT / "results"
CACHE = DATA / "cache"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal KEY=VALUE loader. Existing env vars win. Strips trailing ' # comments'."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "")
    return v if v != "" else default


class MissingKey(RuntimeError):
    """A service was used without its key. The message says which env var to set."""

    def __init__(self, var: str, why: str):
        super().__init__(f"{var} is not set ({why}). Add it to .env (see .env.example) "
                         f"and run `python -m slabwatch doctor`.")
        self.var = var


@dataclass(frozen=True)
class Settings:
    tabpfn_token: str
    gemma_provider: str          # google | ollama
    google_api_key: str
    ollama_url: str
    gemma_model: str
    embed_model: str
    database_url: str
    browserbase_api_key: str
    browserbase_project_id: str
    serpapi_key: str
    ntfy_topic: str
    ntfy_server: str
    temporal_address: str
    temporal_namespace: str
    temporal_queue: str
    slab_threshold: float
    penalty_months: int
    lat: float
    lon: float
    cycle_days: int
    forecast_backend: str        # tabpfn_api | tabpfn_local | gbm | naive

    def require(self, field: str, var: str, why: str) -> str:
        val = getattr(self, field)
        if not val:
            raise MissingKey(var, why)
        return val


def settings() -> Settings:
    load_dotenv()
    provider = env("GEMMA_PROVIDER", "google").lower()
    default_model = "gemma-3-27b-it" if provider == "google" else "gemma3:4b"
    return Settings(
        tabpfn_token=env("TABPFN_TOKEN"),
        gemma_provider=provider,
        google_api_key=env("GOOGLE_API_KEY"),
        ollama_url=env("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        gemma_model=env("GEMMA_MODEL", default_model),
        embed_model=env("EMBED_MODEL", "embeddinggemma"),
        database_url=env("DATABASE_URL"),
        browserbase_api_key=env("BROWSERBASE_API_KEY"),
        browserbase_project_id=env("BROWSERBASE_PROJECT_ID"),
        serpapi_key=env("SERPAPI_KEY"),
        ntfy_topic=env("NTFY_TOPIC"),
        ntfy_server=env("NTFY_SERVER", "https://ntfy.sh").rstrip("/"),
        temporal_address=env("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=env("TEMPORAL_NAMESPACE", "default"),
        temporal_queue=env("TEMPORAL_TASK_QUEUE", "slabwatch"),
        slab_threshold=float(env("SLAB_THRESHOLD", "200")),
        penalty_months=int(env("PENALTY_MONTHS", "6")),
        lat=float(env("LAT", "31.55")),
        lon=float(env("LON", "74.34")),
        cycle_days=int(env("CYCLE_DAYS", "30")),
        forecast_backend=env("FORECAST_BACKEND", "tabpfn_api" if env("TABPFN_TOKEN") else "gbm"),
    )
