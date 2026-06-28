import re
from pathlib import Path
from rank_bm25 import BM25Plus
from core.models import Candidate, Symptoms

_WORD_RE = re.compile(r'\w+')


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def build_index(repo_dir: Path) -> tuple[list[Path], BM25Plus]:
    files = [f for f in repo_dir.rglob("*.py") if ".git" not in f.parts]
    corpus = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        corpus.append(_tokenize(text))
    bm25 = BM25Plus(corpus if corpus else [[""]])
    return files, bm25


def retrieve(symptoms: Symptoms, repo_dir: Path, top_n: int = 10) -> list[Candidate]:
    files, bm25 = build_index(repo_dir)
    if not files:
        return []

    query_text = (
        " ".join(symptoms.error_messages)
        + " " + " ".join(symptoms.mentioned_identifiers)
        + " " + " ".join(f.function for f in symptoms.traceback_frames)
    )
    tokens = _tokenize(query_text) or ["error"]
    scores = bm25.get_scores(tokens)

    result = []
    for idx, score in sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]:
        f = files[idx]
        try:
            snippet = f.read_text(encoding="utf-8", errors="ignore")[:500]
        except OSError:
            snippet = ""
        result.append(Candidate(
            file=f.relative_to(repo_dir).as_posix(),
            score=float(score),
            snippet=snippet,
        ))
    return result
