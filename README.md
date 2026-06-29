# TriageAgent

HVR-loop bug root-cause localization on SWE-bench Lite — portfolio project for FDSE / AI engineer interviews.

Given a real GitHub issue and its repository, the agent localizes the root cause:

```
issue + repo → parse symptoms → retrieve candidates → hypothesize root cause
            → verify against real code → replan on rejection → diagnosis report
```

Evaluated on **SWE-bench Lite (300 instances)**, where the gold patch's changed files are held out from the agent and used only for scoring.

---

## Architecture

```
DETERMINISTIC PREPROCESSING          LLM AGENTIC HVR LOOP
┌──────────────┐  ┌─────────────┐    ┌──────────────┐
│ IssueParser  │─▶│  Retriever  │──▶ │ Hypothesizer │◀──┐
│ symptoms,    │  │ BM25 top-N  │    │ ranked cause │   │
│ tracebacks,  │  │ candidates  │    │ locations    │   │
│ identifiers  │  │ + AST index │    └──────┬───────┘   │
└──────────────┘  └─────────────┘           ▼           │
                                     ┌──────────────┐    │
   (Retriever also exposes           │   Verifier   │    │
    code_search + ast_index          │ read code,   │    │
    tools the agents call live)      │ judge fit    │    │
                                     └──┬────────┬──┘    │
                              CONFIRMED │        │REJECTED│
                                        ▼        ▼        │
                                   [Reporter] [Replanner] │
                                   diagnosis  broaden,    │
                                   report     re-query ───┘
                                             (≤3 rounds)
```

| Component | Model | Role |
|---|---|---|
| Hypothesizer | `claude-sonnet-4-6` | Few-shot ranked hypothesis generation |
| Verifier | `claude-haiku-4-5-20251001` | Chain-of-thought code fit judgment |
| Replanner | `claude-haiku-4-5-20251001` | Structured JSON search broadening |
| Reporter | `claude-haiku-4-5-20251001` | Template-guided diagnosis report |

---

## Results

20-instance dev slice (astropy + django). Full SWE-bench Lite (300) run in progress.

| Metric | HVR Agent | BM25 Baseline |
|---|---|---|
| File-level Acc@1 | **0.67** | 0.25 |
| File-level Acc@5 | **0.67** | 0.35 |
| Avg latency / instance | 15.9 s | 0.006 s |
| Mean replanning rounds | 1.0 | — |

The HVR loop improves file-level Acc@1 by **+42 points** over BM25-only retrieval.

---

## Quick Start

```bash
pip install -r requirements.txt

# Run on a single SWE-bench Lite instance
python demo.py run --instance astropy__astropy-12907

# Run eval on the 20-instance dev slice
python eval/run_eval.py --n 20 --output output/eval/eval_n20.json
```

Repos are checked out at each instance's base commit and cached under `data/swebench/` (gitignored). Requires an `ANTHROPIC_API_KEY` environment variable.

---

## Sample Report

> **Instance:** `astropy__astropy-12907` — *Modeling: separability matrix for compound models*

**Predicted files:** `astropy/modeling/separable.py`, `astropy/modeling/core.py`
**Confidence:** 0.90 | **Replanning rounds:** 1

### Root Cause

The separability matrix for nested compound models is computed incorrectly when stacking coordinate matrices — the existing separability information of the right-hand model is overwritten instead of merged.

### Evidence Chain

When `right` is an ndarray (a nested compound model's `coord_matrix`), the code assigns `1` to the block instead of copying the actual right submatrix, overwriting its separability information.

---

## Project Layout

```
triage-agent/
├── pipeline/          # Deterministic preprocessing
│   ├── issue_parser.py    # regex symptom extraction
│   └── retriever.py       # BM25 candidate retrieval
├── agents/            # LLM agentic HVR loop
│   ├── hypothesizer.py
│   ├── verifier.py
│   └── replanner.py
├── core/
│   ├── loop.py        # HVR orchestrator
│   ├── models.py      # Pydantic models
│   └── db.py          # SQLite persistence
├── tools/
│   ├── code_search.py # ripgrep keyword search
│   └── repo_index.py  # AST symbol index
├── eval/
│   ├── metrics.py     # Acc@k vs gold patch
│   ├── baseline.py    # BM25-only baseline
│   └── run_eval.py    # eval runner
├── report/
│   └── generator.py   # JSON + Markdown reports
├── knowledge_base/
│   └── bug_patterns.json
└── demo.py            # one-command CLI
```

---

## Reference

Inspired by: *"A Hypothesis-Verification-Replanning Agentic System for Extreme Weather Diagnosis"* (HVR-Met), ICML 2026, [arXiv:2603.01121](https://arxiv.org/abs/2603.01121).
