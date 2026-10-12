# Hand reviews of generated tasks

Side-by-side reviews against `examples/` and the task-quality guideline (Bercovich, arXiv 2604.28093). Each review ends with the generator changes it caused.

## 1. `ledger-reconcile` (Phase 0 spike; Sonnet 4.6 via the meta-task; hand-written blueprint)

Automated gates: structure ✓, lint ✓, leak scan ✓ (no blocking leaks), oracle 3/3, nop 0 (5 of 7 tests fail unsolved), `harbor check` 16/16, novelty ✓ (nearest published task at cosine 0.08). The red-team run, told to cheat, instead solved it honestly **in 94 s**.

| Aspect | vs examples | Finding |
|---|---|---|
| Instruction | Similar to `log-summary-date-ranges` in length and voice (104 words, two paragraphs, no headers or emphasis) | ✅ outcome-focused. ❌ **States the defect's mechanism**: "not an arbitrary charge of the same amount" tells the solver what bug #2 is, and "off by a few cents" points at rounding. This is the guideline's "hidden assumptions" and "hinting" problem. |
| Environment | Larger than the examples (10 files) but **~300 lines** | ❌ Small enough to read in one pass; neither bug needs investigation to locate. |
| Oracle | Like `fix-code-vulnerability`'s direct patch | ⚠️ One token "inspection" (`report \|\| true`), then exact string-replacement patches of the buggy text. That encodes author knowledge (guideline 3.4), and neither the lint nor the rubric caught it. |
| Tests | More thorough than most examples (7 tests vs 1-6) | ✅ fixed-seed data generated at verify time; separate trap and idempotency tests; outcome-based. |
| Dockerfile | As clean as `fix-git`'s | ✅ minimal, no leaks. |

**Prediction:** too easy for Opus (Sonnet solved it in 94 s under hack instructions). Confirmed or refuted by calibration.

**Generator changes (commit after this review):**
1. Blueprint prompt and meta-task rules: state requirements as end states, never as the defect's description (with this task's bad and good phrasing as the example).
2. A realistically sized environment (~800-2,000 lines across components, including uninvolved code), so locating the problem takes investigation.
3. Oracle rule: reproduce, then apply a fix justified by the evidence, preferring robust rewrites over exact-string patches.
