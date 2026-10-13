# output/ — audited task packages

**A directory here is not a shipped task.** Every package below is a real Terminal-Bench task that
passed the structural validator, the strict quality rubric and the functional gates, and was then
measured against the calibration model. None of them landed in the **1–3 of 5 learnable band**, so
none is marked approved.

| Package | Quality | Gates | Calibration (GPT-5.4-mini) | Status |
|---|---|---|---|---|
| `repair-attributed-funnel-service` | pass, **0 blocking / 0 advice** | oracle 3/3, nop 0 | **5/5** (≈78% over 9 valid trials) | not approved — too easy |
| `optimize-policy-decision-audit` | pass (1 advice) | oracle 3/3, nop 0 | **4/5** | not approved — too easy |
| `repair-reproducible-release-packager` | pass (2 advice) | oracle 3/3, nop 0 | **0/5** | not approved — too hard |
| `repair-log-replay-sql` | pass | oracle 3/3, nop 0 | 5 attempts, 0 valid passes | not approved — too hard |
| `global-settlement-reconciliation` | pass | oracle 3/3, nop 0 | **5/5** | not approved — too easy |

Each directory contains, alongside the task itself:

- **`calibration.json`** — the five-attempt record for that exact package hash: per-trial outcome,
  turn count against the 100-turn cap, the pass audit, the failure label and the **verbatim
  instruction quote** justifying each failure, plus the model pair.
- **`verification.json`** — the gate results for that exact hash, the measured verdict, and
  `why_not_approved`.

`analysis/report.py` derives the approved count only from records that pass
`analysis.package_evidence.approval_errors()` with `status: "passed"`, so listing these packages
cannot inflate the shipped count. `docs/result/verification.json` repeats the same information.

Why nothing is approved: the difficulty lever that produced in-band results was a stated wall-clock
budget, which the quality rubric correctly rejects as an environment-dependent invalid failure mode.
Removing it moved `optimize-policy-decision-audit` from 3/5 to 4/5. See `docs/result/report.md` §7.
