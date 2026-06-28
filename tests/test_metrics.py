from pathlib import Path
from core.models import Diagnosis, RunResult, Symptoms
from eval.metrics import parse_gold_files, acc_at_k, compute_metrics

PATCH = """diff --git a/django/db/models/query.py b/django/db/models/query.py
index abc..def 100644
--- a/django/db/models/query.py
+++ b/django/db/models/query.py
@@ -1 +1 @@
-old
+new
diff --git a/django/db/models/sql/compiler.py b/django/db/models/sql/compiler.py
index abc..def 100644
--- a/django/db/models/sql/compiler.py
+++ b/django/db/models/sql/compiler.py
@@ -1 +1 @@
-old
+new
"""


def test_parse_gold_files():
    files = parse_gold_files(PATCH)
    assert "django/db/models/query.py" in files
    assert "django/db/models/sql/compiler.py" in files
    assert len(files) == 2


def test_parse_gold_files_no_duplicates():
    double_patch = PATCH + PATCH
    files = parse_gold_files(double_patch)
    assert len(files) == len(set(files))


def test_acc_at_1_hit():
    assert acc_at_k(["a.py", "b.py"], ["a.py"], k=1) is True


def test_acc_at_1_miss():
    assert acc_at_k(["b.py", "c.py"], ["a.py"], k=1) is False


def test_acc_at_5_hit():
    predicted = ["x.py", "y.py", "z.py", "w.py", "a.py"]
    assert acc_at_k(predicted, ["a.py"], k=5) is True


def test_compute_metrics():
    diagnosis = Diagnosis(
        instance_id="test__repo-1",
        predicted_files=["django/db/models/query.py", "other.py"],
        predicted_functions=[],
        confidence=0.8,
        evidence_chain=["found it"],
        explanation="here",
        rounds=1,
    )
    results = [RunResult(instance_id="test__repo-1", diagnosis=diagnosis)]
    instances = [{"instance_id": "test__repo-1", "patch": PATCH}]
    metrics = compute_metrics(results, instances)

    assert metrics["total"] == 1
    assert metrics["acc@1"] == 1.0
    assert metrics["acc@5"] == 1.0


def test_compute_metrics_miss():
    diagnosis = Diagnosis(
        instance_id="test__repo-1",
        predicted_files=["wrong.py"],
        predicted_functions=[],
        confidence=0.5,
        evidence_chain=["nope"],
        explanation="wrong",
        rounds=1,
    )
    results = [RunResult(instance_id="test__repo-1", diagnosis=diagnosis)]
    instances = [{"instance_id": "test__repo-1", "patch": PATCH}]
    metrics = compute_metrics(results, instances)
    assert metrics["acc@1"] == 0.0


def test_compute_metrics_skips_error_results():
    results = [RunResult(instance_id="test__repo-1", error="timeout")]
    instances = [{"instance_id": "test__repo-1", "patch": PATCH}]
    metrics = compute_metrics(results, instances)
    assert metrics["total"] == 0


from unittest.mock import patch
from eval.baseline import run_baseline


def test_baseline_returns_run_result(tmp_path):
    (tmp_path / "core.py").write_text("def filter(): raise ValueError('oops')")
    symptoms = Symptoms(error_messages=["ValueError"])
    result = run_baseline("test__repo-1", symptoms, tmp_path)
    assert result.instance_id == "test__repo-1"
    assert result.diagnosis is not None
    assert result.diagnosis.rounds == 0


def test_baseline_error_on_exception():
    with patch("eval.baseline.retrieve", side_effect=RuntimeError("boom")):
        result = run_baseline("test__repo-1", Symptoms(), Path("/nonexistent"))
    assert result.error is not None
    assert result.diagnosis is None
