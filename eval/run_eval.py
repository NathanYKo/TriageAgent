"""
eval/run_eval.py — Compare HVR agent vs BM25 baseline on the dev slice.

Usage:
    python eval/run_eval.py [--n 20] [--output output/eval] [--db output/triage.db]
"""
import json
import click
from pathlib import Path
from pipeline.swebench_loader import load_instances, checkout_repo, instance_to_issue
from pipeline.retriever import retrieve
from core.loop import run_instance
from core.db import open_db, save_run, completed_ids
from eval.baseline import run_baseline
from eval.metrics import compute_metrics, parse_gold_files


def _print_hits(label, diagnosis, gold, latency, conf=None):
    hit1 = any(g in diagnosis.predicted_files[:1] for g in gold)
    hit5 = any(g in diagnosis.predicted_files[:5] for g in gold)
    conf_str = f"  conf={conf:.2f}" if conf is not None else ""
    print(
        f"  {label} @1={'Y' if hit1 else 'N'} @5={'Y' if hit5 else 'N'}"
        f"{conf_str}  {latency:.1f}s  pred={diagnosis.predicted_files[:3]}"
    )


def _gold_rank_in_bm25(gold: list[str], symptoms, repo_dir: Path, top_n: int = 20) -> int | None:
    """Return rank (1-indexed) of first gold file in BM25 top_n, or None if absent."""
    candidates = retrieve(symptoms, repo_dir, top_n=top_n)
    files = [c.file for c in candidates]
    for g in gold:
        if g in files:
            return files.index(g) + 1
    return None


@click.command()
@click.option("--n", default=20, help="Number of instances to evaluate")
@click.option("--output", default="output/eval", help="Directory for results JSON")
@click.option("--db", "db_path", default=None,
              help="Optional path to SQLite results DB for resumable runs")
def main(n: int, output: str, db_path: str | None):
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = open_db(Path(db_path)) if db_path else None
    done = completed_ids(conn) if conn else set()
    if done:
        print(f"Resuming: {len(done)} instances already completed, skipping.")

    instances = load_instances(n=n)
    agent_results, baseline_results, gold_ranks, golds = [], [], [], []

    try:
        for i, inst in enumerate(instances, 1):
            iid = inst["instance_id"]
            gold = parse_gold_files(inst.get("patch", ""))
            print(f"\n[{i}/{n}] {iid}  gold={gold}")

            if iid in done:
                print(f"  Skipped (already in DB).")
                continue

            issue = instance_to_issue(inst)
            repo_dir = Path(str(checkout_repo(inst)))

            agent_r = run_instance(issue, repo_dir)
            agent_results.append(agent_r)

            if conn is not None:
                save_run(conn, agent_r)

            base_r = run_baseline(iid, issue.symptoms, repo_dir)
            baseline_results.append(base_r)

            gold_rank = _gold_rank_in_bm25(gold, issue.symptoms, repo_dir, top_n=20)

            if agent_r.diagnosis:
                _print_hits("Agent ", agent_r.diagnosis, gold, agent_r.latency_s,
                            conf=agent_r.diagnosis.confidence)
            else:
                print(f"  Agent  ERROR: {agent_r.error}")

            if base_r.diagnosis:
                _print_hits("BM25  ", base_r.diagnosis, gold, base_r.latency_s)

            golds.append(gold)
            gold_ranks.append(gold_rank)
            rank_str = f"rank={gold_rank}" if gold_rank else "NOT in BM25 top-20"
            print(f"  Retrieval diagnostic: gold {rank_str}")

    finally:
        if conn is not None:
            conn.close()

    agent_m = compute_metrics(agent_results, instances)
    base_m = compute_metrics(baseline_results, instances)

    avg_agent_lat = sum(r.latency_s for r in agent_results) / max(len(agent_results), 1)
    avg_base_lat = sum(r.latency_s for r in baseline_results) / max(len(baseline_results), 1)
    mean_rounds = (
        sum(r.diagnosis.rounds for r in agent_results if r.diagnosis)
        / max(agent_m["total"], 1)
    )

    print(f"\n{'='*52}")
    print(f"{'Metric':<22} {'HVR Agent':>12} {'BM25':>12}")
    print(f"{'-'*52}")
    print(f"{'Acc@1':<22} {agent_m['acc@1']:>12.3f} {base_m['acc@1']:>12.3f}")
    print(f"{'Acc@5':<22} {agent_m['acc@5']:>12.3f} {base_m['acc@5']:>12.3f}")
    print(f"{'Mean rounds':<22} {mean_rounds:>12.2f} {'—':>12}")
    print(f"{'Avg latency (s)':<22} {avg_agent_lat:>12.1f} {avg_base_lat:>12.1f}")
    print(f"{'Scored':<22} {agent_m['total']:>12} {base_m['total']:>12}")
    print(f"{'='*52}")

    out = {
        "n": n,
        "agent": {**agent_m, "avg_latency_s": round(avg_agent_lat, 2),
                  "mean_rounds": round(mean_rounds, 2)},
        "baseline": {**base_m, "avg_latency_s": round(avg_base_lat, 3)},
        "per_instance": [
            {
                "instance_id": inst["instance_id"],
                "gold": gold,
                "agent_pred": r.diagnosis.predicted_files if r.diagnosis else [],
                "agent_conf": r.diagnosis.confidence if r.diagnosis else None,
                "agent_rounds": r.diagnosis.rounds if r.diagnosis else None,
                "agent_latency_s": round(r.latency_s, 2),
                "agent_error": r.error,
                "baseline_pred": br.diagnosis.predicted_files if br.diagnosis else [],
                "baseline_latency_s": round(br.latency_s, 3),
                "gold_bm25_rank": rank,
            }
            for inst, r, br, rank, gold in zip(
                instances, agent_results, baseline_results, gold_ranks, golds
            )
        ],
    }
    out_path = out_dir / f"eval_n{n}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nResults saved → {out_path}")


if __name__ == "__main__":
    main()
