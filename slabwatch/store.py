"""Postgres / Tiger Cloud persistence. Degrades gracefully:
  - timescaledb present  -> readings and forecasts become hypertables (create_hypertable)
  - pgvector present     -> tariff_docs.embedding vector(EMBED_DIM) + HNSW index
  - embeddings available -> hybrid search (full-text + vector, Reciprocal Rank Fusion k=60)
  - otherwise            -> full-text search only
"""
from __future__ import annotations

import json
from importlib import resources

from slabwatch.config import Settings, settings

EMBED_DIM = 768   # embeddinggemma output size; TO VERIFY with `ollama show embeddinggemma`
RRF_K = 60


def connect(s: Settings | None = None):
    s = s or settings()
    url = s.require("database_url", "DATABASE_URL", "Tiger Cloud / Postgres connection string")
    try:
        import psycopg
    except ImportError:
        raise RuntimeError("pip install 'psycopg[binary]'") from None
    return psycopg.connect(url, autocommit=True)


def init_db(s: Settings | None = None) -> dict:
    sql = resources.files("slabwatch").joinpath("sql/schema.sql").read_text()
    report = {}
    with connect(s) as c:
        c.execute(sql)
        report["core"] = "ok"
        for ext in ("timescaledb", "vector"):
            try:
                c.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                report[ext] = "ok"
            except Exception as e:  # noqa: BLE001
                report[ext] = f"unavailable: {str(e).splitlines()[0]}"
        if report["timescaledb"] == "ok":
            for t in ("readings", "forecasts"):
                c.execute("SELECT create_hypertable(%s, 'ts', if_not_exists => TRUE, migrate_data => TRUE)", (t,))
            report["hypertables"] = ["readings", "forecasts"]
        if report["vector"] == "ok":
            c.execute(f"ALTER TABLE tariff_docs ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIM})")
            c.execute("CREATE INDEX IF NOT EXISTS tariff_docs_emb ON tariff_docs "
                      "USING hnsw (embedding vector_cosine_ops)")
    return report


def has_embedding_column(c) -> bool:
    return bool(c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='tariff_docs' "
                          "AND column_name='embedding'").fetchone())


_ST = {}


def _embed_local(text: str) -> list[float] | None:
    """BAAI/bge-base-en-v1.5 (MIT, 768-d) via sentence-transformers, run on this machine."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    if "m" not in _ST:
        _ST["m"] = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _ST["m"].encode([text], normalize_embeddings=True)[0].tolist()


def embed(text: str, s: Settings | None = None) -> list[float] | None:
    """Open embedding model: Ollama (/api/embed, e.g. embeddinggemma) if reachable, else bge-base locally.
    Returns None if neither is available (hybrid search then degrades to full-text only)."""
    s = s or settings()
    from slabwatch.net import post_json

    try:
        r = post_json(f"{s.ollama_url}/api/embed", {"model": s.embed_model, "input": text}, timeout=60)
        v = r["embeddings"][0]
        return v if len(v) == EMBED_DIM else None
    except Exception:  # noqa: BLE001
        v = _embed_local(text)
        return v if v and len(v) == EMBED_DIM else None


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


# ---------------------------------------------------------------- writes
def upsert_household(hid: str, **fields) -> None:
    cols = ["id", *fields]
    vals = [hid, *[json.dumps(v) if isinstance(v, dict) else v for v in fields.values()]]
    upd = ", ".join(f"{k}=EXCLUDED.{k}" for k in fields) or "id=EXCLUDED.id"
    with connect() as c:
        c.execute(f"INSERT INTO households ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
                  f"ON CONFLICT (id) DO UPDATE SET {upd}", vals)


def add_reading(hid: str, ts, reading_kwh: float, source: str, confidence=None, label=None) -> None:
    with connect() as c:
        c.execute("INSERT INTO households (id) VALUES (%s) ON CONFLICT DO NOTHING", (hid,))
        c.execute("INSERT INTO readings VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (household_id, ts) DO UPDATE "
                  "SET reading_kwh=EXCLUDED.reading_kwh, source=EXCLUDED.source", (hid, ts, reading_kwh, source,
                                                                                    confidence, label))


def readings(hid: str, since=None) -> list[tuple]:
    with connect() as c:
        q = "SELECT ts, reading_kwh, source FROM readings WHERE household_id=%s"
        args: list = [hid]
        if since is not None:
            q += " AND ts >= %s"
            args.append(since)
        return c.execute(q + " ORDER BY ts", args).fetchall()


def save_forecast(hid: str, cycle_start, f: dict, d: dict) -> None:
    with connect() as c:
        c.execute("INSERT INTO forecasts (household_id, cycle_start, days_elapsed, units_so_far, p10, p50, p90, "
                  "p_cross, threshold, verdict, backend, quantiles) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (hid, cycle_start, d["days_elapsed"], d["units_so_far"], f["p10"], f["p50"], f["p90"],
                   f["p_cross"], f["threshold"], d["verdict"], f["backend"],
                   json.dumps({"levels": f["levels"], "units": f["units"]})))


def save_cycles_from_history(hid: str, history: list[dict]) -> int:
    with connect() as c:
        c.execute("INSERT INTO households (id) VALUES (%s) ON CONFLICT DO NOTHING", (hid,))
        for h in history:
            c.execute("INSERT INTO cycles (household_id, start_date, billed_units, bill_month) "
                      "VALUES (%s, %s::date, %s, %s) ON CONFLICT (household_id, start_date) "
                      "DO UPDATE SET billed_units=EXCLUDED.billed_units",
                      (hid, h["month"] + "-01", h["units"], h["month"]))
    return len(history)


def save_tariff_docs(docs: list[dict]) -> int:
    n = 0
    with connect() as c:
        emb_col = has_embedding_column(c)
        for d in docs:
            vec = embed(f"{d.get('title', '')}\n{d.get('snippet', '')}") if emb_col else None
            c.execute(
                "INSERT INTO tariff_docs (url, title, snippet, published, source, query"
                + (", embedding" if vec else "") + ") VALUES (%s,%s,%s,%s,%s,%s"
                + (", %s::vector" if vec else "") + ") ON CONFLICT (url) DO NOTHING",
                [d["url"], d.get("title"), d.get("snippet"), d.get("published"), d.get("source"), d.get("query"),
                 *([_vec(vec)] if vec else [])])
            n += 1
    return n


# ---------------------------------------------------------------- hybrid search
def rrf_fuse(ranked_lists: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = sum 1/(k + rank). Pure function (tested)."""
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, doc in enumerate(lst, 1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def search_tariff(query: str, top: int = 5) -> dict:
    with connect() as c:
        fts = [r[0] for r in c.execute(
            "SELECT id FROM tariff_docs, websearch_to_tsquery('english', %s) q WHERE tsv @@ q "
            "ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 50", (query,)).fetchall()]
        mode, lists = "fulltext", [fts]
        if has_embedding_column(c):
            v = embed(query)
            if v:
                vec = [r[0] for r in c.execute(
                    "SELECT id FROM tariff_docs WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT 50",
                    (_vec(v),)).fetchall()]
                lists.append(vec)
                mode = "hybrid_rrf"
        fused = rrf_fuse(lists)[:top]
        ids = [i for i, _ in fused]
        rows = {r[0]: r for r in c.execute(
            "SELECT id, title, url, published, snippet FROM tariff_docs WHERE id = ANY(%s)", (ids,)).fetchall()}
    return {"mode": mode, "results": [
        {"id": i, "score": round(sc, 5), "title": rows[i][1], "url": rows[i][2], "published": rows[i][3],
         "snippet": rows[i][4]} for i, sc in fused if i in rows]}
