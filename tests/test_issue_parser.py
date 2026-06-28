from pipeline.issue_parser import parse_issue

FIXTURE_BODY = """
When calling `queryset.filter()`, a ValueError is raised.

Traceback (most recent call last):
  File "django/db/models/query.py", line 920, in filter
    return self._filter_or_exclude(False, args, kwargs)
  File "django/db/models/sql/compiler.py", line 55, in get_columns
    raise ValueError("Invalid column")
ValueError: Invalid column

Reproduction:
```python
qs = MyModel.objects.filter(name="test")
```

The issue is in django.db.models.query.QuerySet.filter.
"""

def test_extracts_error_messages():
    s = parse_issue("ValueError in queryset.filter", FIXTURE_BODY)
    assert any("ValueError" in e for e in s.error_messages)

def test_extracts_traceback_frames():
    s = parse_issue("ValueError in queryset.filter", FIXTURE_BODY)
    files = [f.file for f in s.traceback_frames]
    assert any("query.py" in f for f in files)

def test_extracts_identifiers():
    s = parse_issue("ValueError in queryset.filter", FIXTURE_BODY)
    assert any("django.db.models" in i for i in s.mentioned_identifiers)

def test_empty_body():
    s = parse_issue("", "")
    assert s.error_messages == []
    assert s.traceback_frames == []

def test_no_duplicate_identifiers():
    body = "django.db.models.query django.db.models.query django.db.models.query"
    s = parse_issue("", body)
    count = sum(1 for i in s.mentioned_identifiers if i == "django.db.models.query")
    assert count == 1

def test_repro_steps_extracted():
    s = parse_issue("test", FIXTURE_BODY)
    assert len(s.repro_steps) >= 1
