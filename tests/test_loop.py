import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.models import Issue, Symptoms, Candidate, Hypothesis, Verdict, Diagnosis
from core.loop import run_instance

BASE_ISSUE = Issue(
    instance_id="test__repo-99",
    repo="test/repo",
    base_commit="abc",
    title="Bug",
    body="Something broke",
    symptoms=Symptoms(error_messages=["ValueError"]),
)

CANDIDATES = [Candidate(file="src/foo.py", score=3.0, snippet="def foo(): raise ValueError()")]

HYPOTHESIS = Hypothesis(
    location_file="src/foo.py",
    location_function="foo",
    rationale="ValueError raised here",
    predicted_evidence="raise ValueError in foo",
    confidence=0.9,
    rank=1,
)

CONFIRMED_VERDICT = Verdict(hypothesis=HYPOTHESIS, status="CONFIRMED", reason="Found raise ValueError")
REJECTED_VERDICT = Verdict(hypothesis=HYPOTHESIS, status="REJECTED", reason="No match")


def test_run_instance_confirmed():
    with patch("core.loop.retrieve", return_value=CANDIDATES), \
         patch("core.loop.hypothesize", return_value=[HYPOTHESIS]), \
         patch("core.loop.verify", return_value=CONFIRMED_VERDICT):
        result = run_instance(BASE_ISSUE, Path("/fake/repo"))

    assert result.instance_id == "test__repo-99"
    assert result.error is None
    assert result.diagnosis is not None
    assert "src/foo.py" in result.diagnosis.predicted_files


def test_run_instance_all_rejected_returns_best_guess():
    with patch("core.loop.retrieve", return_value=CANDIDATES), \
         patch("core.loop.hypothesize", return_value=[HYPOTHESIS]), \
         patch("core.loop.verify", return_value=REJECTED_VERDICT):
        result = run_instance(BASE_ISSUE, Path("/fake/repo"))

    assert result.diagnosis is not None
    assert len(result.diagnosis.predicted_files) >= 1


def test_run_instance_exception_returns_error():
    with patch("core.loop.retrieve", side_effect=RuntimeError("index failed")):
        result = run_instance(BASE_ISSUE, Path("/fake/repo"))

    assert result.error == "index failed"
    assert result.diagnosis is None


def test_run_instance_records_latency():
    with patch("core.loop.retrieve", return_value=CANDIDATES), \
         patch("core.loop.hypothesize", return_value=[HYPOTHESIS]), \
         patch("core.loop.verify", return_value=CONFIRMED_VERDICT):
        result = run_instance(BASE_ISSUE, Path("/fake/repo"))

    assert result.latency_s >= 0.0


def test_run_instance_diagnosis_rounds_is_1():
    with patch("core.loop.retrieve", return_value=CANDIDATES), \
         patch("core.loop.hypothesize", return_value=[HYPOTHESIS]), \
         patch("core.loop.verify", return_value=CONFIRMED_VERDICT):
        result = run_instance(BASE_ISSUE, Path("/fake/repo"))

    assert result.diagnosis.rounds == 1
