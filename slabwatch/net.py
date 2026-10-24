"""Tiny stdlib HTTP helpers (keeps the Render install light)."""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

UA = {"User-Agent": "slabwatch/0.1 (+https://github.com/ArqamWaheed/slabwatch)"}


class HTTPFail(RuntimeError):
    def __init__(self, status: int, body: str, url: str):
        super().__init__(f"HTTP {status} from {url.split('?')[0]}: {body[:300]}")
        self.status, self.body = status, body


def _open(req: urllib.request.Request, timeout: float) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted endpoints)
            return r.read()
    except urllib.error.HTTPError as e:
        raise HTTPFail(e.code, e.read().decode(errors="replace"), req.full_url) from None


def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 30,
             headers: dict[str, str] | None = None) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    return json.loads(_open(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout))


def post_json(url: str, payload: dict[str, Any], timeout: float = 120,
              headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={**UA, "Content-Type": "application/json", **(headers or {})},
    )
    return json.loads(_open(req, timeout) or b"{}")


def post_text(url: str, text: str, headers: dict[str, str] | None = None, timeout: float = 15) -> int:
    req = urllib.request.Request(url, data=text.encode(), headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.status


def download(url: str, dest: Path, timeout: float = 600) -> Path:
    """Stream a URL to disk (atomic rename). Skips if dest already exists and is non-empty."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r, \
            open(tmp, "wb") as f:  # noqa: S310
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.rename(dest)
    return dest
