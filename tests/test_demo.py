import sqlite3 as _sqlite3
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from demo import main, run_dev_slice_cmd
from core.models import RunResult, Diagnosis
from core.db import init_db


FAKE_DIAGNOSIS = Diagnosis(
    instance_id="django__django-1234",
    predicted_files=["django/db/models/query.py"],
    predicted_functions=["filter"],
    confidence=0.85,
    evidence_chain=["Found ValueError"],
    explanation="filter raises ValueError",
    rounds=1,
)

FAKE_RESULT = RunResult(instance_id="django__django-1234", diagnosis=FAKE_DIAGNOSIS)
FAKE_INSTANCE = {
    "instance_id": "django__django-1234",
    "repo": "django/django",
    "base_commit": "abc123",
    "problem_statement": "ValueError in filter\nTraceback:\n  pass",
    "patch": "+++ b/django/db/models/query.py\n",
    "hints_text": "",
}


def _mem_conn():
    c = _sqlite3.connect(":memory:")
    init_db(c)
    return c


# ── existing tests (patched to avoid filesystem side-effects) ─────────────────

def test_main_single_instance():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=FAKE_RESULT), \
         patch("demo.generate_report", return_value=("/fake/out.json", "/fake/out.md")), \
         patch("demo.open_db", return_value=_mem_conn()), \
         patch("demo.save_run"):
        result = runner.invoke(main, ["--instance", "django__django-1234"])
    assert result.exit_code == 0
    assert "django__django-1234" in result.output


def test_main_instance_not_found():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]):
        result = runner.invoke(main, ["--instance", "nonexistent-id"])
    assert "not found" in result.output.lower()


def test_main_error_result():
    error_result = RunResult(instance_id="django__django-1234", error="timed out")
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=error_result), \
         patch("demo.open_db", return_value=_mem_conn()), \
         patch("demo.save_run"):
        result = runner.invoke(main, ["--instance", "django__django-1234"])
    assert "timed out" in result.output


# ── new DB-wiring tests ───────────────────────────────────────────────────────

def test_run_saves_result_to_db():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=FAKE_RESULT), \
         patch("demo.generate_report", return_value=("/o.json", "/o.md")), \
         patch("demo.open_db", return_value=_mem_conn()), \
         patch("demo.save_run") as mock_save:
        result = runner.invoke(main, ["--instance", "django__django-1234"])
    assert result.exit_code == 0
    mock_save.assert_called_once()
    assert mock_save.call_args[0][1].instance_id == "django__django-1234"


def test_run_db_default_path():
    from pathlib import Path
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=FAKE_RESULT), \
         patch("demo.generate_report", return_value=("/o.json", "/o.md")), \
         patch("demo.open_db") as mock_open, \
         patch("demo.save_run"):
        mock_open.return_value = _mem_conn()
        runner.invoke(main, ["--instance", "django__django-1234"])
    assert Path(mock_open.call_args[0][0]) == Path("output/triage.db")


def test_dev_slice_skips_completed_instances():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.open_db", return_value=_mem_conn()), \
         patch("demo.completed_ids", return_value={"django__django-1234"}), \
         patch("demo.run_instance") as mock_run:
        result = runner.invoke(run_dev_slice_cmd, ["--n", "1"])
    assert result.exit_code == 0
    mock_run.assert_not_called()
    assert "Skipping django__django-1234" in result.output


def test_dev_slice_saves_new_result_to_db():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=FAKE_RESULT), \
         patch("demo.generate_report", return_value=("/o.json", "/o.md")), \
         patch("demo.open_db", return_value=_mem_conn()), \
         patch("demo.completed_ids", return_value=set()), \
         patch("demo.save_run") as mock_save:
        result = runner.invoke(run_dev_slice_cmd, ["--n", "1"])
    assert result.exit_code == 0
    mock_save.assert_called_once()
