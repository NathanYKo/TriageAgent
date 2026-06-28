from unittest.mock import patch, MagicMock
from pathlib import Path
from pipeline.swebench_loader import load_instances, instance_to_issue, checkout_repo

FAKE_INSTANCE = {
    "instance_id": "django__django-1234",
    "repo": "django/django",
    "base_commit": "abc123def456",
    "problem_statement": "ValueError raised in queryset.filter\n\nTraceback:\n  File \"django/db/models/query.py\", line 10, in filter\n    raise ValueError(\"bad\")\nValueError: bad",
    "patch": "--- a/django/db/models/query.py\n+++ b/django/db/models/query.py\n@@ -1,3 +1,4 @@\n+fix",
    "hints_text": "",
}

def test_instance_to_issue_fields():
    issue = instance_to_issue(FAKE_INSTANCE)
    assert issue.instance_id == "django__django-1234"
    assert issue.repo == "django/django"
    assert issue.base_commit == "abc123def456"
    assert "ValueError" in issue.body

def test_instance_to_issue_parses_symptoms():
    issue = instance_to_issue(FAKE_INSTANCE)
    assert any("ValueError" in e for e in issue.symptoms.error_messages)
    assert any("query.py" in f.file for f in issue.symptoms.traceback_frames)

def test_load_instances_returns_list():
    fake_ds = [FAKE_INSTANCE] * 5
    with patch("pipeline.swebench_loader.load_dataset") as mock_load:
        mock_load.return_value = fake_ds
        result = load_instances(n=3)
    assert len(result) == 3

def test_checkout_repo_clones_if_missing(tmp_path):
    instance = dict(FAKE_INSTANCE)
    with patch("pipeline.swebench_loader.REPO_CACHE", tmp_path), \
         patch("pipeline.swebench_loader.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)
        repo_dir = checkout_repo(instance)
    assert mock_sub.run.called

def test_checkout_repo_skips_clone_if_present(tmp_path):
    instance = dict(FAKE_INSTANCE)
    existing = tmp_path / "django__django"
    existing.mkdir()
    with patch("pipeline.swebench_loader.REPO_CACHE", tmp_path), \
         patch("pipeline.swebench_loader.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0)
        checkout_repo(instance)
    calls = mock_sub.run.call_args_list
    assert not any("clone" in c.args[0] for c in calls)
