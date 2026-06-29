"""tests/test_db.py — unit tests for core/db.py SQLite persistence layer."""
import sqlite3
import pytest
from pathlib import Path
from core.db import init_db, open_db, save_run, load_run, completed_ids
from core.models import RunResult, Diagnosis


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def sample_diagnosis():
    return Diagnosis(
        instance_id="django__django-1234",
        predicted_files=["django/db/models/query.py", "django/db/models/sql/compiler.py"],
        predicted_functions=["filter", "_execute_sql"],
        confidence=0.87,
        evidence_chain=["ValueError raised in filter()", "call stack confirms query.py"],
        explanation="filter() fails to guard against None queryset",
        rounds=2,
    )


@pytest.fixture
def result_success(sample_diagnosis):
    return RunResult(
        instance_id="django__django-1234",
        diagnosis=sample_diagnosis,
        cost_usd=0.012,
        latency_s=4.73,
    )


@pytest.fixture
def result_error():
    return RunResult(
        instance_id="astropy__astropy-9999",
        error="index failed: no .py files found",
        latency_s=0.21,
    )


# ── init_db ───────────────────────────────────────────────────────────────────

def test_init_db_creates_runs_table(tmp_path):
    db_path = tmp_path / "triage.db"
    c = sqlite3.connect(str(db_path))
    init_db(c)
    tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "runs" in tables
    c.close()


def test_init_db_is_idempotent(conn):
    init_db(conn)  # second call — must not raise


def test_init_db_creates_expected_columns(conn):
    info = conn.execute("PRAGMA table_info(runs)").fetchall()
    col_names = {row[1] for row in info}
    assert col_names == {"instance_id", "diagnosis_json", "error", "cost_usd", "latency_s", "created_at"}


# ── open_db ───────────────────────────────────────────────────────────────────

def test_open_db_creates_file_and_schema(tmp_path):
    db_path = tmp_path / "sub" / "triage.db"
    c = open_db(db_path)
    assert db_path.exists()
    tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "runs" in tables
    c.close()


# ── save_run / load_run round-trips ───────────────────────────────────────────

def test_save_and_load_successful_run(conn, result_success):
    save_run(conn, result_success)
    loaded = load_run(conn, "django__django-1234")
    assert loaded is not None
    assert loaded.instance_id == result_success.instance_id
    assert loaded.error is None
    assert loaded.diagnosis is not None
    assert loaded.diagnosis.predicted_files == result_success.diagnosis.predicted_files
    assert loaded.diagnosis.predicted_functions == result_success.diagnosis.predicted_functions
    assert loaded.diagnosis.confidence == pytest.approx(result_success.diagnosis.confidence)
    assert loaded.diagnosis.rounds == result_success.diagnosis.rounds
    assert loaded.cost_usd == pytest.approx(result_success.cost_usd)
    assert loaded.latency_s == pytest.approx(result_success.latency_s)


def test_save_and_load_error_run(conn, result_error):
    save_run(conn, result_error)
    loaded = load_run(conn, "astropy__astropy-9999")
    assert loaded is not None
    assert loaded.diagnosis is None
    assert loaded.error == result_error.error
    assert loaded.latency_s == pytest.approx(result_error.latency_s)


def test_load_run_returns_none_for_missing(conn):
    assert load_run(conn, "nonexistent__id-0") is None


def test_save_run_upserts_on_duplicate(conn, result_success):
    save_run(conn, result_success)
    updated = RunResult(
        instance_id="django__django-1234",
        error="second attempt failed",
        latency_s=9.9,
    )
    save_run(conn, updated)
    loaded = load_run(conn, "django__django-1234")
    assert loaded.error == "second attempt failed"
    assert loaded.diagnosis is None
    count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 1


def test_save_run_multiple_instances(conn, result_success, result_error):
    save_run(conn, result_success)
    save_run(conn, result_error)
    count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 2


# ── completed_ids ─────────────────────────────────────────────────────────────

def test_completed_ids_empty_db(conn):
    assert completed_ids(conn) == set()


def test_completed_ids_only_successful_runs(conn, result_success, result_error):
    save_run(conn, result_success)
    save_run(conn, result_error)
    ids = completed_ids(conn)
    assert "django__django-1234" in ids
    assert "astropy__astropy-9999" not in ids


def test_completed_ids_returns_set(conn, result_success):
    save_run(conn, result_success)
    assert isinstance(completed_ids(conn), set)


def test_completed_ids_multiple_successes(conn, sample_diagnosis):
    for iid in ("a__b-1", "a__b-2", "a__b-3"):
        diag = sample_diagnosis.model_copy(update={"instance_id": iid})
        save_run(conn, RunResult(instance_id=iid, diagnosis=diag))
    assert completed_ids(conn) == {"a__b-1", "a__b-2", "a__b-3"}
