from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from server.config import DB_PATH, ensure_data_dir
from server.search import semantic_rank


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL,
    created_at TEXT NOT NULL,
    audio BLOB,
    audio_type TEXT,
    duration_seconds REAL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    title,
    transcript,
    content='memories',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, title, transcript)
    VALUES (new.id, new.title, new.transcript);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, title, transcript)
    VALUES ('delete', old.id, old.title, old.transcript);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, title, transcript)
    VALUES ('delete', old.id, old.title, old.transcript);
    INSERT INTO memories_fts(rowid, title, transcript)
    VALUES (new.id, new.title, new.transcript);
END;
"""


def _connect() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
        for name, kind in [("audio", "BLOB"), ("audio_type", "TEXT"), ("duration_seconds", "REAL")]:
            if name not in columns:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {kind}")
        _backfill_fts(conn)


def _backfill_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")


def _parse_created(created_at: str) -> datetime:
    text = (created_at or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    created = _parse_created(row["created_at"])
    return {
        "id": row["id"],
        "title": row["title"],
        "transcript": row["transcript"],
        "created_at": row["created_at"],
        "has_audio": bool(row["audio_bytes"]),
        "audio_type": row["audio_type"],
        "duration_seconds": row["duration_seconds"],
        "year": created.year,
        "month": created.month,
        "day": created.day,
    }


def _matches_date(
    memory: dict[str, Any],
    year: int | None,
    month: int | None,
    day: int | None,
) -> bool:
    if year is not None and memory["year"] != year:
        return False
    if month is not None and memory["month"] != month:
        return False
    if day is not None and memory["day"] != day:
        return False
    return True


def list_memories(
    *,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, title, transcript, created_at, length(audio) AS audio_bytes, audio_type, duration_seconds FROM memories "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    memories = [_row_to_dict(r) for r in rows]
    if year is None and month is None and day is None:
        return memories
    return [m for m in memories if _matches_date(m, year, month, day)]


def get_memory(memory_id: int) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, title, transcript, created_at, length(audio) AS audio_bytes, audio_type, duration_seconds FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_memory(transcript: str, title: str = "", *, audio: bytes | None = None,
                  audio_type: str | None = None, duration_seconds: float | None = None) -> dict[str, Any]:
    text = (transcript or "").strip()
    if not text and not audio:
        raise ValueError("A transcript or recording is required")

    cleaned_title = (title or "").strip()
    if not cleaned_title:
        cleaned_title = _default_title(text) if text else "Recorded memory"

    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO memories (title, transcript, created_at, audio, audio_type, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (cleaned_title, text, now, audio, audio_type, duration_seconds),
        )
        memory_id = int(cur.lastrowid)

    memory = get_memory(memory_id)
    assert memory is not None
    return memory


def delete_memory(memory_id: int) -> bool:
    with connection() as conn:
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0


def timeline(
    *,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> list[dict[str, Any]]:
    """Nest memories under year → month → day."""
    memories = list_memories(year=year, month=month, day=day)
    years: dict[int, dict[str, Any]] = {}

    for memory in memories:
        y = memory["year"]
        m = memory["month"]
        d = memory["day"]
        year_node = years.setdefault(
            y,
            {"year": y, "months": {}},
        )
        month_node = year_node["months"].setdefault(
            m,
            {
                "month": m,
                "label": datetime(y, m, 1).strftime("%B %Y"),
                "days": {},
            },
        )
        day_node = month_node["days"].setdefault(
            d,
            {
                "day": d,
                "label": f"{datetime(y, m, d).strftime('%b')} {d}",
                "memories": [],
            },
        )
        day_node["memories"].append(memory)

    result: list[dict[str, Any]] = []
    for y in sorted(years.keys(), reverse=True):
        year_node = years[y]
        months_out = []
        for m in sorted(year_node["months"].keys(), reverse=True):
            month_node = year_node["months"][m]
            days_out = [
                month_node["days"][d]
                for d in sorted(month_node["days"].keys(), reverse=True)
            ]
            months_out.append(
                {
                    "month": m,
                    "label": month_node["label"],
                    "days": days_out,
                }
            )
        result.append({"year": y, "months": months_out})
    return result


def search_memories(
    query: str,
    *,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    pool = list_memories(year=year, month=month, day=day)
    if not pool:
        return []

    by_id = {m["id"]: m for m in pool}
    scores: dict[int, float] = {}

    fts_query = _fts_query(q)
    if fts_query:
        placeholders = ",".join("?" for _ in by_id) or "NULL"
        sql = (
            "SELECT rowid AS id, bm25(memories_fts) AS rank "
            "FROM memories_fts "
            f"WHERE memories_fts MATCH ? AND rowid IN ({placeholders}) "
            "ORDER BY rank LIMIT ?"
        )
        params: list[Any] = [fts_query, *by_id.keys(), limit]
        try:
            with connection() as conn:
                rows = conn.execute(sql, params).fetchall()
            for row in rows:
                # bm25: lower is better; flip into a positive score
                scores[int(row["id"])] = scores.get(int(row["id"]), 0.0) + (
                    1.0 / (1.0 + max(float(row["rank"]), 0.0))
                ) * 1.2
        except sqlite3.OperationalError:
            pass

    for memory, score in semantic_rank(q, pool, limit=limit):
        scores[memory["id"]] = scores.get(memory["id"], 0.0) + score

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    out: list[dict[str, Any]] = []
    for memory_id, score in ranked:
        item = dict(by_id[memory_id])
        item["score"] = round(score, 4)
        out.append(item)
    return out


def _fts_query(query: str) -> str:
    terms = re.findall(r"[a-z0-9áéíóúüñ]+", query.lower())
    terms = [t for t in terms if len(t) > 1]
    if not terms:
        return ""
    return " OR ".join(f'{term}*' for term in terms)


def _default_title(transcript: str) -> str:
    first = transcript.split(".")[0].strip()
    if len(first) > 48:
        return first[:45].rstrip() + "…"
    return first or "Memory"


def get_audio(memory_id: int) -> tuple[bytes, str] | None:
    with connection() as conn:
        row = conn.execute("SELECT audio, audio_type FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return (bytes(row["audio"]), row["audio_type"]) if row and row["audio"] else None
