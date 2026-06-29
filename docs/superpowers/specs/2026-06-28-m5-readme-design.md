# M5 README Design

**Date:** 2026-06-28
**Status:** Approved
**Milestone:** M5 — Polish
**Scope:** README.md only (no FAISS embed search, no function-level localization)

---

## Goal

Write a tight, scannable `README.md` for the project root that works as a portfolio poster for FDSE / AI engineer interviews. The README must communicate what the project does, show real numbers, and let someone clone-and-run in under 5 minutes.

---

## Sections

### 1. Title + one-liner

```
# TriageAgent
HVR-loop bug root-cause localization on SWE-bench Lite — portfolio project for FDSE / AI engineer interviews.
```

### 2. Architecture (ASCII diagram)

The HVR loop diagram from the design doc, trimmed to README width (~80 chars). Shows the deterministic preprocessing → LLM agentic loop → report pipeline.

### 3. Results

Eval table using real 20-instance numbers from `output/eval/eval_n20.json`:

| Metric | HVR Agent | BM25 Baseline |
|---|---|---|
| File-level Acc@1 | 0.67 | 0.25 |
| File-level Acc@5 | 0.67 | 0.35 |
| Avg latency / instance | 15.9 s | 0.006 s |
| Mean replanning rounds | 1.0 | — |

Note: n=20 dev slice; full SWE-bench Lite (300) run in progress.

### 4. Quick start

```bash
pip install -r requirements.txt
# Run on a single instance
python demo.py run --instance astropy__astropy-12907
# Run eval on the 20-instance dev slice
python eval/run_eval.py --n 20 --output output/eval/eval_n20.json
```

### 5. Sample report

Embed the `astropy__astropy-12907` diagnosis from `output/integration/astropy__astropy-12907.md` — already the cleanest output available.

### 6. Project layout

Condensed file tree covering only source directories (pipeline/, agents/, core/, tools/, eval/, report/, demo.py). No .venv, no data/.

### 7. Reference

HVR-Met citation: *"A Hypothesis-Verification-Replanning Agentic System for Extreme Weather Diagnosis"*, ICML 2026, arXiv:2603.01121.

---

## What is NOT included

- Badges (noise for a portfolio project)
- Contributing / license sections
- FAISS embedding search (deferred, optional M5 item)
- Function-level localization (deferred, optional M5 item)
- Full narrative "How it works" prose (that's in the design doc)

---

## Source of truth for content

- Architecture diagram: `docs/superpowers/specs/2026-06-28-triageagent-swebench-design.md` §2
- Eval numbers: `output/eval/eval_n20.json`
- Sample report: `output/integration/astropy__astropy-12907.md`
- Run commands: `demo.py` and `eval/run_eval.py`
