# TriageAgent: An HVR Bug-Localization Agent on SWE-bench

**Date:** 2026-06-28
**Status:** Approved design (pre-implementation)
**Supersedes:** `alert-triage-agent-spec.md` (the original BGL log-triage framing)
**Inspired by:** HVR-Met, *"A Hypothesis-Verification-Replaning Agentic System for Extreme Weather Diagnosis"* (ICML 2026, arXiv:2603.01121)
**Goal:** Polished portfolio project for FDSE / AI engineer interviews.

---

## 1. Summary

TriageAgent applies the **Hypothesis-Verification-Replanning (HVR)** loop from the HVR-Met
weather-diagnosis paper to a new domain: **software bug root-cause localization**.

Given a real GitHub issue and the repository it belongs to, the agent:

```
issue + repo → parse symptoms → retrieve candidates → hypothesize root cause
            → verify against real code → replan on rejection → diagnosis report
```

It is evaluated on **SWE-bench Lite (300 instances)**, where each issue is paired with the
actual fixing PR (the "gold patch"). The gold patch's changed files are **held out** from the
agent and used only for scoring — so the headline accuracy number reflects genuine inference,
not a label leaked in the input.

### Why this framing (design rationale)

This project pivoted away from the original BGL/HDFS log-triage idea for three reasons, all of
which this design resolves:

1. **No leaked label.** BGL's ground-truth alert category sits inline in the input data, making
   any accuracy number suspect. SWE-bench's ground truth (the gold patch) is never shown to the
   agent.
2. **Not an over-trodden benchmark.** BGL + drain3 is the canonical academic log-anomaly setup.
   Bug localization on SWE-bench is the live, recognizable AI-engineering benchmark.
3. **The replanning loop actually fires.** First localization guesses are usually wrong, so the
   Replanner — the paper's centerpiece — animates on most instances instead of being dead weight.

---

## 2. Architecture

A clean split between **deterministic preprocessing** and the **LLM agentic loop**. LLMs are used
only where ambiguous judgment is needed; parsing, indexing, and retrieval stay deterministic,
cheap, and reproducible.

```
DETERMINISTIC PREPROCESSING          LLM AGENTIC HVR LOOP
┌──────────────┐  ┌─────────────┐    ┌──────────────┐
│ IssueParser  │─▶│  Retriever  │──▶ │3.Hypothesizer│◀──┐
│ symptoms,    │  │ BM25 top-N  │    │ ranked cause │   │
│ tracebacks,  │  │ candidates  │    │ locations    │   │
│ identifiers  │  │ + AST index │    └──────┬───────┘   │
└──────────────┘  └─────────────┘           ▼           │
                                     ┌──────────────┐    │
   (Retriever also exposes code-     │ 4. Verifier  │    │
    search/AST tools the agents      │ read code,   │    │
    call live during the loop)       │ judge fit    │    │
                                     └──┬────────┬──┘    │
                              CONFIRMED │        │ REJECTED│
                                        ▼        ▼        │
                                  [Reporter]  [5.Replanner]
                                   diagnosis   broaden,    │
                                   report      re-query ───┘
                                              (≤3 rounds → escalate)
```

### 2.1 Deterministic preprocessing

**IssueParser** (`pipeline/issue_parser.py`)
- Input: raw issue title + body.
- Extracts structured signal: error messages, Python tracebacks (frames → file/function),
  mentioned identifiers (module/class/function names referenced in the text), reproduction steps.
- Output: an `Issue` model with raw text + extracted symptoms.
- No LLM; pure parsing/regex/heuristics.

**Retriever** (`pipeline/retriever.py`)
- Input: parsed issue + repo checked out at the instance's base commit.
- Builds a **BM25 index** over code units (files and/or functions) and returns the **top-N
  candidate locations** that seed the Hypothesizer. This is the role the old Clusterer played:
  narrow the search space deterministically before the LLM reasons.
- Also exposes **tools the agents call live during the loop**:
  - `code_search(query)` — keyword/ripgrep search over the repo (`tools/code_search.py`).
  - `ast_index` — symbol index of modules/classes/functions with locations and signatures
    (`tools/repo_index.py`, built with Python's `ast`).
  - `embed_search(query)` — optional FAISS semantic search over code chunks
    (`tools/embed_search.py`, stretch).

### 2.2 LLM agentic HVR loop

**Hypothesizer** (`agents/hypothesizer.py`, `claude-sonnet-4-6`)
- Input: parsed symptoms + top-N candidates (+ rejection context on replanning rounds).
- Generates 1–3 ranked hypotheses: `{location (file/function), rationale, predicted_evidence,
  confidence}`. `predicted_evidence` states what the code at that location should contain if the
  hypothesis is true (e.g. "a function that returns `None` when the input list is empty").
- Few-shot prompting with 2–3 worked localization examples.

**Verifier** (`agents/verifier.py`, `claude-haiku-4-5-20251001`)
- For each hypothesis: retrieves the **real code** at the predicted location (+ related code via
  the tools) and judges, with chain-of-thought, whether it is consistent with the issue symptoms
  and the hypothesis's `predicted_evidence`.
- Returns `CONFIRMED` / `PARTIAL` / `REJECTED` with a reason.

**Replanner** (`agents/replanner.py`, `claude-haiku-4-5-20251001`)
- On `REJECTED` (or all hypotheses exhausted): broadens the search — expand to callers/callees,
  new keywords, additional candidate files — and re-invokes the Hypothesizer with the rejection
  reason appended as context. Structured JSON output.
- **Max 3 rounds**, then escalate: "low confidence — human review required."

**Reporter** (`report/generator.py`, `claude-haiku-4-5-20251001`)
- On `CONFIRMED`: produces the diagnosis report — root-cause files/functions, evidence chain,
  plain-English explanation, confidence. Template-guided. Written as JSON + Markdown.

### 2.3 Orchestration

`core/loop.py` runs the closed loop. `core/models.py` holds Pydantic models (`Issue`,
`Candidate`, `Hypothesis`, `Evidence`, `Verdict`, `Diagnosis`, `RunResult`). `core/db.py`
persists runs to SQLite so eval runs are resumable and inspectable.

---

## 3. Data

- **SWE-bench Lite (300)** loaded via HuggingFace `datasets`.
- Each repo is checked out at the instance **base commit** (gitpython/subprocess) and cached
  under `data/swebench/` (gitignored).
- **Held-out ground truth:** the set of files (and functions) changed in the instance's gold
  patch. The agent never sees the patch; it is loaded only by the eval harness for scoring.
- **Dev slice:** a fixed ~20-instance subset for fast iteration. **Headline run:** full 300.

---

## 4. Evaluation

The eval is the centerpiece of the interview story, so it is rigorous and honest.

| Metric | Definition | Target |
|---|---|---|
| **File-level Acc@1** | Gold file is the agent's #1 ranked location | > 0.35 |
| **File-level Acc@5** | A gold file is in the agent's top-5 locations | > 0.65 |
| **File-level F1** | Precision/recall of predicted vs. gold changed files | report |
| **Function-level Acc@5** (stretch) | A gold function in top-5 | report |
| **Mean replanning rounds** | Avg rounds before confirmation/escalation | < 2.0 |
| **Cost / instance** | Tokens → USD per diagnosis | report |
| **Latency / instance** | Wall-clock seconds per diagnosis | report |

> Targets are provisional anchors; real numbers are recorded after the M4 full run. Acc@k is the
> standard Agentless-style localization metric.

### Comparisons that make the result meaningful

- **Baseline to beat** (`eval/baseline.py`): BM25-retrieval-only localization, no LLM loop. The
  headline claim is "the HVR loop beats BM25 by X points on Acc@5."
- **Ablation:** full loop **with** replanning vs. **single-shot** (no replanning). Demonstrates
  the replanning loop earns its cost.

`eval/metrics.py` runs the agent over a subset, compares predicted locations to held-out gold
files, and emits the table above plus the baseline and ablation columns.

---

## 5. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| LLM | Anthropic Python SDK | Hypothesizer `claude-sonnet-4-6`; Verifier/Replanner/Reporter `claude-haiku-4-5-20251001` |
| Dataset | `datasets` (HuggingFace) | SWE-bench Lite |
| Repo handling | `gitpython` / subprocess | checkout at base commit |
| Code indexing | Python `ast` | symbol index (modules/classes/functions) |
| Lexical retrieval | `rank_bm25` | candidate retrieval + baseline |
| Code search | ripgrep | keyword search tool |
| Semantic search (opt) | `sentence-transformers` + FAISS | stretch |
| Orchestration | Pure Python agent classes | no LangChain |
| Storage | SQLite (stdlib) | resumable runs |
| CLI | `click` | `demo.py` |
| Output | JSON + Markdown | reports |

**Dropped from the original spec:** `drain3`, sliding-window log clustering.

No Docker required (localization-only; we do not execute the repo's tests).

---

## 6. Repo Layout

```
triage-agent/
├── data/
│   └── swebench/          # cached instances + checked-out repos (gitignored)
├── knowledge_base/
│   └── bug_patterns.json  # lightweight bug taxonomy priors
├── pipeline/              # deterministic preprocessing
│   ├── issue_parser.py
│   └── retriever.py
├── agents/                # LLM agentic loop
│   ├── hypothesizer.py
│   ├── verifier.py
│   └── replanner.py
├── core/
│   ├── loop.py            # HVR orchestrator
│   ├── models.py          # Pydantic models
│   └── db.py              # SQLite persistence
├── tools/
│   ├── code_search.py     # ripgrep/keyword search
│   ├── repo_index.py      # AST symbol index
│   └── embed_search.py    # optional FAISS
├── report/
│   └── generator.py
├── eval/
│   ├── metrics.py         # localization metrics vs gold patch
│   └── baseline.py        # BM25-only baseline
├── demo.py
└── requirements.txt
```

---

## 7. Knowledge Base

`knowledge_base/bug_patterns.json` — a lightweight bug taxonomy used as priors for the
Hypothesizer (e.g. `None`-dereference, off-by-one, wrong default argument, missing edge-case
handling, API misuse), each with signature keywords. Unlike the log-domain KB, this is
**secondary** — the Hypothesizer reasons mostly from issue + code directly — so it is kept small
and may be cut if it does not measurably help.

---

## 8. Build Order (vertical-slice first)

- **M0 — Thin end-to-end (week 1):** load SWE-bench Lite, checkout a repo, BM25 retrieve, one
  Hypothesizer call, naive verify, emit a report, score ~5 instances. Produces a real (bad)
  number and surfaces integration issues early.
- **M1 — Retrieval + Hypothesizer:** AST symbol index, `code_search` tool, real few-shot
  Hypothesizer.
- **M2 — Verify + Replan + Report:** CoT Verifier, Replanner loop (≤3 rounds), Reporter
  (JSON + Markdown).
- **M3 — Eval harness:** `metrics.py`, BM25 `baseline.py`, replanning ablation, on the
  ~20-instance dev slice.
- **M4 — Full run + persistence:** full SWE-bench Lite run → headline numbers; SQLite
  persistence; `demo.py` one-command run.
- **M5 — Polish:** README with architecture diagram + sample report, Loom demo; optional
  function-level localization and FAISS embedding search.

---

## 9. Interview Narrative

> "I took the Hypothesis-Verification-Replanning loop from an ICML 2026 weather-diagnosis paper
> and re-grounded it in software bug localization. Given a GitHub issue and a repo, the agent
> hypothesizes root-cause locations, actively verifies each against the real code, and replans
> when the evidence rejects a hypothesis. On SWE-bench Lite — 300 real issues with held-out gold
> patches — it beats a BM25 baseline by [X] points on top-5 localization accuracy, at a mean of
> [Y] replanning rounds and [Z]¢ per diagnosis. The architecture is pure Python with a clean
> split between deterministic retrieval and the LLM reasoning loop, so I can walk through any
> component."

Bracketed numbers become real after M4.

---

## 10. Open Questions / Deferred to Implementation

- Candidate granularity: file-level vs. function-level retrieval for the Hypothesizer seed
  (start file-level; function-level is a stretch metric).
- Exact code-context budget per Verifier call (token/cost tradeoff) — tune during M2.
- Whether `bug_patterns.json` measurably improves Acc@k — decide empirically in M3.

---

## 11. Resources

| Resource | URL |
|---|---|
| HVR-Met paper (ICML 2026) | https://arxiv.org/abs/2603.01121 |
| SWE-bench | https://www.swebench.com / https://github.com/princeton-nlp/SWE-bench |
| SWE-bench Lite (HF) | https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite |
| Anthropic Python SDK | https://github.com/anthropics/anthropic-sdk-python |
| rank_bm25 | https://github.com/dorianbrown/rank_bm25 |
