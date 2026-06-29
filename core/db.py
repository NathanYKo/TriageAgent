"""core/db.py — SQLite persistence for TriageAgent run results."""
import sqlite3
from pathlib import Path

from core.models import Diagnosis, RunResult

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    instance_id    TEXT PRIMARY KEY,
    diagnosis_json TEXT,
    error          TEXT,
    cost_usd       REAL NOT NULL DEFAULT 0.0,
    latency_s      REAL NOT NULL DEFAULT 0.0,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) a SQLite DB at *path*, initialise schema, return connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the ``runs`` table if it does not exist. Idempotent."""
    conn.execute(_DDL)
    conn.commit()


def save_run(conn: sqlite3.Connection, result: RunResult) -> None:
    """Upsert *result* into the ``runs`` table."""
    diag_json: str | None = (
        result.diagnosis.model_dump_json() if result.diagnosis is not None else None
    )
    conn.execute(
        "INSERT OR REPLACE INTO runs "
        "(instance_id, diagnosis_json, error, cost_usd, latency_s) "
        "VALUES (?, ?, ?, ?, ?)",
        (result.instance_id, diag_json, result.error, result.cost_usd, result.latency_s),
    )
    conn.commit()


def load_run(conn: sqlite3.Connection, instance_id: str) -> RunResult | None:
    """Return the stored ``RunResult`` for *instance_id*, or ``None`` if absent."""
    row = conn.execute(
        "SELECT instance_id, diagnosis_json, error, cost_usd, latency_s "
        "FROM runs WHERE instance_id = ?",
        (instance_id,),
    ).fetchone()
    if row is None:
        return None
    iid, diag_json, error, cost_usd, latency_s = row
    diagnosis = Diagnosis.model_validate_json(diag_json) if diag_json is not None else None
    return RunResult(
        instance_id=iid,
        diagnosis=diagnosis,
        error=error,
        cost_usd=cost_usd,
        latency_s=latency_s,
    )


def completed_ids(conn: sqlite3.Connection) -> set[str]:
    """Return instance_ids with a successful diagnosis (error IS NULL AND diagnosis_json IS NOT NULL).

    Error runs and bare runs (neither diagnosis nor error) are excluded so they can be retried.
    """
    rows = conn.execute(
        "SELECT instance_id FROM runs WHERE error IS NULL AND diagnosis_json IS NOT NULL"
    ).fetchall()
    return {row[0] for row in rows}
