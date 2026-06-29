import click
from pathlib import Path
from pipeline.swebench_loader import load_instances, checkout_repo, instance_to_issue
from core.loop import run_instance
from core.db import open_db, save_run, completed_ids
from report.generator import generate_report
from eval.metrics import compute_metrics, parse_gold_files


@click.group()
def cli():
    pass


@cli.command("run")
@click.option("--instance", "instance_id", required=True, help="SWE-bench instance ID")
@click.option("--output", default="output/reports", help="Report output directory")
@click.option("--n-load", default=300, help="Number of instances to load for lookup")
@click.option("--db", "db_path", default="output/triage.db", show_default=True,
              help="Path to SQLite results DB")
def main(instance_id: str, output: str, n_load: int, db_path: str):
    instances = load_instances(n=n_load)
    id_map = {inst["instance_id"]: inst for inst in instances}

    if instance_id not in id_map:
        click.echo(f"Instance {instance_id} not found in first {n_load} instances.")
        return

    inst = id_map[instance_id]
    click.echo(f"Processing {instance_id} ({inst['repo']})...")

    issue = instance_to_issue(inst)
    repo_dir = checkout_repo(inst)
    result = run_instance(issue, Path(str(repo_dir)))

    conn = open_db(Path(db_path))
    try:
        save_run(conn, result)
    finally:
        conn.close()

    if result.diagnosis:
        json_p, md_p = generate_report(result.diagnosis, Path(output))
        click.echo(f"Predicted files: {result.diagnosis.predicted_files}")
        click.echo(f"Confidence: {result.diagnosis.confidence:.2f}")
        click.echo(f"Report written: {md_p}")
    else:
        click.echo(f"Error: {result.error}")


@cli.command("dev-slice")
@click.option("--n", default=5, help="Number of instances to evaluate")
@click.option("--output", default="output/reports", help="Report output directory")
@click.option("--db", "db_path", default="output/triage.db", show_default=True,
              help="Path to SQLite results DB")
def run_dev_slice_cmd(n: int, output: str, db_path: str):
    instances = load_instances(n=n)
    results = []

    conn = open_db(Path(db_path))
    try:
        done = completed_ids(conn)
        if done:
            click.echo(f"Resuming: {len(done)} already completed, skipping.")

        for inst in instances:
            iid = inst["instance_id"]
            if iid in done:
                click.echo(f"Skipping {iid} (already in DB).")
                continue

            click.echo(f"Running {iid}...")
            try:
                issue = instance_to_issue(inst)
                repo_dir = checkout_repo(inst)
                result = run_instance(issue, Path(str(repo_dir)))
                results.append(result)
                save_run(conn, result)
                generate_report(result.diagnosis or _empty_diagnosis(iid), Path(output))
            except Exception as e:
                click.echo(f"  ERROR: {e}")
    finally:
        conn.close()

    metrics = compute_metrics(results, instances)
    click.echo(f"\n=== Dev Slice Results (n={n}) ===")
    click.echo(f"Acc@1: {metrics['acc@1']:.3f}")
    click.echo(f"Acc@5: {metrics['acc@5']:.3f}")
    click.echo(f"Total scored: {metrics['total']}")


def _empty_diagnosis(instance_id: str):
    from core.models import Diagnosis
    return Diagnosis(
        instance_id=instance_id,
        predicted_files=[],
        predicted_functions=[],
        confidence=0.0,
        evidence_chain=["error — no diagnosis produced"],
        explanation="Pipeline error",
        rounds=0,
    )


if __name__ == "__main__":
    cli()
