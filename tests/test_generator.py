import json
import tempfile
from pathlib import Path
from core.models import Diagnosis
from report.generator import generate_report

DIAGNOSIS = Diagnosis(
    instance_id="django__django-1234",
    predicted_files=["django/db/models/query.py"],
    predicted_functions=["filter"],
    confidence=0.85,
    evidence_chain=["Found raise ValueError in filter method"],
    explanation="The filter method raises ValueError on invalid column names",
    rounds=1,
)


def test_generate_report_creates_json(tmp_path):
    json_p, md_p = generate_report(DIAGNOSIS, tmp_path)
    assert json_p.exists()
    data = json.loads(json_p.read_text())
    assert data["instance_id"] == "django__django-1234"
    assert data["predicted_files"] == ["django/db/models/query.py"]
    assert data["confidence"] == 0.85


def test_generate_report_creates_markdown(tmp_path):
    json_p, md_p = generate_report(DIAGNOSIS, tmp_path)
    assert md_p.exists()
    text = md_p.read_text()
    assert "django__django-1234" in text
    assert "django/db/models/query.py" in text
    assert "0.85" in text


def test_generate_report_filenames_use_instance_id(tmp_path):
    json_p, md_p = generate_report(DIAGNOSIS, tmp_path)
    assert json_p.name == "django__django-1234.json"
    assert md_p.name == "django__django-1234.md"


def test_generate_report_creates_output_dir():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "nested" / "reports"
        generate_report(DIAGNOSIS, out)
        assert out.exists()
