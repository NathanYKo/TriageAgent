import subprocess
from pathlib import Path
from datasets import load_dataset
from core.models import Issue
from pipeline.issue_parser import parse_issue

REPO_CACHE = Path("data/swebench/repos")


def _repo_cache_dir(repo: str) -> Path:
    return REPO_CACHE / repo.replace("/", "__")


def load_instances(n: int = 20) -> list[dict]:
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    return list(ds)[:n]


def checkout_repo(instance: dict) -> Path:
    repo = instance["repo"]
    base_commit = instance["base_commit"]
    repo_dir = _repo_cache_dir(repo)

    if not repo_dir.exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", repo_dir],
            check=True,
            capture_output=True,
        )

    subprocess.run(
        ["git", "checkout", base_commit],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    return repo_dir


def instance_to_issue(instance: dict) -> Issue:
    body = instance.get("problem_statement", "")
    title = body.split("\n")[0][:200]
    symptoms = parse_issue(title, body)
    return Issue(
        instance_id=instance["instance_id"],
        repo=instance["repo"],
        base_commit=instance["base_commit"],
        title=title,
        body=body,
        symptoms=symptoms,
    )
