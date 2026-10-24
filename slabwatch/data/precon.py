"""PRECON (LUMS, e-Energy '19): download from Open Data Pakistan, extract RARs, aggregate to daily kWh.

Real format (inspected 2026-10-24 on houses 1-10, see docs/DATA.md):
  HouseN.csv, header `"Date_Time","Usage_kW",<appliance>_kW,...`
  Date_Time = "YYYY-MM-DD HH:MM:SS" local time, 1-minute steps, 2018-06-01 .. 2019-05-31.
  Usage_kW = whole-house average power (kW) over the minute. kWh for a day = mean(kW) * 24.
  Some houses start late (House1: 2018-07-15) and a few rows are garbled (House3: '0.950350.001').
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from slabwatch.config import DATA
from slabwatch.net import download, get_json

CKAN = "https://opendata.com.pk/api/3/action/package_show"
PACKAGE_ID = "precon-pakistan-residential-electricity-consumption-dataset"
PRECON_DIR = DATA / "precon"
RAW, EXTRACTED = PRECON_DIR / "raw", PRECON_DIR / "extracted"
DAILY = PRECON_DIR / "daily.parquet"
META = PRECON_DIR / "metadata.parquet"
MIN_COVERAGE = 0.9  # a day counts only if >= 90% of its 1440 minutes are present


def list_resources() -> list[dict]:
    """Ask CKAN for the current file list (no hardcoded URLs)."""
    res = get_json(CKAN, {"id": PACKAGE_ID})["result"]["resources"]
    out = []
    for r in res:
        url = r.get("url", "")
        if url.endswith(".rar") or url.endswith(".csv"):
            out.append({"name": r.get("name"), "url": url, "size": r.get("size"),
                        "file": url.rsplit("/", 1)[-1]})
    return out


def fetch(which: str = "1-10") -> list[Path]:
    """Download metadata.csv + the RAR(s). which = '1-10' | '11-20' | '21-31' | '31-42' | 'all'."""
    got = []
    for r in list_resources():
        f = r["file"]
        if f.endswith(".csv") or which == "all" or f"house-{which}." in f:
            print(f"  {f} ({(r['size'] or 0) / 1e6:.1f} MB)", file=sys.stderr)
            got.append(download(r["url"], RAW / f))
    return got


# ---------------------------------------------------------------- extraction
def _cli_extractor() -> list[str] | None:
    for tool, args in (("unar", ["-f", "-o"]), ("unrar", ["x", "-o+"]), ("7z", ["x", "-y"])):
        if shutil.which(tool):
            return [tool, *args]
    return None


def extract(rar: Path, out: Path = EXTRACTED) -> list[str]:
    """Extract one RAR. Prefers unar/unrar/7z; falls back to libarchive-c (pip) if libarchive.so exists.

    Returns warnings. libarchive 3.6 reports a CRC error on the final block of House3/House5
    (<=189 bytes short); we keep what decoded and the aggregator drops the torn last line.
    """
    out.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    cli = _cli_extractor()
    if cli:
        tool = cli[0]
        cmd = [*cli, str(out), str(rar)] if tool == "unar" else (
            [*cli, str(rar), str(out) + "/"] if tool == "unrar" else [*cli, f"-o{out}", str(rar)])
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        return warnings
    try:
        import libarchive  # type: ignore
    except (ImportError, OSError):
        raise RuntimeError(
            "No RAR extractor found. Install one of: `sudo apt install unar` (or unrar / p7zip-full), "
            "or `pip install libarchive-c` (needs libarchive13, present on most Ubuntu installs)."
        ) from None
    with libarchive.file_reader(str(rar)) as arc:
        for entry in arc:
            if entry.isdir:
                continue
            dest = out / Path(entry.pathname).name  # flatten; never trust archive paths
            n = 0
            with open(dest, "wb") as f:
                try:
                    for block in entry.get_blocks():
                        f.write(block)
                        n += len(block)
                except libarchive.ArchiveError as e:  # keep partial data, report it
                    warnings.append(f"{dest.name}: {getattr(e, 'msg', e)} after "
                                    f"{n}/{entry.size} bytes; torn tail dropped")
            _trim_to_last_newline(dest)
    return warnings


def _trim_to_last_newline(path: Path) -> None:
    """Drop a partial final line (from a torn archive block) so CSV parsers don't choke on it."""
    with open(path, "rb+") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return
        f.seek(max(size - 4096, 0))
        tail = f.read()
        if tail.endswith(b"\n"):
            return
        cut = tail.rfind(b"\n")
        if cut >= 0:
            f.truncate(size - len(tail) + cut + 1)


# ---------------------------------------------------------------- aggregation
def house_daily(csv: Path):
    """1-minute Usage_kW -> one row per local day: kwh, coverage (fraction of 1440 minutes)."""
    import pandas as pd

    _trim_to_last_newline(csv)
    df = pd.read_csv(csv, usecols=["Date_Time", "Usage_kW"], dtype=str, on_bad_lines="skip")
    t = pd.to_datetime(df["Date_Time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    kw = pd.to_numeric(df["Usage_kW"], errors="coerce")
    ok = t.notna() & kw.notna() & (kw >= 0) & (kw < 100)  # 100 kW: far above any home here
    d = pd.DataFrame({"t": t[ok], "kw": kw[ok]}).drop_duplicates("t")
    g = d.groupby(d["t"].dt.normalize())["kw"].agg(["mean", "count"])
    out = pd.DataFrame({
        "date": g.index,
        "kwh": g["mean"] * 24.0,           # mean power over the day x 24 h (assumes gaps look like the rest)
        "coverage": g["count"] / 1440.0,
        "bad_rows": int((~ok).sum()),
    }).reset_index(drop=True)
    return out


def house_id(path: Path) -> int:
    return int("".join(ch for ch in path.stem if ch.isdigit()))


def load_metadata():
    import pandas as pd

    m = pd.read_csv(RAW / "metadata.csv")
    m.columns = [c.strip().replace(" ", "") for c in m.columns]
    m["house"] = m["WebsiteName"].str.extract(r"(\d+)").astype(int)
    keep = {"house": "house", "Property_Area_sqft": "area_sqft", "No_of_People": "people",
            "No_of_ACs": "n_acs", "No_of_Fans": "n_fans", "No_of_Refrigerators": "n_fridges",
            "Connection_Type": "connection", "No_of_Floors": "floors"}
    m = m[list(keep)].rename(columns=keep)
    m["three_phase"] = m["connection"].str.contains("3", na=False).astype(int)
    return m.drop(columns=["connection"])


def aggregate() -> dict:
    """All extracted HouseN.csv -> data/precon/daily.parquet (+ metadata.parquet)."""
    import pandas as pd

    files = sorted(EXTRACTED.glob("House*.csv"), key=house_id)
    if not files:
        raise RuntimeError(f"No HouseN.csv under {EXTRACTED}. Run `python -m slabwatch fetch-data` first.")
    parts = []
    for f in files:
        d = house_daily(f)
        d.insert(0, "house", house_id(f))
        parts.append(d)
        print(f"  house {house_id(f):>2}: {len(d)} days, median {d['kwh'].median():.1f} kWh/day, "
              f"{int(d['bad_rows'].iloc[0]) if len(d) else 0} bad rows", file=sys.stderr)
    daily = pd.concat(parts, ignore_index=True).drop(columns=["bad_rows"])
    daily.to_parquet(DAILY, index=False)
    meta = load_metadata()
    meta.to_parquet(META, index=False)
    return {"houses": int(daily["house"].nunique()), "days": int(len(daily)),
            "full_days": int((daily["coverage"] >= MIN_COVERAGE).sum()),
            "first": str(daily["date"].min().date()), "last": str(daily["date"].max().date()),
            "daily": str(DAILY), "metadata": str(META)}


def fetch_and_build(which: str = "1-10") -> dict:
    warnings = []
    for p in fetch(which):
        if p.suffix == ".rar":
            print(f"extracting {p.name}", file=sys.stderr)
            warnings += extract(p)
    info = aggregate()
    info["extract_warnings"] = warnings
    return info
