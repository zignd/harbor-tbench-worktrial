# Candidate evidence: luna → GPT-5.4-mini

This index contains the 22 candidate records for `openai/gpt-5.6-luna|openrouter/openai/gpt-5.4-mini`.
A candidate is an attempted task, not necessarily a complete or valid package. Recalibrated copies (`-m`) reuse earlier luna-authored packages; they are not 22 independent fresh generations. Status and package hashes in `evidence-manifest.json` are a snapshot; background work may subsequently change local files.

## Browse the candidates

| Candidate | Task | Recorded status | Instruction exists |
|---|---|---|---|
| [official-1112cdbd9938-m](official-1112cdbd9938-m/) | repair-security-event-index | calibrated | yes |
| [official-371a54d3de9f-m](official-371a54d3de9f-m/) | reconstruct-signed-audit-query | building | yes |
| [official-37d13d3e2124-m](official-37d13d3e2124-m/) | repair-log-replay-sql | calibrated | yes |
| [official-3a04e2577db1-m](official-3a04e2577db1-m/) | accelerate-sqlite-policy-gate | calibrated | yes |
| [official-5b087c5fdff2](official-5b087c5fdff2/) | No accepted blueprint | rejected | no |
| [official-8a671c38fabd](official-8a671c38fabd/) | repair-event-seal-refactor | calibrated | yes |
| [official-9114f040ac4a](official-9114f040ac4a/) | repair-flowwatch-rollups | calibrated | yes |
| [official-936e7746aeaa](official-936e7746aeaa/) | repair-mosaic-statistics-daemon | calibrated | no |
| [official-99d1e913c00d](official-99d1e913c00d/) | deploy-beacon-catalog-service | failed | yes |
| [official-a111d7f89576-m](official-a111d7f89576-m/) | optimize-policy-decision-audit | gated | yes |
| [official-a67391f8734a](official-a67391f8734a/) | repair-modal-stream-auditor | building | yes |
| [official-ac47e792cfa3](official-ac47e792cfa3/) | repair-fill-quality-rollups | building | yes |
| [official-c7bfa2cec6f0](official-c7bfa2cec6f0/) | repair-modal-recovery-daemon | building | yes |
| [official-cd259cd6c51d](official-cd259cd6c51d/) | repair-reproducible-release-packager | gated | yes |
| [official-ce30ab52c4d1-m](official-ce30ab52c4d1-m/) | repair-attributed-funnel-service | failed | yes |
| [official-d19257a8f76d](official-d19257a8f76d/) | reproduce-burst-trace-results | building | yes |
| [official-d2e19ef21fe3](official-d2e19ef21fe3/) | repair-assay-cohort-reproducer | building | yes |
| [official-df18f32a069b-m](official-df18f32a069b-m/) | compile-schema-contract-registry | calibrated | yes |
| [official-e05a846f6234-m](official-e05a846f6234-m/) | repair-event-metric-query | building | yes |
| [official-ea89cb64bf34-m](official-ea89cb64bf34-m/) | repair-segment-replay-service | building | yes |
| [official-ee9176b9c4d1-m](official-ee9176b9c4d1-m/) | repair-wire-event-rollups | building | yes |
| [official-f45203ab22ca](official-f45203ab22ca/) | repair-assay-calibration-reports | building | yes |

## Evidence files

Each directory includes available `spec.json`, `blueprint.json`, `models.json`, gate/quality reviews, `calibration.json`, `status.json`, the current `task/`, and saved attempts. Rejected candidates can lack a task. `runs/ledger.jsonl` is the stage-level history. `reports/summary.md` is the model-labelled aggregate report.

## Generated Git-history fixtures

Nested `.git/` directories cannot be committed as normal files. Their tracked working-tree files are included, and their history is preserved as `.bundle` files beside the candidate metadata. Do not confuse these generated repositories with public source repositories. To restore one, clone its bundle to a temporary directory and copy that clone’s `.git/` into the listed repository; keep the committed working-tree files unchanged. The manifest’s package hash ignores `.git/` metadata.

- `official-8a671c38fabd/task/environment/repository`: history in `official-8a671c38fabd/git-history-task-environment-repository.bundle`.
- `official-a111d7f89576-m/task/environment/repo`: history in `official-a111d7f89576-m/git-history-task-environment-repo.bundle`.
