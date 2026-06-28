# TriageAgent

A software **bug root-cause localization** agent implementing the **Hypothesis-Verification-Replanning (HVR)** loop, adapted from HVR-Met (ICML 2026, arXiv:2603.01121). Portfolio project for FDSE / AI engineer interviews.

## Project Goal

Given a real GitHub issue and its repository, localize the root cause:
```
issue + repo → parse symptoms → retrieve candidates → hypothesize root cause
            → verify against real code → replan on rejection → diagnosis report
```

Evaluated on **SWE-bench Lite (300)**, where each issue ships with the actual fixing PR (the
"gold patch"). The gold patch's changed files are **held out** from the agent and used only for
scoring — so accuracy reflects genuine inference, not a label leaked in the input.

## Architecture

Honest split: **deterministic preprocessing** feeds an **LLM agentic loop**, orchestrated by
`core/loop.py`. LLMs are used only where ambiguous judgment is needed.

**Deterministic preprocessing**
1. **IssueParser** (`pipeline/issue_parser.py`) — issue text → structured symptoms (error
   messages, tracebacks, mentioned identifiers, repro steps)
2. **Retriever** (`pipeline/retriever.py`) — BM25 over the repo → top-N candidate locations;
   also exposes `code_search` + `ast_index` tools the agents call live during the loop

**LLM agentic HVR loop**
3. **Hypothesizer** (`agents/hypothesizer.py`) — LLM generates ranked root-cause hypotheses
   `{location, rationale, predicted_evidence, confidence}` from symptoms + candidates
4. **Verifier** (`agents/verifier.py`) — retrieves the real code and scores fit
   `CONFIRMED / PARTIAL / REJECTED` (chain-of-thought)
5. **Replanner** (`agents/replanner.py`) — on rejection, broadens search (callers/callees, new
   keywords) and re-hypothesizes; max 3 rounds, then escalates

Diagnosis reports written by `report/generator.py` as JSON + Markdown.

## Tech Stack

- **LLM**: Anthropic Python SDK — `claude-sonnet-4-6` (Hypothesizer), `claude-haiku-4-5-20251001` (Verifier, Replanner, Reporter)
- **Dataset**: SWE-bench Lite via HuggingFace `datasets`
- **Repo handling**: `gitpython` / subprocess — checkout at instance base commit
- **Code indexing**: Python `ast` (symbol index); ripgrep (keyword search)
- **Lexical retrieval**: `rank_bm25` (candidate retrieval + baseline)
- **Embedding search**: `sentence-transformers` + FAISS (optional, `tools/embed_search.py`)
- **Orchestration**: Pure Python agent classes — no LangChain
- **Storage**: SQLite (`core/db.py`)
- **CLI**: `click` via `demo.py`
- **Data models**: Pydantic (`core/models.py`)

No Docker — localization-only; the repo's tests are not executed.

## Repo Layout

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
│   ├── models.py          # Pydantic models: Issue, Candidate, Hypothesis, Diagnosis, etc.
│   └── db.py              # SQLite persistence
├── tools/
│   ├── code_search.py     # ripgrep/keyword search
│   ├── repo_index.py      # AST symbol index
│   └── embed_search.py    # optional FAISS semantic search
├── report/generator.py
├── eval/
│   ├── metrics.py         # localization metrics vs gold patch
│   └── baseline.py        # BM25-only baseline
├── demo.py                # one-command demo
└── requirements.txt
```

## Datasets

- **SWE-bench Lite (300)** — primary eval set, loaded via HuggingFace `datasets`. Repos checked
  out at each instance's base commit, cached under `data/swebench/` (gitignored).
- **Dev slice (~20)** — fixed subset for fast iteration.
- **Ground truth** — files/functions changed in the gold patch; never shown to the agent, loaded
  only by the eval harness.

Add `data/swebench/` to `.gitignore`.

## LLM Usage

| Agent | Model | Strategy |
|---|---|---|
| Hypothesizer | `claude-sonnet-4-6` | Few-shot (2–3 localization examples) |
| Verifier | `claude-haiku-4-5-20251001` | Chain-of-thought |
| Replanner | `claude-haiku-4-5-20251001` | Structured JSON output |
| Reporter | `claude-haiku-4-5-20251001` | Template-guided |

## Evaluation Targets

| Metric | Target |
|---|---|
| File-level Acc@1 | > 0.35 |
| File-level Acc@5 | > 0.65 |
| Mean Replanning Rounds | < 2.0 |
| Cost / instance | report |

Targets are provisional anchors; real numbers recorded after the full run. Always compare against
the **BM25-only baseline** (`eval/baseline.py`) and the **no-replanning ablation**. Run
`python eval/metrics.py` against held-out gold patches.

## Build Order (vertical-slice first)

0. Thin end-to-end on ~5 instances (load → checkout → BM25 → 1 hypothesis → naive verify → report)
1. AST symbol index + `code_search` tool + real few-shot Hypothesizer
2. CoT Verifier + Replanner loop + Reporter
3. Eval harness + BM25 baseline + replanning ablation on ~20-instance dev slice
4. Full SWE-bench Lite run + SQLite persistence + `demo.py`
5. README, Loom demo; (optional) function-level localization, FAISS embedding search

## Running the Demo

```bash
python demo.py --instance <swebench_instance_id>
```

## Key Reference

Full design doc: `docs/superpowers/specs/2026-06-28-triageagent-swebench-design.md`
Original spec: `alert-triage-agent-spec.md`
