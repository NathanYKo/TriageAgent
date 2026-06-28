import time
from pathlib import Path
from core.models import Issue, RunResult, Diagnosis
from pipeline.retriever import retrieve
from agents.hypothesizer import hypothesize
from agents.verifier import verify


def run_instance(issue: Issue, repo_dir: Path) -> RunResult:
    start = time.monotonic()
    try:
        candidates = retrieve(issue.symptoms, repo_dir, top_n=10)
        hypotheses = hypothesize(issue.symptoms, candidates)
        if not hypotheses:
            raise ValueError(f"Hypothesizer returned no hypotheses for {issue.instance_id}")
        verdicts = [verify(h, repo_dir) for h in hypotheses]

        confirmed = [
            (h, v) for h, v in zip(hypotheses, verdicts)
            if v.status in ("CONFIRMED", "PARTIAL")
        ]
        best_h, best_v = confirmed[0] if confirmed else (hypotheses[0], verdicts[0])

        diagnosis = Diagnosis(
            instance_id=issue.instance_id,
            predicted_files=[h.location_file for h in hypotheses],
            predicted_functions=[h.location_function for h in hypotheses if h.location_function],
            confidence=best_h.confidence if confirmed else best_h.confidence * 0.5,
            evidence_chain=[best_v.reason],
            explanation=best_h.rationale,
            rounds=1,
        )
        return RunResult(
            instance_id=issue.instance_id,
            diagnosis=diagnosis,
            latency_s=time.monotonic() - start,
        )
    except Exception as e:
        return RunResult(
            instance_id=issue.instance_id,
            error=str(e),
            latency_s=time.monotonic() - start,
        )
