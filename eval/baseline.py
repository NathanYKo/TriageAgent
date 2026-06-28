import time
from pathlib import Path
from core.models import RunResult, Diagnosis, Symptoms
from pipeline.retriever import retrieve


def run_baseline(instance_id: str, symptoms: Symptoms, repo_dir: Path) -> RunResult:
    start = time.monotonic()
    try:
        candidates = retrieve(symptoms, repo_dir, top_n=5)
        diagnosis = Diagnosis(
            instance_id=instance_id,
            predicted_files=[c.file for c in candidates],
            predicted_functions=[],
            confidence=candidates[0].score if candidates else 0.0,
            evidence_chain=["BM25 retrieval only — no LLM"],
            explanation="BM25 baseline: top-ranked file by lexical similarity",
            rounds=0,
        )
        return RunResult(
            instance_id=instance_id,
            diagnosis=diagnosis,
            latency_s=time.monotonic() - start,
        )
    except Exception as e:
        return RunResult(
            instance_id=instance_id,
            error=str(e),
            latency_s=time.monotonic() - start,
        )
