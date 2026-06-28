import tempfile
from pathlib import Path
from core.models import Symptoms, TracebackFrame
from pipeline.retriever import retrieve, build_index


def make_temp_repo(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return d


def test_build_index_finds_py_files():
    repo = make_temp_repo({
        "foo/bar.py": "def bar(): pass",
        "foo/baz.py": "def baz(): raise ValueError('oops')",
        "README.md": "not python",
    })
    files, bm25 = build_index(repo)
    assert len(files) == 2
    assert all(f.suffix == ".py" for f in files)


def test_retrieve_ranks_matching_file_higher():
    repo = make_temp_repo({
        "core/queryset.py": "def filter(): raise ValueError('Invalid column')",
        "core/admin.py": "def register(): pass",
    })
    symptoms = Symptoms(
        error_messages=["ValueError: Invalid column"],
        mentioned_identifiers=["core.queryset"],
    )
    candidates = retrieve(symptoms, repo, top_n=5)
    assert len(candidates) >= 1
    assert candidates[0].file == "core/queryset.py"


def test_retrieve_returns_candidate_with_snippet():
    repo = make_temp_repo({"app/views.py": "def index(): return 200"})
    symptoms = Symptoms(error_messages=["error"])
    candidates = retrieve(symptoms, repo, top_n=3)
    assert len(candidates) >= 1
    assert candidates[0].snippet != ""
    assert candidates[0].score >= 0


def test_retrieve_empty_symptoms_still_returns():
    repo = make_temp_repo({"x.py": "pass", "y.py": "pass"})
    symptoms = Symptoms()
    candidates = retrieve(symptoms, repo, top_n=2)
    assert len(candidates) == 2


def test_retrieve_respects_top_n():
    files = {f"mod{i}.py": f"def f{i}(): pass" for i in range(20)}
    repo = make_temp_repo(files)
    symptoms = Symptoms(error_messages=["error"])
    candidates = retrieve(symptoms, repo, top_n=5)
    assert len(candidates) == 5
