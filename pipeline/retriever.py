import heapq
import re
from pathlib import Path
from rank_bm25 import BM25Plus
from core.models import Candidate, Symptoms

_WORD_RE = re.compile(r'\w+')
SNIPPET_CHARS = 500


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _safe_read(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:limit] if limit is not None else text
    except OSError:
        return ""


def build_index(repo_dir: Path) -> tuple[list[Path], BM25Plus, list[str]]:
    files = [f for f in repo_dir.rglob("*.py") if ".git" not in f.parts]
    texts = [_safe_read(f) for f in files]
    corpus = [_tokenize(t) for t in texts]
    bm25 = BM25Plus(corpus if corpus else [[""]])
    return files, bm25, texts


def retrieve(symptoms: Symptoms, repo_dir: Path, top_n: int = 10) -> list[Candidate]:
    files, bm25, texts = build_index(repo_dir)
    if not files:
        return []

    query_text = " ".join([
        *symptoms.error_messages,
        *symptoms.mentioned_identifiers,
        *(f.function for f in symptoms.traceback_frames),
    ])
    tokens = _tokenize(query_text) or ["error"]
    scores = bm25.get_scores(tokens)

    return [
        Candidate(
            file=files[idx].relative_to(repo_dir).as_posix(),
            score=float(score),
            snippet=texts[idx][:SNIPPET_CHARS],
        )
        for idx, score in heapq.nlargest(top_n, enumerate(scores), key=lambda x: x[1])
    ]
