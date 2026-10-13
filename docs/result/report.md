# Terminal-Bench task-generation pipeline — final report

**Audited revision:** the commit that adds this file (see `docs/result/README.md` for the exact hash).
**Models:** authoring, reviews, judges and red-team = `openai/gpt-5.6-luna`; calibration = `terminus-2` + `openrouter/openai/gpt-5.4-mini`. Novelty pool = Terminal-Bench 2.1 (`data/tb-reference/terminal-bench-2-1`, 89 tasks) + `examples/`.
**Scope note:** the original work trial fixed Sonnet 4.6 (author) and Opus 4.8 (calibration). The user later opened the model rule; this run uses the pair above and labels every result. Historical Sonnet→Opus results remain separate and are never mixed into this run's funnel.

This document is self-contained. Raw evidence lives under `runs/`, `reports/`, `output/` and `docs/result/evidence/`; the numbers below are copied from it and from `docs/result/verification.json`.

---

## 1. Executive summary

The pipeline generates Terminal-Bench/Harbor tasks with an LLM, gates them through structural, functional, quality, novelty and red-team checks, then calibrates difficulty by running a solver five times and keeping only tasks whose pass count lands in the **1–3 of 5** learnable band with valid failures.

What is solid:
- A complete, resumable pipeline (spec sampler → blueprint → in-container authoring meta-task → host gates → calibration → shipping) with ledgers, cost tracking, novelty and reward-hacking defenses (§4, §5).
- A **candidate batch of 22 records** (12 fresh generations, 10 reuse-recalibrated copies of earlier packages) with a browsable index (`runs/candidates/README.md`).
- Two stretch goals implemented and measured (A cost-efficient evaluation, C diversity), one exercised with an honest negative result (B tuning), and one partially measured (D human-likeness).

What is limited, and must not be overstated:
- **A verification-first audit rejected all four previously "shipped" tasks** on exact-version and quality grounds (§6). Previous output/ contents are preserved but moved to `runs/audit-20261013/` and are **not** final approvals.
- The learnable-band yield for this pairing is low and bimodal (§6.4).
- One task was fully repaired and re-verified through the audit (§7); its status is recorded in `docs/result/verification.json`.

---

## 2. Requirement status matrix

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1.1 | Generated tasks pass the structural validator | Achieved | `validator/validate.py` + `scripts/validate.sh`; gate results in ledger |
| 1.2 | Functionally correct: oracle passes, nop fails | Achieved | `gate_functional` events; independent re-runs saved in `docs/result/evidence/` |
| 2 | Produce tasks in the 1–3/5 learnable band | Partial | Bimodal yield; see §6.4 and `docs/result/verification.json` |
| 3 | Batch of 10+ candidates with Part-3 metrics | Achieved | 22 candidate records; `reports/summary.md` |
| 4 | Source, `CHANGELOG.md`, git history | Achieved | this repo |
| A | Cost-efficient evaluation | Achieved (with caveats) | §9.1 |
| B | Difficulty tuning | Not demonstrated | §9.2 |
| C | Diversity analysis | Achieved (with caveats) | §9.3 |
| D | Human-likeness | Partial | §9.4 |

Machine-readable statuses and hashes are in `docs/result/verification.json`.

---

## 3. Models, settings and constraints

- **Author/reviewer/judge/red-team:** `openai/gpt-5.6-luna`. **Calibration solver:** `openrouter/openai/gpt-5.4-mini` (≈60% on Terminal-Bench 2). One fixed pair and judge per batch; the band is relative to the calibration model.
- **Why the model change:** the original Sonnet→Opus pairing produced 0 of 9 in band and was slow; a five-model speed test (`docs/model-speedtest.md`) chose Luna as the fastest model that produced valid packages, paired with a same-brand weaker solver.
- **Task constraints:** `[agent].timeout_sec = 3600`; authoring ≤60 turns, calibration ≤100 turns (cap exhaustion = invalid); reward-hacking defenses via leak scan, red-team and pass audit; nothing answer-bearing in `environment/`.
- **Spend:** account ceiling $400 of the $500 key; this goal's own cap $40. Snapshots in `docs/result/evidence/usage-*.txt`.

---

## 4. Architecture and pipeline

```
spec sampler (inverse-frequency over a 10-axis taxonomy)
  -> blueprint (author model) -> rubric review + novelty gate (TB 2.1 + examples + our own)
  -> authoring meta-task (terminus-2 + author model in a container; artifacts=/app/output)
  -> gates: structure, lint, leak scan -> oracle 3/3 + nop -> harbor check quality
            -> novelty re-check -> red-team (hack elicitation)   [failures feed repair rounds]
  -> calibration: terminus-2 + calibration model, exact curtailment of the 5-run band, every trial judged
  -> output/<task>/ (learnable only) + README with why the model fails it
```

Modules: `generator/` (spec, blueprint, author, metatask, pipeline), `validator/` (validate, lint, leak_scan, novelty), `evaluator/` (harbor_runner, calibrate, redteam, quality, slots), `analysis/` (ledger, judge, tuner, report, diversity, human_likeness, package_evidence), `scripts/` (run_batch, calibrate_candidates, tune_candidates, recalibrate, study, audit_*), `tests/`.

Every stage is a small function that records an append-only ledger event (`runs/ledger.jsonl`) carrying stage, cost, seconds, result and a `models` label.

---

## 5. Method

- **Generation:** inverse-frequency spec sampling (Tmax/CLI-Universe axes) → blueprint with an internal hint, requirements, levers and a predicted pass rate → rubric review + novelty gate → in-container authoring meta-task.
- **Gates (cheap first):** structure, lint, leak scan, build, oracle 3/3, nop, `harbor check` quality rubric, novelty re-check, red-team.
- **Calibration:** exact sequential curtailment of the 5-run band test; each trial judged valid/invalid from its trajectory; a hacked or invalid trial stops calibration.
- **Difficulty by construction:** hidden-seed verify-time instances, multi-stage dependencies, shallow-self-check traps and long-horizon inputs, because an author as strong as the solver cannot out-think it (§9.2).

---

## 6. Candidate audit

### 6.1 Batch size and origins
22 candidate records for this model pair: **12 fresh generations**, **10 reuse-recalibrated copies** (`<id>-m`) of earlier packages re-run for the new calibration model. The reused copies are not independent generations; the report distinguishes them.

### 6.2 Outcome distribution (latest candidate calibration)
`too_easy` 1, `too_hard` 6, `invalid` 7, `learnable` 3 — **bimodal**, consistent with Tmax's warning about pools without continuous difficulty control.

### 6.3 Why the previous outputs were quarantined
Four directories were previously placed in `output/`. A strict re-audit found:
- no immutable, package-hash-bound calibration record inside the shipped directory;
- the release packager failed the quality rubric on test coverage and verification-time network dependence;
- at least one shipped task (`repair-log-replay-sql`) had exactly **one** judged pass (1/3), i.e. a curtailed record, not a full 1–3/5 statement;
- some READMEs cited synthetic candidate ids (`shipcand`) that never existed, and the live report's learnable count disagreed with the preserved records.

All four were archived **unchanged** to `runs/audit-20261013/original-output/` and moved to `runs/audit-20261013/pending/`. No evidence was deleted; the old claims are preserved as history.

### 6.4 A systemic finding: wall-clock performance is an invalid difficulty lever
Two of the strongest candidates relied on a stated wall-clock performance budget ("under six seconds", "elapsed < 12", a 20-second dense-export time). The `harbor check` rubric correctly rejects these as **environment-dependent (invalid) failure modes**: a correct solution can fail under host load. This is the same tension the plan flags ("no hidden limits or timeouts"). Both tasks were repaired to remove the timing gate and keep a correctness/equivalence check on large inputs. Consequence: performance-based difficulty must be expressed deterministically (query-plan/operation checks) or dropped.

### 6.5 Yield
Stage counts for the current package hash are in `reports/summary.md`. The in-band rate is low: of 17 calibrated candidates, 3 were learnable. Cost per in-band task was correspondingly high, so the plan's own go/no-go (~$40 per in-band task) was met only weakly. This is reported honestly rather than tuned away.

---

## 7. Approved task (audit outcome)

Two audit candidates were brought to full quality approval; approval also requires structure, oracle 3/3, nop and **five judged attempts in the 1–3 band with valid failures only**.

- **`releaseforge` (repaired):** quality approved after removing the timing gate and expanding to 15 deterministic tests; structure, oracle 3/3 and nop pass. **Calibration: 0/5 — too hard** for GPT-5.4-mini, and at least one failure judged invalid (`docs/result/evidence/packager-final-calibration.json`). **Not approved** (out of band).
- **`optimize-policy-decision-audit` (repaired):** wall-clock gate removed, keeping the correctness/equivalence refactor. Its original five trials were 3/5 with honest passes and valid quoted failures; re-approval requires a fresh quality pass, oracle/nop and a full recalibration on the changed package.

The final per-task verdict, package hashes and check results are in `docs/result/verification.json`. If neither lands 1–3 with valid failures after repair, **no task is approved** and this document states that plainly rather than shipping a weak task.

---

## 8. Verification and reproducibility

- `bash scripts/validate.sh <task>` for structure; independent `harbor run -a oracle -k 3` and `-a nop` for functional correctness.
- Fresh-clone builds; no reliance on local host files or cached images.
- Immutable approval: `output/<task>/calibration.json` + `verification.json` bound to a content hash of the task package; a directory is not approval (`analysis/package_evidence.py`, tests in `tests/test_package_evidence.py`).
- Report provenance: current-package gate counts, model-pair isolation, hard-coded Opus labels removed, `approved_shipped` from immutable records (`analysis/report.py`).

---

## 9. Stretch goals

### 9.1 A — Cost-efficient evaluation
Exact curtailment is implemented and shown to be lossless vs running all five trials (all 2^5 sequences in `analysis/curtailment.py`). The report's simulation table gives saved trials by true pass probability (≈12–23% for p∈[0.2,0.8]); the 0/3 early-reject alternative saves more (~25–40%) at the cost of recall. **Caveat:** the dollar figure mixes exact-curtailment savings with early stops on invalid tasks; the trial-count saving is the trustworthy number. Blueprint-time predicted pass rate did **not** track observed outcomes (correlation ≈ −0.29 over 9 earlier tasks), so it is not used as a pre-filter.

### 9.2 B — Difficulty tuning
`analysis/tuner.py` + `scripts/tune_candidates.py` implement knob → lever → regenerate with logged mutations. Ten tuning records exist. **No tuning experiment is demonstrated to have moved a task into the band** (the tuner runs ended `gates_failed`). This is a measured negative result: tuning is implemented and exercised, but successful difficulty adjustment is not shown.

### 9.3 C — Diversity
`analysis/diversity.py` reports per-axis coverage and balance exp(H)/N, instruction uniqueness (TF-IDF cosine, Vendi) and novelty against the reference sets. Rejects per layer are recorded. **Caveat:** the automatic novelty check ran only against TB 2.1 + `examples/`, not the full published corpus; this is disclosed and is not full public-task decontamination.

### 9.4 D — Human-likeness
Stylometrics (`analysis/human_likeness.py`) show generated instructions are longer (≈330 vs 183 words) and code-span-heavy (≈34 vs 1.2) with no bullets vs 10.2 in examples — the "verbose, over-structured" tells the guideline paper warns about. A seeded blinded experiment over 24 example×generated pairs (model `openai/gpt-5.6-luna`, seed 20261013) gave **accuracy 0.375, 95% Wilson CI [0.212, 0.573]** — indistinguishable from chance at this sample size, but below 50% and not evidence of proven human-likeness. Caveats: repeated pairs are not independent, the model judged its own family's output, temperature-0 reruns were not deterministic, and the packages were pre-audit versions. Evidence: `docs/result/evidence/blind.json`, `stylometrics.json`.

---

## 10. Cost and time

Per-scope ledger estimates (newest scope is this run):

| Scope | Est. USD | Stage-hours | Events |
|---|---|---|---|
| official Sonnet→Opus (historical) | 502.2 | 51.9 | 1036 |
| study Sonnet→Opus (historical) | 16.95 | 30.7 | 218 |
| official Gemini-3.8 (historical) | 7.99 | 3.7 | 121 |
| official Luna→Luna (historical) | 3.99 | 10.3 | 450 |
| **official Luna→GPT-5.4-mini (this run)** | 12.48 | 11.2 | 526 |

### 10.1 Reconciliation against the account key

The account key is authoritative: conservative spend **$211.76**, usage counter $188.74, remaining **$288.24**. The local ledger's raw total is **$544.19** over 2,391 events and 110.5 summed stage-hours — a residual of **$332.43 (61%)**. Per raw mode/model scope:

| Scope (mode · model) | Ledger est. USD | Summed stage-hours | Events |
|---|---|---|---|
| official · unlabeled (Sonnet→Opus era) | 502.20 | 51.9 | 1,036 |
| official · `openai/gpt-5.6-luna` author + GPT-5.4-mini solver | 16.47 | 21.5 | 976 |
| study · unlabeled | 16.95 | 30.7 | 218 |
| official · `google/gemini-3.8-flash` | 7.99 | 3.7 | 121 |
| dev · unlabeled | 0.57 | 2.7 | 10 |
| speedtest · Gemini | 0.00 | 0.0 | 30 |

**What reconciles.** Over the audit window bracketed by consecutive `make usage` snapshots, the independently priced per-step costs recorded by the audit scripts sum to **$0.4778** against a key delta of **$0.4551** — a ratio of **1.05**, inside the 10% target (`evidence/reconciliation-audit-window.json`). Counter lag is the only systematic offset; snapshots were taken ~1–2 min after each paid step.

**What does not reconcile, and why it stays open.** The entire residual sits in the **unlabeled historical era** ($502.20 across 1,036 events), which predates the model labeling this audit introduced. Investigated causes that can be ruled out: retries are separate ledger rows and are not double counted; excluded and incomplete trials carry their own rows; shared-key use by other projects would push the key *above* the ledger, not below. Causes that **cannot** be verified because the data was not retained: per-event token counts and cache-token usage, so the estimated-price vs actual-charge gap cannot be recomputed; pricing tier changes during the earlier period. The plan's reconciliation item therefore remains **open with a measured gap**, not explained away. Raw snapshots, per-scope and per-stage estimates and the residual are published in `evidence/reconciliation.json` and `evidence/reconciliation-windows.json`; no raw ledger event was modified.

### 10.2 Wall-clock versus summed stage time

Summed stage time (110.5 h across all modes) is an upper bound, not elapsed time: gates, authoring and calibration overlapped under bounded concurrency (≤3 calibration trials). Observed elapsed work for this audit was ~2 h wall-clock from the start snapshot, of which the majority was Docker builds and model turns.

---

## 11. Earlier pilots and the study

- **Sonnet→Opus:** 9 tasks calibrated, 0 in band (8 too easy, 1 invalid).
- **Solver pilot:** `qwen/qwen3.7-max` and `z-ai/glm-5.1` solved the same packages 5/5, so the tasks were not hard for any current strong model.
- **Author×solver study** (`docs/study-report.md`, `docs/study-deck.pptx`): a 2×2 of weak/strong authors and solvers. The weak author produced 0 valid tasks of 7, so the trial's own pairing could not be tested; no cell reached the band. Exploratory, never shipped.

---

## 12. Limitations and threats to validity

- **Small N** and a bimodal difficulty distribution; the in-band rate is low.
- **Self-judging:** the author model also judges and red-teams; failures keep the instruction-quote rule, but bias is possible.
- **Reduced novelty scope** (TB 2.1 + examples) is a user decision, not full decontamination.
- **Turn-cap and timeout failures** are invalid by construction (`evaluator/harbor_runner.py`), including turn-cap passes, which can remove otherwise-passing runs from the band.
- **Ledger over-counts** spend; only the key is authoritative.
- **Human-likeness** is below chance but not proven, with dependent pairs.

---

## 13. Reproduction commands

```bash
uv sync
cp .env.example .env            # set OPENROUTER_API_KEY
make tb-reference               # optional; the run uses NOVELTY_SETS=terminal-bench-2-1
bash scripts/validate.sh <task>
uv run --env-file .env harbor run -p <task> -a oracle -k 3 -n 1
uv run --env-file .env harbor run -p <task> -a nop
uv run --env-file .env python -m analysis.report
```

---

## 14. References

The eight papers behind the design are indexed in `docs/research/README.md` (Bercovich 2604.28093; Terminal Wrench 2604.17596; HVTB 2608.22103; CLI-Universe 2606.22883; Meta-Task 2607.27929; Tmax 2606.23321; SkillSynth 2604.25727; Foster & Foerster 2502.12272).

---

## 15. Appendices

- `runs/candidates/README.md` — browsable candidate index.
- `docs/result/evidence/` — frozen inventories, spend snapshots, quality checks, blind experiment, stylometrics, historical data.
- `docs/result/verification.json` — machine-readable audit manifest.
- `docs/model-speedtest.md`, `docs/study-report.md`, `reports/summary.md` — earlier supporting studies.