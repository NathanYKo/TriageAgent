# TriageAgent: A Hypothesis-Verification-Replanning System for Bug Root-Cause Localization

**Inspired by:** HVR-Met (ICML 2026, arXiv:2603.01121)
**Goal:** Portfolio project demonstrating applied agentic AI for FDSE / AI engineer interviews
**Target runtime:** ~4–6 weeks solo, demonstrable in a 20-minute interview walkthrough

> **Note:** This project was reshaped from its original "IT ops alert triage on BGL logs"
> framing to **software bug root-cause localization on SWE-bench**. Same HVR loop, stronger
> substrate. See `docs/superpowers/specs/2026-06-28-triageagent-swebench-design.md` for the
> design rationale. (The filename `alert-triage-agent-spec.md` is now a historical misnomer and
> can be renamed.)

---

## 1. Problem Statement

When a bug is reported, the hardest part of fixing it is usually not writing the patch — it is
*finding where the bug lives*. An engineer reads the issue, forms a hypothesis about which code is
responsible, opens that code to check, and revises the hypothesis when the evidence does not fit.

This project builds an agent that automates that diagnostic loop:

```
GitHub issue + repo → parse symptoms → retrieve candidates → hypothesize root cause
                   → verify against real code → confirm or replan → diagnosis report
```

This is the **Hypothesis-Verification-Replanning (HVR)** loop, lifted from ICML 2026's HVR-Met
paper (originally for extreme-weather diagnosis) and re-grounded in software bug localization.

### Why this domain

- **Ground truth that is not leaked into the input.** Each SWE-bench issue ships with the actual
  fixing PR (the "gold patch"). The agent never sees it; the patch's changed files are used only
  for scoring. The accuracy number reflects genuine inference.
- **A live, recognizable benchmark.** SWE-bench is the reference AI-engineering benchmark, far
  more relatable in an interview than a 2005 supercomputer log corpus.
- **The replanning loop actually fires.** First localization guesses are usually wrong, so the
  Replanner — the paper's centerpiece — animates on most instances.

---

## 2. Architecture

### 2.1 The HVR Loop

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

### 2.2 Component Descriptions

**IssueParser** (deterministic — `pipeline/issue_parser.py`)
- Input: raw issue title + body.
- Extracts structured signal: error messages, Python tracebacks (frames → file/function),
  mentioned identifiers (module/class/function names), reproduction steps.
- Output: an `Issue` model with raw text + extracted symptoms. No LLM.

**Retriever** (deterministic — `pipeline/retriever.py`)
- Input: parsed issue + repo checked out at the instance base commit.
- Builds a **BM25 index** over code units and returns the **top-N candidate locations** that seed
  the Hypothesizer (the role the old Clusterer played: narrow the search space first).
- Exposes tools the agents call live during the loop: `code_search(query)` (ripgrep keyword
  search), `ast_index` (symbol index of modules/classes/functions), and optional
  `embed_search(query)` (FAISS over code chunks).

**Hypothesizer** (LLM — `agents/hypothesizer.py`, `claude-sonnet-4-6`)
- Input: parsed symptoms + top-N candidates (+ rejection context on replanning rounds).
- Generates 1–3 ranked hypotheses: `{location (file/function), rationale, predicted_evidence,
  confidence}`. `predicted_evidence` states what the code at that location should contain if the
  hypothesis holds.
- Few-shot prompting with 2–3 worked localization examples.

**Verifier** (LLM — `agents/verifier.py`, `claude-haiku-4-5-20251001`)
- For each hypothesis: retrieves the **real code** at the predicted location (+ related code via
  the tools) and judges, with chain-of-thought, whether it is consistent with the symptoms and
  the hypothesis's `predicted_evidence`.
- Returns `CONFIRMED` / `PARTIAL` / `REJECTED` with a reason.

**Replanner** (LLM — `agents/replanner.py`, `claude-haiku-4-5-20251001`)
- On `REJECTED` / exhausted hypotheses: broadens search (callers/callees, new keywords,
  additional candidate files) and re-invokes the Hypothesizer with the rejection reason appended.
  Structured JSON output.
- **Max 3 rounds**, then escalates: "low confidence — human review required."

**Reporter** (LLM — `report/generator.py`, `claude-haiku-4-5-20251001`)
- On `CONFIRMED`: produces the diagnosis report — root-cause files/functions, evidence chain,
  plain-English explanation, confidence. Written as JSON + Markdown.

### 2.3 LLM Calls

| Stage | LLM Task | Prompt Strategy |
|---|---|---|
| Hypothesizer | Generate ranked root-cause locations from symptoms + candidates | Few-shot (2–3 examples) |
| Verifier | Judge whether real code confirms the hypothesis | Chain-of-thought |
| Replanner | Reformulate hypothesis given rejection reason | Structured output (JSON) |
| Reporter | Summarize the diagnosis in plain English | Template-guided |

All LLM calls use `claude-haiku-4-5-20251001` for speed/cost, except the Hypothesizer, which uses
`claude-sonnet-4-6` where reasoning quality matters most.

---

## 3. Datasets

### Primary: SWE-bench Lite (300) — **Start here**

- **What it is:** 300 real GitHub issues from popular Python repositories, each paired with the
  PR that fixed it (the gold patch) and the test that verifies the fix.
- **Why it's ideal:** The gold patch gives honest, held-out ground truth — the files (and
  functions) that actually had to change. It is the reference AI-engineering benchmark.
- **Download:** HuggingFace `datasets` — `princeton-nlp/SWE-bench_Lite`.
- **Repos:** checked out at each instance's base commit (gitpython/subprocess), cached under
  `data/swebench/` (gitignored).

### Dev slice (~20) — **Use for rapid iteration**

- A fixed ~20-instance subset for fast feedback loops before running the full 300.

### Ground truth handling

- The agent receives only the issue text + repo at the base commit.
- The gold patch's changed files are loaded **only by the eval harness** for scoring — never by
  the agent.

---

## 4. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| LLM calls | Anthropic Python SDK (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001`) | Fast iteration; quality where it matters |
| Dataset | `datasets` (HuggingFace) | SWE-bench Lite, one-line load |
| Repo handling | `gitpython` / subprocess | checkout at base commit |
| Code indexing | Python `ast` | symbol index (modules/classes/functions) |
| Lexical retrieval | `rank_bm25` | candidate retrieval + baseline |
| Code search | ripgrep | fast keyword search tool |
| Embedding search | `sentence-transformers` + FAISS (optional) | semantic code retrieval, no external service |
| Orchestration | Pure Python with explicit agent classes | architecture stays visible; no LangChain |
| Storage | SQLite (`sqlite3` stdlib) | resumable, inspectable runs |
| CLI | `click` | clean demo interface |
| Output | JSON + Markdown | easy to show in an interview |

No Docker (localization-only; the repo's tests are not executed). Runs entirely local apart from
LLM API calls.

---

## 5. Repo Structure

```
triage-agent/
├── README.md
├── data/
│   └── swebench/          # cached instances + checked-out repos (gitignored)
├── knowledge_base/
│   └── bug_patterns.json  # lightweight bug taxonomy priors
├── pipeline/              # deterministic preprocessing
│   ├── issue_parser.py    # issue text → structured symptoms
│   └── retriever.py       # BM25 candidate retrieval + tool exposure
├── agents/                # LLM agentic loop
│   ├── hypothesizer.py    # ranked root-cause hypotheses
│   ├── verifier.py        # evidence retrieval + scoring
│   └── replanner.py       # hypothesis reformulation
├── core/
│   ├── loop.py            # HVR loop orchestrator
│   ├── models.py          # Pydantic models (Issue, Candidate, Hypothesis, Diagnosis, ...)
│   └── db.py              # SQLite persistence
├── tools/
│   ├── code_search.py     # ripgrep/keyword search over the repo
│   ├── repo_index.py      # AST symbol index
│   └── embed_search.py    # optional FAISS semantic search
├── report/
│   └── generator.py       # diagnosis report writer
├── eval/
│   ├── metrics.py         # localization metrics vs gold patch
│   └── baseline.py        # BM25-only localization baseline
├── demo.py                # one-command demo
└── requirements.txt
```

---

## 6. Bug Pattern Knowledge Base (seed)

`knowledge_base/bug_patterns.json` — a lightweight bug taxonomy used as priors for the
Hypothesizer. Unlike the original log-domain KB, this is **secondary**: the Hypothesizer reasons
mostly from issue + code directly, so the KB is kept small and may be cut if it does not
measurably improve Acc@k.

```json
[
  {
    "id": "none_deref",
    "name": "None dereference / missing null check",
    "signatures": ["AttributeError", "'NoneType' object has no attribute"],
    "typical_fix_area": "guard clause or default value"
  },
  {
    "id": "off_by_one",
    "name": "Off-by-one / boundary error",
    "signatures": ["IndexError", "list index out of range", "slice"],
    "typical_fix_area": "loop bound or range/slice expression"
  },
  {
    "id": "wrong_default_arg",
    "name": "Incorrect or mutable default argument",
    "signatures": ["unexpected shared state", "default value"],
    "typical_fix_area": "function signature default"
  },
  {
    "id": "edge_case",
    "name": "Missing edge-case handling",
    "signatures": ["empty input", "zero", "negative", "unicode"],
    "typical_fix_area": "conditional branch for the edge case"
  },
  {
    "id": "api_misuse",
    "name": "Library/API misuse",
    "signatures": ["TypeError", "deprecated", "wrong argument"],
    "typical_fix_area": "call site of the misused API"
  }
]
```

---

## 7. Evaluation Plan

Measured against the **held-out gold patch**:

| Metric | Definition | Target |
|---|---|---|
| **File-level Acc@1** | Gold file is the agent's #1 ranked location | > 0.35 |
| **File-level Acc@5** | A gold file is in the agent's top-5 locations | > 0.65 |
| **File-level F1** | Precision/recall of predicted vs. gold changed files | report |
| **Function-level Acc@5** (stretch) | A gold function in top-5 | report |
| **Mean Replanning Rounds** | Avg rounds before confirmation/escalation | < 2.0 |
| **Cost / instance** | Tokens → USD per diagnosis | report |
| **Latency / instance** | Wall-clock seconds per diagnosis | report |

Targets are provisional anchors; real numbers recorded after the full run. Acc@k is the standard
Agentless-style localization metric.

### Comparisons that make the result meaningful

- **Baseline to beat** (`eval/baseline.py`): BM25-retrieval-only localization, no LLM loop.
  Headline claim: "the HVR loop beats BM25 by X points on Acc@5."
- **Ablation:** full loop **with** replanning vs. **single-shot**. Demonstrates the loop earns
  its cost.

Run `python eval/metrics.py` over a subset; it compares predicted locations to held-out gold
files and emits the table plus baseline and ablation columns.

---

## 8. Build Plan (4–6 Weeks, vertical-slice first)

### Milestone 0 — Thin end-to-end (week 1)
- Load SWE-bench Lite; checkout a repo at base commit; BM25 retrieve; one Hypothesizer call;
  naive verify; emit a report; score ~5 instances. Get a real (bad) number; surface integration
  issues early.
- Define all Pydantic models in `core/models.py`.

### Milestone 1 — Retrieval + Hypothesizer
- AST symbol index (`tools/repo_index.py`) + `code_search` tool (`tools/code_search.py`).
- Real few-shot Hypothesizer.

### Milestone 2 — Verify + Replan + Report
- CoT Verifier; Replanner loop (≤3 rounds); Reporter (JSON + Markdown).
- Wire the full HVR loop in `core/loop.py`.

### Milestone 3 — Evaluation
- `eval/metrics.py`, BM25 `eval/baseline.py`, replanning ablation on the ~20-instance dev slice.

### Milestone 4 — Full run + hardening
- Full SWE-bench Lite run; record baseline numbers; SQLite persistence; `demo.py`.

### Milestone 5 — Polish + README
- README with architecture diagram and a sample diagnosis report; 2-minute Loom demo.

### Milestone 6 (buffer) — Optional Extensions
- Function-level localization metric; FAISS embedding search in the Retriever.

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

The bracketed numbers become real after Milestone 4. Everything before that is the architecture
story.

---

## 10. Resources & Links

| Resource | URL |
|---|---|
| HVR-Met paper (ICML 2026) | https://arxiv.org/abs/2603.01121 |
| SWE-bench | https://www.swebench.com |
| SWE-bench Lite (HF) | https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite |
| SWE-bench repo | https://github.com/princeton-nlp/SWE-bench |
| rank_bm25 | https://github.com/dorianbrown/rank_bm25 |
| Anthropic Python SDK | https://github.com/anthropics/anthropic-sdk-python |
