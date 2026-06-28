"""
Integration test: runs the full pipeline on 5 SWE-bench Lite instances.
Requires ANTHROPIC_API_KEY and internet access.
Skip with: pytest tests/test_integration.py --ignore-glob="*integration*"
Or run explicitly: pytest tests/test_integration.py -v -s
"""
import os
import pytest
from pathlib import Path
from pipeline.swebench_loader import load_instances, checkout_repo, instance_to_issue
from core.loop import run_instance
from report.generator import generate_report
from eval.metrics import compute_metrics

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration test",
)

N_INSTANCES = 5
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "integration"


def test_pipeline_on_dev_slice():
    instances = load_instances(n=N_INSTANCES)
    results = []

    for inst in instances:
        iid = inst["instance_id"]
        print(f"\nRunning {iid}...")
        issue = instance_to_issue(inst)
        repo_dir = checkout_repo(inst)
        result = run_instance(issue, Path(str(repo_dir)))

        if result.diagnosis:
            generate_report(result.diagnosis, OUTPUT_DIR)
            print(f"  Predicted: {result.diagnosis.predicted_files[:3]}")
            print(f"  Confidence: {result.diagnosis.confidence:.2f}")
            print(f"  Latency: {result.latency_s:.1f}s")
        else:
            print(f"  ERROR: {result.error}")

        results.append(result)

    metrics = compute_metrics(results, instances)
    print(f"\n=== Integration Results (n={N_INSTANCES}) ===")
    print(f"Acc@1: {metrics['acc@1']:.3f}")
    print(f"Acc@5: {metrics['acc@5']:.3f}")
    print(f"Scored: {metrics['total']}/{N_INSTANCES}")

    assert metrics["total"] >= 1, "At least 1 instance should produce a diagnosis"
