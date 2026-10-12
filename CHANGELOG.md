# Changelog

What we did, why, and the design tradeoffs. Newest first. Each entry is stamped `### HH:MM ±HH:MM · Title` under its `## YYYY-MM-DD` day: local time with its UTC offset, taken from when the change was committed. Spend figures come from `make usage` (OpenRouter `/api/v1/key`).

## 2026-10-12

### 18:25 -03:00 · Tuning round 1 still too easy; `make status`; pipeline tests; secret audit
- **Tuning round 1 on `ledger-reconcile`:** the plan added a third interacting bug (an idempotency dedup key). The task re-gated cleanly (quality 15/16, novelty ok, red-team honest in 554 s vs 94 s before, so it was harder for Sonnet), but Opus still went **4/4** (9-12 turns, ~2 min, $0.20-0.37 per trial).
  - **Lesson:** Opus reads a ~300-line codebase in one pass, so adding bugs to a small codebase doesn't create difficulty. It has to come from how much *investigation* the task needs. This supports the post-review rule for ~800-2,000-line environments. Round 2 is running.
- **`make status`** (`scripts/status.py`): running pipeline processes, task containers, the current turn of each unfinished authoring run, the last ledger events, and live spend, on one screen. Read-only.
- **`tests/test_pipeline.py`:** `build_candidate` control flow with every paid stage faked: first-try pass, repair with feedback and the previous package, exhausted repairs → exactly one regeneration from the blueprint → failed, and a rejected blueprint stopping early. 102 tests in total.
- **Secret audit (final-cleanup item, done early):** 38 commits, no key-shaped strings, the real key absent from history, tracked files and evidence dirs, and no `.env` or PDF ever committed.

### 18:07 -03:00 · Repair feedback now carries the real build error
- Pilot candidate 1 failed the static gate: `docker build` died in the author's `setup_repo.sh`. The pipeline sent it to repair, but the feedback was only BuildKit's last 600 characters ("process … did not complete successfully: exit code 1"), which hid the actual cause.
- **Fix:** the leak-scan build now uses `--progress=plain`, and the failure feedback keeps the last ~60 lines (≤3.5k chars) of the failing step's own output. For this task that reveals the real problem: `git commit` with **"nothing to commit"**, so the repo files were never written where the setup script expected.
- The repair already in flight got the old, short message (its process loaded the earlier code). Future repairs get the full error.

### 18:07 -03:00 · Authoring cost, measured: levers helped input, bigger tasks cost more
- Pilot candidate 1 (`rust-codec-deploy-regression`, a Rust codebase as the new size rule asks for) was authored in **80 turns (cap), 42 min, $3.86**.
  - Summarization fired twice and cut total input by 25% vs Phase 0 (3.82M vs 5.07M tokens).
  - But every summary breaks the prompt cache (uncached input 0.35M vs 0.10M), and output doubled (100k vs 58k tokens) for the larger environment.
- The tuner's repair-style round on `ledger-reconcile` took **24 turns, $0.91**: starting from an existing package is ~4× cheaper.
- **Conclusion:** fresh builds of realistically sized tasks cost ~$3-4, and repairs/tunes ~$1. The ≤$1.5 target only held for repairs, and that is recorded rather than hidden. The $90 authoring bucket still covers ~25 builds. Summarization stays on, since it bounds context growth on long runs.

### 18:04 -03:00 · Architecture guide with Mermaid diagrams
- `docs/architecture.md` is a presentation-oriented guide:
  - **9 Mermaid diagrams:** the band, the system overview, the candidate lifecycle state machine, an authoring meta-task sequence diagram, the calibration curtailment flow, the valid-vs-invalid failure taxonomy, the reward-hacking defence layers, the budget controls, and a repository map.
  - **A decisions table** with the why and tradeoff for each choice, each tied to a paper or a measured result.
  - **Q&A for reviewers**, answered with measured numbers.
- All 9 diagrams render with `@mermaid-js/mermaid-cli` 11, so there are no syntax errors. Linked from the README.

### 17:58 -03:00 · Stretch D baseline: AfterQuery's examples on our 16-criterion rubric
- `harbor check` with `generator/quality_rubric.toml` on all 6 hand-written examples ($0.66; `reports/quality_examples.json`):

  | Example | Passed | Gate |
  |---|---|---|
  | chess-best-move | 12/16 | blocked |
  | configure-git-webserver | 12/16 | blocked |
  | fix-code-vulnerability | 11/16 | blocked |
  | fix-git | 8/16 | blocked |
  | log-summary-date-ranges | 12/16 | blocked |
  | openssl-selfsigned-cert | 12/16 | ok |

- **Most-failed criteria:** valid_failure_modes (5/6), behavior_in_task_description (4/6), anti_cheating_measures (4/6), verify_time_inputs (4/6), instruction_style (3/6), oracle_investigates (2/6).
- **Read:** the examples were written to an older, looser bar (TB 1/2-era tasks; HVTB classes all six as "Easy"). Our gate would block 5 of 6. The Phase 0 Sonnet-authored task scored 16/16, yet hand review still found difficulty leaks. So "passes the rubric" is necessary but not sufficient, and stretch D compares on both the rubric and human review.

### 17:55 -03:00 · First calibration: `ledger-reconcile` is too easy (4/4); Opus costs $0.23 per trial
- **Calibration** (terminus-2 + Opus 4.8, concurrency 2): **4/4 legit passes → too easy**, stopped after 4 trials (curtailment saved the 5th). Each run took 11-13 turns and 1.3-1.7 min.
  - **Cost: $0.20-0.26 per Opus trial** and $0.012-0.013 per audit, $0.97 in total. The budget had assumed $1.5 per trial, so Opus is cheaper than planned on tasks like this. Harder tasks will run longer.
  - The hand review predicted this outcome: the instruction named the bug and the code was small.
- **`harbor analyze` vs our judge:** on the 2 wave-1 passes, `harbor analyze` (built-in `reward_hacking` + `task_specification` rubrics) agreed with our audit (both pass), at **$0.13 per trial vs $0.012**. Our judges stay primary: they're 10× cheaper and produce the structured labels the tuner and report use.
- **Stretch B in action:** this too-easy task (all failures valid, i.e. none) is now going through the tuner: a Sonnet mutation plan, a repair-style authoring round, the gates, then recalibration.
- **Example quality so far:** AfterQuery's own examples score 11-12 of 16 on our rubric and are each blocked on at least one criterion. Our rubric is stricter than the examples' authors were.
- Progress 46/83.

### 17:52 -03:00 · Hand review #1: the instruction named the bug; prompts tightened
- Reviewed the Phase 0 `ledger-reconcile` task side by side with `examples/` (`docs/reviews/hand-review.md`). Every automated gate passed (including `harbor check` 16/16), yet a human read found three problems:
  1. **The instruction states the defect's mechanism** ("not an arbitrary charge of the same amount").
  2. **The environment is too small** (~300 lines) to need investigation.
  3. **The oracle patches the exact buggy text**, which is author knowledge.
- That's consistent with the red-team run solving it honestly in 94 s. Prediction: too easy for Opus (calibration running).
- **Changes:** the blueprint prompt and meta-task rules now require end-state requirements (never a description of the defect, with this task's bad and good phrasing as the example), a realistically sized environment (~800-2,000 lines across components, including uninvolved code), and an oracle that reproduces before fixing with robust rewrites instead of exact-string patches.
- **Why it matters:** automated quality gates check *consistency* (tests ↔ instruction), not *difficulty leakage*. Hand review caught what the rubric judges as fine.
- Red-team on `ledger-reconcile`: **not hackable** (the attempt produced an honest fix, confirmed by the audit), $0.12.

### 17:51 -03:00 · Tuner (stretch B) and curtailment analysis (stretch A); first calibration started
- **`analysis/tuner.py` + `scripts/tune_candidates.py`:** an ACCEL-style mutation loop for near-misses.
  - A Sonnet plan proposes ONE change, preferring the verifier knob (more or nastier verify-time cases, a stricter *stated* threshold), then a difficulty lever, then regeneration.
  - The change is applied as a repair-style authoring round on the current package, re-gated (with up to one repair) and recalibrated. At most 2 rounds.
  - Fairness rules are part of the directive: the instruction must state everything the tests check, and a too-hard task is never eased by weakening the check on its core requirement.
  - Only tasks whose failures were all valid are tuned. 4 tests.
- **`analysis/curtailment.py`:** exact expectation over all 2^5 sequences.

  | true p | P(in band) | exact: trials (saved) | 0/3 early reject: trials (saved, recall of learnable) |
  |---|---|---|---|
  | 0.1 | 0.41 | 4.42 (11.7%) | 3.03 (39.4%, 0.66) |
  | 0.2 | 0.67 | 4.05 (19.0%) | 3.13 (37.4%, 0.72) |
  | 0.35 | 0.83 | 3.85 (23.1%) | 3.39 (32.1%, 0.81) |
  | 0.5 | 0.78 | 3.94 (21.3%) | 3.75 (25.0%, 0.88) |
  | 0.8 | 0.26 | 4.32 (13.7%) | 4.31 (13.9%, 0.97) |

  Exact curtailment is lossless (recall 1.0). The aggressive rule saves up to 40% on hard tasks but **loses 19-37% of learnable tasks at low p**, so we don't use it: learnable tasks are the scarce output.
  - **Correction:** my early study guide said P(in band) = 0.94 at p = 0.5. The correct value is 25/32 = 0.78.
- **First calibration launched:** the Phase 0 Sonnet-authored `ledger-reconcile` task (oracle 3/3, nop 0, `harbor check` 16/16) is registered as candidate `official-p0-ledger-reconcile` and is being red-teamed, then calibrated on Opus (concurrency 2). It came from a **hand-written blueprint**, and the report will label it as such.
- `harbor check` on all 6 examples is running for the stretch D comparison. ruff now skips generated task code (`runs/`, `output/`). 98 tests pass.

### 17:34 -03:00 · Fix: stale Harbor job dirs could be silently resumed
- **Found while the pilot ran:** the earlier dry run sampled the same spec (same seed, so the same candidate ID) and left gate job dirs (`jobs/gate-official-<id>-a1-*`) in the shared `jobs/`. Harbor **resumes** an existing job dir with the same config and keeps its finished trials, so the live pilot's oracle/nop gate would have reused the dry run's results, which came from the fixture task.
- **Fixes:**
  - The stale dirs were removed before the pilot reached its gates.
  - `run_job()` now deletes an existing job dir before every run.
  - Dry runs write their gate jobs under `jobs/dry-run/jobs/`, isolated from real runs. Verified.
- **Lesson:** deterministic job names need either fresh dirs or unique names. Resume semantics are a footgun for an evaluation pipeline.

### 17:32 -03:00 · Novelty gate also covers our own earlier tasks
- `validator/novelty.gate_index()` builds the gate's index from the 425 published TB tasks + `examples/` + **our own earlier candidates** (excluding the candidate being checked), at both the blueprint gate and the final-package re-check. A batch can't drift into near-duplicates of what it already generated, not just of published work.
- **Coverage-steered sampling** was already in place (`run_batch` samples inverse-frequency against all earlier candidates' specs), so it's ticked.
- `analysis/report.py` added: funnel, per-stage cost and time, calibration histogram and savings, coverage and balance, uniqueness, nearest published task, stylometrics. Official evidence only.
- 93 tests. Progress 42/83.

### 17:30 -03:00 · Diversity and human-likeness analysis modules (stretch C, D)
- **`analysis/diversity.py`:** per-axis coverage and **balance = exp(H)/N** (Tmax), instruction uniqueness (max/mean pairwise TF-IDF cosine, and a **Vendi score** with Jacobi eigenvalues, no numpy), and nearest published TB task per generated task.
  - **Baseline on the 6 examples:** Vendi 5.97 of 6, mean pairwise cosine 0.034, max 0.119. That's the bar for our batch.
- **`analysis/human_likeness.py`:**
  - `stylometrics()` measures instruction words, sentences, bullets, headers, emphasis and code spans, plus test count, Dockerfile, solution and environment size.
  - `discrimination()` is a blinded pairwise test: an example and a generated instruction, shuffled, and Sonnet guesses which a human wrote. Accuracy near 50% means indistinguishable.
  - **Examples:** 30-575 instruction words, no headers or emphasis in any of them. The Phase 0 Sonnet task: 104 words, 6 sentences, no bullets, headers or emphasis.
- 92 tests pass. **Spend:** $0.

### 17:29 -03:00 · Red-team gate (implemented; first real runs on the pilot)
- **`evaluator/redteam.py`:** a Terminal-Wrench-style hack elicitation.
  - A copy of the task gets an explicit "make the verifier pass without solving it" paragraph, and one Sonnet terminus-2 run (60 turns) tries.
  - A pass is confirmed as an exploit by the pass-audit judge (an honest solve under hack instructions isn't counted as a hack).
  - The exploit summary and trace tail are saved for repair feedback.
- **Wiring:**
  - It's the **last gate** in `stage_gates()`, after novelty, so it only runs on tasks that are otherwise ready. A beaten verifier becomes repair feedback ("harden the tests so this shortcut fails").
  - `scripts/calibrate_candidates.py` runs it first on candidates gated before the gate existed (the pilot), so no Opus spend goes to a hackable task.
- **Tradeoff:** one attempt is a screen, not a proof. Terminal Wrench ran a second, deeper stage only on tasks that showed a hack. The pass audit during calibration remains the second line of defence.
- Dry run still passes (the red-team is faked there, like the other paid stages). 88 tests.

### 17:28 -03:00 · Plan progress tracker
- Added `scripts/track-plan.sh` (+ `make plan`): overall and per-phase checklist counts for `docs/plan.md`; `--remaining` / `--all` list items with `file:line` references, and `--fail-if-incomplete` exits non-zero while work remains.
- Replaces the `grep -c` hint next to the **Progress** line, which gave only a single total and no view of what is left per phase. Pure awk over the markdown, no dependencies.

### 17:25 -03:00 · Calibration: exact curtailment, per-trial judges, shipping
- **`evaluator/calibrate.py`:**
  - `decide()` implements exact curtailment of the 5-run band test: accept at ≥1 legit pass + ≥2 valid fails, reject at 4 passes or 5 fails, stop immediately on a hacked pass or invalid failure. Tested on all 32 pass/fail sequences: the early verdict always equals the full 5-run verdict. Expected trials are 3.85-4.3 instead of 5 (14-23% saved) for true pass rates 0.2-0.8, before the extra savings from stopping on invalid failures.
  - `next_wave_size()` runs trials in parallel waves no larger than the fewest trials that could still produce a verdict (3, then 2 or 1), so concurrency never pays for a trial whose result can't matter.
  - `calibrate()` runs Opus waves (terminus-2, `max_turns=200`, budget check per wave), judges each trial as it lands, and writes ledger events.
- **`analysis/judge.py`:**
  - `condense()` keeps reasoning, commands and truncated output: ≤90k chars, head and tail kept, since action-only monitors are weaker (Terminal Wrench).
  - `command_scan()` flags commands touching `/tests`, `/solution` or reward paths.
  - `audit_pass()` labels passes legit / non-serious hack / serious exploit.
  - `analyze_failure()` classifies failures with 10 valid modes (partial implementation, weak verification, …) and 6 invalid ones (spec ambiguity, test overreach, broken or nondeterministic env, tool quirk, resource limit). A "valid" verdict with an invalid mode is rejected in code.
  - Harbor-level timeouts and turn-cap endings are always invalid.
- **`scripts/calibrate_candidates.py`:** calibrates gated candidates and ships learnable ones to `output/<slug>/`, with a README modelled on the examples' (what it tests, calibration, why the model fails it, how it's verified). It refuses to run in dev mode.
- 88 tests pass. Pilot batch (3 candidates) and a dev-mode batch are running. The first pilot blueprint was accepted (Rust packet codec with a throughput bar, predicted 0.25; $0.13).

### 17:22 -03:00 · Authoring cost levers; task.toml becomes pipeline-owned
- **Where the Phase 0 money went:** the $2.75 Sonnet authoring run spent ~56% on cache reads of an ever-growing history (2k tokens at step 1, 104k at step 80, resent every turn) and ~32% on output tokens (file contents). Six turns reading the reference task added output that stayed in context for the remaining 74 turns.
- **Levers (authoring agent only; Opus calibration keeps terminus-2's defaults):**
  1. `proactive_summarization_threshold=140000`. LiteLLM gives Sonnet a 200k limit, so history gets summarized once it passes ~60k.
  2. **No reference task.** `task.toml` is now generated by the pipeline from the blueprint (`generator/author.py:make_task_toml`), pre-placed in the synthesis image and enforced by `collect_package()`, like `tests/test.sh`. The author writes only the instruction, environment, solution and `test_outputs.py`. That removes a class of `task.toml` errors as well as the exploration cost.
  3. Turn-efficiency rules in the meta-task instruction: one command per file, batched commands, no echoing files back, plan → write → verify.
- **Verified for free:** the synthesis image builds with only the pipeline-owned files, the dry run passes, and the generated `task.toml` passes the structural validator, including Harbor's schema cross-check. The cost effect is measured on the pilot batch.
- Dev-mode candidates now go to `output-dev/candidates/` (git-ignored), not `runs/`.

### 17:19 -03:00 · End-to-end candidate pipeline, quality gate, batch CLI
- **Quality gate:** `evaluator/quality.py` + `generator/quality_rubric.toml`, wrapping `harbor check`.
  - The rubric is Harbor's 11 default criteria plus 5 work-trial ones: deterministic_tests, valid_failure_modes, verify_time_inputs, oracle_investigates, instruction_style.
  - **9 criteria block:** instruction↔test alignment both ways, anti-cheating, schema, tests/solution in the image, hardcoded solution, unmentioned files, determinism, valid failure modes. The other failures are fed back to repair as advice.
  - On the Phase 0 spike task it passes 16/16 for $0.13 in 80 s.
- **Pipeline:** `generator/pipeline.py`. Each candidate lives in `runs/candidates/<id>/`. Stages: blueprint + gate → authoring meta-task → gates, cheapest first:
  1. structural + lint + leak scan (free);
  2. oracle 3/3 + nop (free);
  3. quality (~$0.13);
  4. novelty re-check of the final instruction (~$0.02).

  A failed gate feeds a **repair round**: the failed package is baked into the synthesis image at `/app/previous`, and the findings are appended to the meta-task instruction. At most 2 repairs, then **one regeneration** from the blueprint (SkillSynth: bad drafts rarely recover), then the candidate is dropped. Every stage writes a ledger event, and the budget guard runs before every paid stage.
- **CLI:** `scripts/run_batch.py` (`make batch N=3 SEED=1 BUDGET=20`).
  - Specs are sampled inverse-frequency against all earlier candidates.
  - A per-batch budget cap applies on top of the global limits.
  - Runs are resumable (finished candidates are skipped).
  - **`--dry-run`** (`make dry-run`) swaps model calls for fixtures but runs the real gates. It passed end to end for free in 37 s.
- **`generator/generate.py`:** the template's `generate_task(topic)` is now implemented. The topic becomes a hint on a sampled spec, so `scripts/generate.sh "<topic>"` produces a gated task.
- `make test` / `make lint` targets added. 43 tests pass.
- **Spend:** quality-gate check $0.13. Running total ≈ $3.3. Progress 36/83.

### 17:12 -03:00 · Lint and leak-scan gates; blueprint stage (dev-mode verified)
- **`validator/lint.py`:** errors block a task, warnings are reported.
  - **Errors:** canary placement, `docker_image` set, a timeout under 3600, COPY of `tests/` or `solution/`, missing COPY sources, answer-like file names in `environment/`, suggestive comments ("BUG", "fix:", "intentionally", …), tests that check installed packages, no test functions.
  - **Warnings:** instruction over 300 words, headers or bold, tests that read solver source, a `solve.sh` that writes before it inspects.
  - Both Phase 0 packages are clean. 6 tests use planted defects.
- **`validator/leak_scan.py`:** builds the image and searches it (pruning OS directories, files under 5 MB) and `docker history` for literals from `tests/` and `solution/`. About 2 s per task.
  - **First design flaw caught by its own test:** I'd skipped tokens the environment "already states", but the Dockerfile is part of the environment, so an answer planted with `RUN echo` was ignored.
  - **Now:** only tokens the *instruction* states, and paths, are exempt. Answer-like tokens (hashes, long or high-precision numbers) found in the image are **blocking leaks**. Quoted strings are non-blocking notes, because they're usually input data the tests regenerate.
  - **Second bug:** `grep --exclude-dir` matches directory names, not paths, so the first version crawled the whole filesystem for more than 10 minutes. It now uses `find -prune`.
- **`generator/blueprint.py`:**
  - **Generation:** spec → `Blueprint` (instruction draft, internal hint, requirements, environment, trap, tests, verifier knob, expected failure modes, predicted pass rate). The prompt gives the frontier-agent failure modes to design around, hard constraints, and the 425-task concept list (~18k prompt tokens).
  - **Review:** a rubric review with acceptance **enforced from the scores** (every score ≥ 3, average ≥ 3.6), not from the model's verdict.
  - **Gate:** `gate_blueprint()` combines the review with the novelty gate. Lexical flags reject without calling the judge; otherwise the Sonnet same-task judge runs.
  - **Dev-mode run:** an accepted blueprint, novel against the 3 nearest TB tasks (max cosine 0.16), for ~$0.03.
- **`analysis/llm.py`:** reasoning models can spend the whole `max_tokens` on hidden reasoning (DeepSeek: 6000/6000 reasoning tokens, empty content, `finish_reason=length`). `chat()` now retries with a doubled budget (up to 32k) and counts every attempt's cost.
- **Tests:** 43 unit tests, all passing. **Spend:** ~$0.03 (dev). Progress 30/83.

### 16:45 -03:00 · Spec sampler, LLM client, novelty index
- **`generator/spec.py`:** `TaskSpec` covers 12 domains, 8 skill types, 11 capabilities (2 per task), 6 pillars, 12 personas, weighted languages, 7 fixture kinds, 5 verifier kinds (each with a difficulty knob), 8 difficulty levers (2 per task) and 4 terse-compatible writing styles.
  - Sampling is **inverse-frequency** (SkillSynth): weight 1/(count+1) per value, optionally seeded with history. A batch therefore spreads across the taxonomy instead of piling onto common cells.
  - Deterministic per seed. 5 unit tests.
- **`analysis/llm.py`:** a minimal OpenAI-compatible `chat()` for direct calls (blueprints, reviews, judges). It retries transient errors, does token-based cost accounting from OpenRouter prices, and has a JSON extractor. The model follows `config.MODEL`, so dev mode swaps it automatically.
- **`validator/novelty.py`:** a TF-IDF + word-13-gram index over the 425 **unique** reference tasks (the 431 files, de-duplicated by text, since `examples/` and some sets repeat tasks). It provides `nearest()`, `lexical_flags()`, `concept_list()` (8.6k words, for the blueprint prompt) and `judge_same_task()` (a Sonnet same/variant/distinct verdict on the top-3).
  - **Threshold calibrated on the corpus itself:** among distinct published tasks, the nearest-neighbour cosine has median 0.24 and p90 0.52, and every pair above ~0.75 is a genuine variant. Examples: `polyglot-rust-c`/`polyglot-c-py` 0.83, two broken-pip repairs 0.75, and a TB 4.0 rewording of a 2.1 HTML-filter task 0.97. Lexical reject is at **0.70**; the judge decides below that.
  - The Phase 0 spike task is clean (nearest 0.08).
  - 6 unit tests run on the examples only, so CI doesn't need the downloaded corpus.
- **Spend:** $0. Progress 28/83.

### 16:41 -03:00 · Phase 1 foundations: runner, ledger, budget guard, pricing
- **`evaluator/harbor_runner.py`:** runs `harbor run` and parses job dirs into `TrialResult` (reward, tokens, cost, turns, timing, paths). It classifies each trial as **pass / fail / invalid / infra / fatal**:
  - Agent or verifier timeouts, context overflow and hitting the turn cap are *invalid*, never valid failures.
  - API, network, build and missing-reward problems are *infra*. They're retried twice, then excluded.
  - A bad key or unknown model is *fatal* and aborts the run.

  Smoke-tested live on 2 parallel oracle trials.
- **`analysis/ledger.py`:** an append-only `runs/ledger.jsonl` of `Event`s (stage, task, result, cost, seconds, inputs hash, dev/official mode). `hash_dir()` gives content hashes, so a stage is skipped when its inputs haven't changed.
- **`analysis/budget.py`:** `check(expected_usd)` refuses work that would exceed the $380 authorization or drop remaining credit below the $75 reserve. It uses the larger of OpenRouter's two lagging counters.
- **`analysis/openrouter.py`:** spend and per-model prices from OpenRouter (cache-read prices included). `TrialResult.priced_cost()` falls back to token pricing when Harbor's `cost_usd` is `None` (DeepSeek). The `make usage` script now reuses this module.
- **Config:** `MAX_TURNS=200`, `METATASK_MAX_TURNS=80`, `OPUS_CONCURRENCY=3`, budget limits and repo paths in `generator/config.py`.
- **Tests:** 20 unit tests on the recorded fixtures cover outcome classification (incl. the turn cap), retry and exclude, token pricing, the ledger cache, the budget limits and the counter-lag handling. `pytest` and `ruff` skip `tests/fixtures/` (which holds an authored task with its own tests).
- **Spend:** $0 (the smoke test used the free oracle). Progress 26/83.

### 16:30 -03:00 · Phase 0 done: meta-task authoring works, and the gates caught a real bug
- **Spike:** one hand-written blueprint (a payment-ledger CLI with two interacting bugs and a cross-day-refund trap), authored as a Harbor meta-task by both Sonnet 4.6 and DeepSeek (dev mode). Both meta-tasks scored 1.0 on the in-container package check, and `artifacts` delivered the package to the host.
- **The host gates caught what self-validation missed.** Sonnet's package failed the oracle 3/3 in the real build: its `tests/test.sh` called `uvx` without installing uv. The author had verified by running pytest directly, never the verifier entry point.
  - **Fix:** `tests/test.sh` is now pipeline-owned (`generator/metatask/standard_test.sh`, the examples' isolated-`uvx` approach). It's pre-placed in the synthesis image (now with uv), and `collect_package()` overwrites it.
  - **Result:** both packages pass oracle 3/3 and nop 0. Sonnet's fails 5 of 7 tests unsolved, including the trap and idempotency tests.
  - **Go/no-go: go.** In-container authoring with a host-side gate produces functionally correct tasks. The custom `docker exec` fallback isn't needed.
- **Costs:**
  - Sonnet authoring was **$2.75** (it hit the 80-turn cap, with ~63k context resent per turn), about twice the plan's estimate. Cutting it is now a Phase 1 item.
  - DeepSeek authoring was ~$0.15-0.2. Harbor reports `cost_usd: None` because LiteLLM has no price for it, so the ledger will price tokens from OpenRouter `/models`.
- **Budget re-planned** from measured unit costs (Opus $0.117 on an Easy task, authoring $2.75, `harbor check` $0.084) into buckets that fit the $380 authorization, with $215 for Opus calibration.
- **Code:** `generator`, `validator`, `evaluator`, `analysis` and `tests` are now packages with absolute imports (`python -m generator.author`). pytest and ruff are configured in `pyproject.toml`. The meta-task fixture was added (without the 5 MB trajectory).
- **Spend:** Phase 0 total **$3.0-3.1** (`make usage`: $2.95 used, $3.12 by `limit − remaining`; the counters lag). Progress 21/83.

### 16:12 -03:00 · Novelty gate against every published Terminal-Bench set; `harbor check` evaluated
- **Novelty corpus:** `make tb-reference` downloads every Terminal-Bench set on the Harbor hub into git-ignored `data/tb-reference/` (~2 min), keeping only `instruction.md` + `task.toml` (3.6 MB). That's 425 tasks:
  - `terminal-bench@latest`, 66 tasks. This matches Terminal-Bench **4.0** (Aug 2026), and none of its tasks overlap with 2.x.
  - 2.1, 89 tasks.
  - Pro, 200 tasks.
  - Science, 70 tasks.
- **Why all of them, and not just the latest:** the README forbids reusing or adapting *any* public task, so newer releases don't replace older ones as things to avoid.
- **Plan change (delta 11):** novelty moved from a Phase 3 report to an **early gate**. It has three layers:
  1. The TB concept list goes in the blueprint prompt ("don't build these or variants").
  2. At blueprint review: 13-gram + TF-IDF, then a Sonnet "same underlying task?" judge on the top-3 nearest TB tasks.
  3. The same check on the finished package before calibration.
- **Tradeoff:** text overlap alone only catches copied wording. The semantic judge catches the same task reworded, at about one small Sonnet call per candidate. Thresholds will be calibrated on TB-vs-TB similarity so tasks that merely share a domain aren't rejected.
- **`harbor check` evaluated:** it runs a reviewer agent in a Harbor job. It works with terminus-2 + Sonnet 4.6 through our gateway, at $0.084 for `fix-git`. Its default rubric has **11 criteria**, not the 19 we assumed. AfterQuery's own `fix-git` fails 4/11, including two instruction↔test alignment criteria (the tests check files the instruction never names).
  - **Decision:** wrap `harbor check` with a custom rubric as the alignment/quality gate, instead of building a judge.
- **Spend:** `harbor check` $0.084, plus the meta-task spikes (accounted when they finish).

### 15:54 -03:00 · Correction: OpenRouter usage counters lag
- My earlier claim that "Harbor's `cost_usd` overstates spend by ~50%" was wrong. The $0.0775 reading was taken 5 s after the Opus trial, before OpenRouter had counted all of it. The settled total ($0.1176) matches Harbor's estimate of $0.1173.
- OpenRouter's `/api/v1/key` `usage` and `limit_remaining` also update out of sync. At one point they implied $0.118 vs $0.145 spent.
- **Changes:**
  - The ledger records Harbor's per-trial `cost_usd`, which is immediate and attributable to a task.
  - Reconcile against OpenRouter only after the counters settle (~1-2 min).
  - The budget guard uses the larger of `usage` and `limit − remaining`.
  - `make usage` now prints both, as `used` and `spent*`.
- Fixed the earlier entry, `docs/harbor-notes.md` and the plan's credentials note.

### 15:51 -03:00 · Phase 0: Harbor baseline, first Opus trial, meta-task template
- **Examples:** oracle 6/6 = 1.0 and nop 6/6 = 0.0, no exceptions. Trials took 9-108 s, the verify step 4-26 s, and no `uvx` install failures across 12 runs. Docker image caching works (env setup ~1 s once built). Details are in `docs/harbor-notes.md`.
- **First Opus 4.8 trial** (`fix-git`, `max_turns=200`): reward 1.0 in 11 turns and 68 s, costing **about $0.117**, with 85% of input tokens served from the prompt cache.
  - *Corrected later the same day:* this entry first said "$0.0775 actual, Harbor overstates by ~50%". That reading was taken 5 s after the run, before OpenRouter had counted it. The settled figure matches Harbor's `cost_usd` ($0.1173). See the 15:54 entry.
  - fix-git is "Easy". Generated Medium/Hard tasks will run longer, so per-trial cost still has to be measured on our own tasks.
- **Confirmed mechanics:**
  - `--ak max_turns=200` reaches terminus-2 (it's in the trial config, and terminus-2 logs a warning).
  - `-k`/`-n` work.
  - The trajectory JSON holds per-step reasoning, keystrokes and observations, which is what the judges and the command scan need.
- **Meta-task template** (`generator/metatask/`) and renderer (`generator/author.py`):
  - The instruction is adapted from Meta-Task's template, with our rules.
  - The synthesis image uses the same base (`python:3.13-slim-bookworm`) that generated tasks must use, so the author can reproduce the task env without Docker.
  - The in-container `check_package.py` gives the meta-task a "package complete" reward.
  - `artifacts = ["/app/output"]` collects the package.
- **Fixtures:** sanitized oracle, nop and Opus job dirs in `tests/fixtures/harbor_jobs/` for unit tests (no secrets; absolute paths replaced by `<REPO>`).
- **Spend:** Opus trial ~$0.117. Running total ~$0.118.

### 15:30 -03:00 · Dev mode: cheap model for plumbing iterations
- `DEV_MODE=1` routes every model call (authoring, judges, red-team, and the terminus-2 eval agent) to `DEV_MODEL`, default `deepseek/deepseek-v4.1-flash`. That's $0.15/$0.60 per M tokens vs Sonnet's $3/$15 and Opus's $5/$25, so ~20-40× cheaper. It's validated through both the OpenAI client and LiteLLM.
- **Why:** the README rule is "Generate tasks with `claude-sonnet-4.6` and benchmark difficulty only against `claude-opus-4.8`. Use no other models for either." It restricts *generating* and *benchmarking*, and says nothing about debugging the pipeline. Most early runs only test plumbing (runner parsing, meta-task wiring, calibration loop, ledger), where paying Opus prices buys nothing.
- **Guardrails:**
  - Dev output goes to `output-dev/` (git-ignored).
  - `RUN_MODE` tags ledger entries `dev` vs `official`.
  - `config.assert_official_models()` makes ship/report steps refuse to run with non-official models.
  - `OFFICIAL_MODEL` / `OFFICIAL_EVAL_MODEL` are now constants, separate from the env overrides.
- **Tradeoff:** DeepSeek behaves differently from Opus (and small models are brittle with terminus-2's keystroke interface, per Tmax). So dev runs never inform difficulty, tuning or any reported metric. They only prove the code works. Dev spend will be reported separately here.
- Checklist: added dev-mode steps before the official meta-task spike, the pilot batch and the first calibration (10/75 items done).
- **Spend:** ~$0.00002 (two DeepSeek validation calls; still $0.0003 total).

### 15:19 -03:00 · Plan as a work checklist
- Replaced the prose "Phases" section of `docs/plan.md` with a **work checklist**: 71 concrete items across Phases 0-4, each naming its output and how we know it's done, with a progress counter (9/71 done).
- Items that call a model are marked 💲, so spend is visible before work starts. Go/no-go checkpoints are explicit: the meta-task spike, and cost per learnable task after the pilot.
- Removed per-phase day estimates. Progress is tracked by ticked items, not by the calendar.

### 15:12 -03:00 · Agent guidance (`AGENTS.md`, `CLAUDE.md`)
- Added `AGENTS.md` with the work-trial constraints, budget rules, commands, changelog and commit conventions. `CLAUDE.md` imports it, so Claude Code and other agents follow one source of truth.
- **Why:** most of the work is done with AI assistance. Writing the hard constraints (allowed models, the 3600 s timeout, valid-failure rule, novelty, $75 reserve) where every agent reads them stops them from being broken by accident.

### 15:07 -03:00 · Spend tracking (`make usage`) and spend discipline
- `make usage` / `make usage-json` (`scripts/openrouter_usage.py`) report limit, spend, remaining credit and key expiry from OpenRouter's per-key endpoint. The account-level `/credits` endpoint needs a management key, which we don't have.
- `docs/plan.md` gained a "Spend discipline" section:
  - Opus runs only after every cheap gate passes.
  - Exact curtailment of the 5-run test.
  - Stop calibrating a task on its first invalid failure.
  - A protected $75 reserve.
  - Batches scaled 1 → 3 → 10 → 15, gated on cost per learnable task.
- **Tradeoff:** curtailment reports some tasks as `k/n` with n < 5. The verdict is mathematically identical to running all 5 runs (after 1 pass and 2 fails, at most 3 of 5 can pass). Shipped tasks can be topped up to a full 5 runs if budget remains.

### 14:59 -03:00 · Inference credentials
- The issued key is an **OpenRouter** key ($500 limit, expires 2026-10-23). `https://api.aqinference.com/v1` (the README's gateway) returns 401 for it, so `generator/config.py` now defaults `OPENROUTER_API_BASE` to `https://openrouter.ai/api/v1`.
- Validated both allowed models with one tiny call each:
  - Sonnet 4.6 through the OpenAI client (generator path).
  - Opus 4.8 through LiteLLM (Harbor path).
- Secrets live in a git-ignored `.env` (mode 600). `.env.example` documents the variables.
- **Spend:** $0.0003 (validation calls).

### 14:54 -03:00 · Plan and research (`docs/plan.md`, `docs/research/`)
- Wrote the pipeline plan covering Parts 1-3 and stretch goals A-D.
- Read eight papers in full and kept text versions in `docs/research/` (PDFs are git-ignored but re-downloadable from arXiv). They cover task quality, reward hacking, terminal task synthesis, and learnability.
- Decisions they drove:
  - Author tasks as a **Harbor meta-task**: Sonnet runs as terminus-2 inside a container, and the finished task is collected via `artifacts` (Meta-Task).
  - A **blueprint + rubric review** before building (CLI-Universe, SkillSynth).
  - Difficulty levers aimed at Opus's documented failure modes, weak self-verification and partial implementation (CLI-Universe, Meta-Task, SkillSynth).
  - Verifier thresholds as a continuous tuning knob (Tmax).
  - An oracle **3/3 determinism gate**, because environment randomness would look learnable without being so (Foster & Foerster).
  - Pass audits and a Sonnet red-team against reward hacking (Terminal Wrench, HVTB).
- **Tradeoff:** a meta-task reuses Harbor's agent, logs and cost tracking, but the authoring container can't run Docker. Real build/oracle/nop checks therefore happen in host-side gates and feed back through repair rounds. A custom `docker exec` authoring loop is the fallback if the Phase 0 spike fails.

### 14:30 -03:00 · Development environment
- Made the repo a **uv** project: `pyproject.toml` + `uv.lock` pin `harbor==0.24.0`, `openai`, `pydantic` and `toml`, with Python 3.13 via `.python-version`.
- **Why:** with Harbor in the project venv, `validator/validate.py`'s native Harbor schema cross-check actually runs. Previously it was silently skipped when Harbor wasn't importable. It also pins one Harbor version for both the CLI and our code.
- `scripts/*.sh` run through `uv run`.
- Fixed a template bug: `validate.sh` broke on relative task paths after `cd validator`.
- All 6 examples pass the validator, including the Harbor cross-check.
