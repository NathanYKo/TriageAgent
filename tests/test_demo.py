from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from demo import main, run_dev_slice_cmd
from core.models import RunResult, Diagnosis

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


def test_main_single_instance():
    runner = CliRunner()
    with patch("demo.load_instances", return_value=[FAKE_INSTANCE]), \
         patch("demo.checkout_repo", return_value="/fake/repo"), \
         patch("demo.run_instance", return_value=FAKE_RESULT), \
         patch("demo.generate_report", return_value=("/fake/out.json", "/fake/out.md")):
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
         patch("demo.run_instance", return_value=error_result):
        result = runner.invoke(main, ["--instance", "django__django-1234"])
    assert "timed out" in result.output
