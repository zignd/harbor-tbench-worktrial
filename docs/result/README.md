# Result deliverables

**Audited revision:** the commit that adds this file. Run `git log -1 --format=%H` to confirm; the same hash is recorded in `docs/result/verification.json` under `revision`.

Two documents plus machine-readable evidence:

- **`report.md`** — the single, self-contained detailed report (requirements matrix, method, audit, verification, stretch goals, costs, limitations, appendices).
- **`presentation.pptx`** — a concise 10–12 slide interview deck with presenter notes.
- **`presentation.html`** — the same deck as an offline HTML file (open in a browser; `←`/`→` to navigate). No server or network needed.
- **`verification.json`** — the machine-readable audit manifest (approved tasks, hashes, checks, spend snapshots). `overall_status` is `passed` only when every check actually passes.
- **`evidence/`** — frozen raw evidence: inventories, spend snapshots, quality checks, the blinded experiment, stylometrics and historical candidate data.

## Rebuild the deck

```bash
uv run python -m docs.result.build_deck_data          # deck_data.json + presentation.html from evidence
NODE_PATH=<pptxgenjs node_modules> node docs/result/build_deck.js   # presentation.pptx
```

## What these documents claim

The report and deck are audited: every count, cost and stretch-goal status traces to a file under `evidence/` or to `reports/summary.md`, and the approved-task table is derived from immutable output records, not from directory names. Unresolved items are labelled partial or not demonstrated rather than skipped.