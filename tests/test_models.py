from core.models import (
    TracebackFrame, Symptoms, Issue, Candidate,
    Hypothesis, Verdict, Diagnosis, RunResult,
)

def test_traceback_frame():
    f = TracebackFrame(file="foo/bar.py", function="baz", line=42)
    assert f.file == "foo/bar.py"
    assert f.function == "baz"
    assert f.line == 42

def test_symptoms_defaults():
    s = Symptoms()
    assert s.error_messages == []
    assert s.traceback_frames == []
    assert s.mentioned_identifiers == []
    assert s.repro_steps == []

def test_issue_round_trip():
    s = Symptoms(error_messages=["ValueError: bad input"])
    issue = Issue(
        instance_id="django__django-1234",
        repo="django/django",
        base_commit="abc123",
        title="Bug in queryset",
        body="Full issue body",
        symptoms=s,
    )
    assert issue.instance_id == "django__django-1234"
    assert issue.symptoms.error_messages == ["ValueError: bad input"]

def test_candidate():
    c = Candidate(file="django/db/models.py", score=3.7, snippet="class Model:")
    assert c.file == "django/db/models.py"

def test_hypothesis_defaults():
    h = Hypothesis(
        location_file="src/foo.py",
        rationale="Suspect null check",
        predicted_evidence="returns None when empty",
        confidence=0.8,
        rank=1,
    )
    assert h.location_function is None
    assert h.confidence == 0.8

def test_verdict_statuses():
    h = Hypothesis(
        location_file="src/foo.py",
        rationale="r",
        predicted_evidence="e",
        confidence=0.5,
        rank=1,
    )
    for status in ("CONFIRMED", "PARTIAL", "REJECTED"):
        v = Verdict(hypothesis=h, status=status, reason="because")
        assert v.status == status

def test_diagnosis():
    d = Diagnosis(
        instance_id="abc",
        predicted_files=["a.py", "b.py"],
        predicted_functions=["foo"],
        confidence=0.7,
        evidence_chain=["found null check"],
        explanation="Root cause is in a.py",
        rounds=1,
    )
    assert d.predicted_files[0] == "a.py"

def test_run_result_defaults():
    r = RunResult(instance_id="abc")
    assert r.diagnosis is None
    assert r.error is None
    assert r.cost_usd == 0.0
    assert r.latency_s == 0.0
