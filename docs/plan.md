# Plan: AfterQuery Harbor / Terminal-Bench task-generation work trial (core + stretch A-D)

## Context

AfterQuery's work trial (`harbor-tbench-worktrial/README.md`) asks for a pipeline that **authors Terminal-Bench-style Harbor tasks with `claude-sonnet-4.6`** and **keeps only "learnable" ones**: 1-3 of 5 runs pass with `terminus-2` + `claude-opus-4.8`. Graded in this order:
1. Fraction of tasks in band, with *valid* failure reasons.
2. Pipeline design.
3. How we know tasks are good.
4. Reliability and throughput.
5. Code quality.

Hard limits:
- $500 of API credit.
- Only those two models.
- Novel tasks only (no public repos or examples).
- `[agent].timeout_sec = 3600`.
- Timeouts and running out of turns are not valid failures.

Deliverables are source, `CHANGELOG.md` and a readable git history in the private repo `zignd/harbor-tbench-worktrial`.

Decisions made with the user:
- **3-5 day timebox.**
- **Agentic in-container authoring.** Sonnet builds and self-tests each task inside a live container. Implemented as a **Harbor meta-task** (see "Changes from the full papers", item 1).
- **Local Docker only.** 10 CPUs and 14.6 GB, so about 3 concurrent trials.

Development environment (set up and committed in `e4c095c`):
- **uv project at the repo root.** `pyproject.toml` + `uv.lock` pin `harbor==0.24.0`, `openai`, `pydantic` and `toml`, with `pytest` and `ruff` as dev dependencies. Run `uv sync` once, then `uv run ...`.
- **Python 3.13.16** (uv-managed) in `.venv/`, pinned by `.python-version` = `3.13`. Harbor needs Python ≥3.12.
- **uv 0.13.0 from Homebrew** is the only uv on PATH. Update it with `brew upgrade uv`.
- **Harbor is a project dependency**, not a global tool. That makes `validator/validate.py`'s native Harbor schema cross-check active; all 6 examples pass it.
- **Scripts** (`scripts/*.sh`) call `uv run --project "$ROOT_DIR"`. `validate.sh` now resolves task paths to absolute (a template bug fix).
- **Confirmed in Harbor 0.24.0:**
  - Agents `oracle`, `nop` and `terminus-2`.
  - Flags `-k/--n-attempts`, `-n/--n-concurrent`, `--ak/--agent-kwarg`.
  - `task.toml` **`artifacts = [...]`**, which copies container paths into the trial's host `artifacts/` dir after the run (`harbor/trial/artifact_handler.py`).
  - Two built-in QA commands that overlap with our judges:
    - **`harbor check`**: task quality against a rubric.
    - **`harbor analyze`**: trajectories against `reward_hacking` and `task_specification` rubrics.

    Both default to `claude-code` + `claude-sonnet-4-6`, so they must be pointed at our gateway and Sonnet 4.6.
- **Machine:** Docker 29.8 (10 CPUs, 14.6 GB). Poppler is installed for reading PDFs.
- **Shell note:** `VIRTUAL_ENV` points at a pyenv 3.11 env, so uv prints a harmless warning. `unset VIRTUAL_ENV` silences it.
- **Inference credentials:** these are in a git-ignored `.env` (mode 600); `.env.example` documents them. Load with `uv run --env-file .env ...`.
  - The key is an **OpenRouter** key with a **$500 limit**. Its base is `https://openrouter.ai/api/v1`, *not* the README's `api.aqinference.com`, which returns 401 for it. `generator/config.py` now defaults to OpenRouter.
  - Validated on 2026-10-12: `anthropic/claude-sonnet-4.6` answered through the OpenAI client, and `openrouter/anthropic/claude-opus-4.8` through LiteLLM (Harbor's path). Both models are listed on `/models`.
  - Spend can be read from OpenRouter's `GET /api/v1/key` (`usage`, `limit_remaining`). Its counters **lag by seconds to minutes** and don't update together, so re-read ~1-2 min after a run, and have the budget guard use the larger of `usage` and `limit − remaining`. Per-trial attribution comes from Harbor's `cost_usd`, which matched OpenRouter once settled (Phase 0).

## Research that shapes the design

All eight papers are downloaded to `docs/research/<arxiv-id>.pdf`, with a text conversion (`<arxiv-id>.txt`, from `pdftotext -layout`), and **all were read in full** (index: `docs/research/README.md`).

| Source | What we take |
|---|---|
| Bercovich, [*What Makes a Good Terminal-Agent Benchmark Task*](https://arxiv.org/abs/2604.28093) (arXiv 2604.28093; also [tbench.ai post](https://www.tbench.ai/news/writing-a-good-terminal-bench-task)) | Short, outcome-only instructions (LLM-written ones are the #1 failure). Oracle must *investigate* before fixing. Test outcomes on more than one or hidden examples. No clerical/format difficulty. Run batches of 5 and read the failures. |
| [Terminal Wrench](https://arxiv.org/abs/2604.17596) (arXiv 2604.17596; data: [few-sh/terminal-wrench](https://github.com/few-sh/terminal-wrench)) | ~17.7% of public TB tasks are hackable, and the synthetic SETA set is 17.5%. Exploit taxonomy (hollow-implementation, output-spoofing, structural-extraction, binary-hijacking, ...). Hack-elicitation prompt plus LLM judge. Judges need the reasoning trace (AUC 0.97 vs 0.92 on actions only). |
| [Hack-Verifiable Terminal Bench (HVTB)](https://arxiv.org/abs/2608.22103) (arXiv 2608.22103; [project page](https://majoroth.github.io/hack-verifiable-environments/hvtb)) | Claude-family agents read leaked tests or solutions ~31% of the time. Harder tasks get hacked more, and hacks happen early. Retry infra errors twice, then exclude them. Cost anchor ≈ $1.1 per trace. All 6 of our `examples/` are in the "Easy" class, so our target is TB "Medium/Hard". |
| [CLI-Universe](https://arxiv.org/abs/2606.22883) (arXiv 2606.22883) | **4-axis taxonomy** (17 domains, 8 skill types, 11 capabilities, 6 engineering pillars; App. A). **Blueprint** = instruction + internal hint + env checklist, rubric-reviewed before building (acceptance 72→91%). **Role-separated** test and solution agents. **Fail-to-pass** check. **Survival is only 33.6%**: ideas −30%, blueprints −14%, env build −14%, F2P −8.4%. Asset quality is the biggest ablation (−6.2 pts). **9-mode failure taxonomy** (Execution / Coherence / Verification). **Opus's dominant failure is *weak verification* (36%)**: it checks, but too shallowly. |
| [Meta-Task](https://arxiv.org/abs/2607.27929) (arXiv 2607.27929) | **Synthesis is itself a TB-format task**, run through Harbor, with the agent working inside a container and self-validating. >85% of packages succeed. Its full **meta-task instruction template** (App. F, Fig. 6) is directly reusable: consistency matrix instruction↔solution↔env↔tests, leakage check, and Dockerfile rules (never COPY solution/tests, verify every COPY source exists). Its **"Hard" spec**: specialized knowledge, non-obvious path, ≥3 checks, ≥1 trap, ~30+ expert minutes, anti-pattern list. **10 instruction writing styles.** Trajectory-level judge prompt (Fig. 8: shortcutting / fabrication / unproductive). Failure modes: context-compaction loss 47%, flawed self-verification 33%; **80% of failures declare success while wrong**. Implementation review uses the official **19-criterion TB rubric**. Decontamination by n-gram + TF-IDF. |
| [Tmax](https://arxiv.org/abs/2606.23321) (arXiv 2606.23321; code: [hamishivi/tmax](https://github.com/hamishivi/tmax)) | **9 sampling axes** (Table 8): domain, skill type, primitive skills, persona, language, task complexity, command complexity, **fixture kind** (image/audio/video/stripped binary/vendored pkg/compose), **verifier kind** (exact, metric_threshold, adversarial_corpus, fuzz_equivalence, multi_protocol). **Verifier thresholds are a continuous difficulty knob.** Without difficulty control, pools come out bimodal. **Balance score exp(H)/N** per axis. 13-gram decontamination vs TB2. Observed hacks: replacing a checker under `/tests` with a no-op, and stub binaries that fake outputs. Local sandboxes caused more timeouts than cloud. |
| [SkillSynth](https://arxiv.org/abs/2604.25727) (arXiv 2604.25727) | **Planner→constructor split**: one-pass generation gives inconsistent, under-complex tasks. Dual checks: oracle execution + rubric (instruction↔test alignment, no hint leakage). **77% of rubric failures are tests over- or under-specified vs the instruction.** Repair ≤3 cycles × ≤20 tool calls. **Bad first drafts rarely recover, so regenerate.** Coherent multi-step workflows are harder than single-skill seeds or random combinations; random multi-skill gives "many fine-grained requirements, few steps". **Inverse-frequency sampling** for coverage (Alg. 1). Base rate with 3 tries: 38% 0/3, **37% learnable**, 25% 3/3. Failures: partial implementation 42%, inline self-test over-trust 30%. ~$27 per verified task. |
| Foster & Foerster, [*Learning to Reason at the Frontier of Learnability*](https://arxiv.org/abs/2502.12272) (arXiv 2502.12272, NeurIPS 2025) | Learnability = p(1-p) bounds expected policy improvement (Thm 3.1), so the 1-3/5 band is justified. **Caveat: variance from aleatoric randomness looks learnable but isn't.** Pass/fail variance must come from the model, not a flaky environment. Future work they suggest: an LLM predicting learnability without rollouts, and ACCEL-style mutation of tasks to the right difficulty. These map to our stretch A and B. |

## Changes from the full papers (delta vs the earlier draft)

1. **Authoring is a Harbor meta-task** (Meta-Task). No custom tool-use loop.
   - Each synthesis request is a Harbor task (`generator/metatask/`) whose instruction is the filled meta-task template. Its env has a task skeleton, an example *format* reference, and common toolchains.
   - Run it with `harbor run -a terminus-2 -m openrouter/anthropic/claude-sonnet-4.6`.
   - Its `task.toml` declares `artifacts = ["/app/output"]`, so Harbor copies the package out. Its `tests/test.sh` runs our structural checks inside the container, so the meta-task reward means "the package is complete".
   - We get Harbor's trajectory logging, cost accounting and retries for free.
   - The repair round is a new meta-task run seeded with the previous package plus the host-gate logs.
   - Fallback, if Phase 0 shows a blocker: the custom `docker exec` loop from the earlier draft.
2. **Blueprint stage before building** (CLI-Universe, SkillSynth).
   - Sonnet turns a sampled spec into a blueprint: instruction draft, *internal hint* (resolution path, never shown to the solver), env/asset checklist, requirement list, difficulty levers, and verifier kind.
   - A cheap rubric review rejects weak ideas *before* any container work. The rubric covers clarity and convergence, solvability and verifiability, and difficulty and robustness.
3. **Taxonomy and sampler upgrade.**
   - Axes: CLI-Universe's four (domain, skill type, capability, pillar), plus Tmax's persona, task/command complexity, **fixture kind** and **verifier kind**, plus Meta-Task's **writing style** (restricted to terse-compatible styles: minimal, casual, terminal-dump, short narrative).
   - Tasks must be a **coherent, sequentially dependent workflow**, not a bundle of small requirements.
   - SkillSynth's **inverse-frequency weighting** (∝ 1/(count+1)) steers coverage.
4. **Difficulty levers aimed at frontier failure modes.**
   - All three synthesis papers find that strong models fail mostly by **shallow self-verification and partial implementation**. Opus specifically: weak verification at 36%.
   - So the levers that produce *valid*, stochastic Opus failures are:
     - Several substantive requirements, all stated in the instruction.
     - At least one non-obvious trap that a naive implementation fails (Meta-Task Hard spec).
     - Behavior checked on **hidden, verify-time-generated inputs** (Tmax `fuzz_equivalence`, `adversarial_corpus`).
     - State that must be consistent across components.
   - Forbidden as levers: format fussiness, hidden resource limits, hidden timeouts. CLI-Universe's compcert example shows how a hidden 120 s cap creates an invalid failure.
5. **Verifier kinds give the tuner a continuous knob** (Tmax). Stretch B tunes in this order:
   1. Adjust a stated threshold, N inputs, or corpus size, then recalibrate.
   2. Add or remove one lever.
   3. Regenerate from the blueprint, rather than repairing more than twice, because bad first drafts rarely recover (SkillSynth).

   This is an ACCEL-style mutation, the follow-up Foster & Foerster suggest.
6. **Test↔instruction alignment is the #1 gate** (SkillSynth: 77% of rubric failures).
   - Check both directions: *too lenient* (a requirement with no test) and *too strict* (a test with no requirement).
   - Run it before Opus spend, preferably via `harbor check` with a custom rubric built on the TB 19-criterion rubric (Meta-Task App. D).
7. **Determinism gate** (Foster & Foerster's aleatoric caveat).
   - Oracle must pass **3/3**, and nop must fail.
   - Lint tests for time, randomness or network dependence.
   - The failure judge has an explicit "environment nondeterminism" label (invalid).
8. **Failure-judge taxonomy made concrete.**
   - Use CLI-Universe's 9 modes plus the SkillSynth and Meta-Task categories, each mapped to valid/invalid.
   - **Valid:** partial implementation, weak/no verification, premature termination, wrong root cause, reasoning–action mismatch, context-compaction loss, API hallucination.
   - **Invalid:** turn/step budget exhausted, pager/tmux/interactive-editor trap, env timeout, spec ambiguity, test overreach, env nondeterminism.
   - Judge at the **trajectory level** (Meta-Task found task-level judging less precise).
9. **Pass-audit prompt adopts Meta-Task's Fig. 8 criteria** (shortcutting, fabrication, red-flag filenames, reading "BUG:" comments), plus the Terminal Wrench exploit labels.
10. **New lints** (Meta-Task Dockerfile rules, plus the Tmax hack observations):
    - No COPY of `solution/` or `tests/`.
    - Every COPY source exists.
    - Setup scripts deleted after use.
    - No expected-output files in `environment/`.
    - **No suggestive comments** in env files (`BUG`, `FIXME`, `fix:`, `intentionally`, `hint`).
    - Test helpers live in `tests/`, never in agent-writable paths.
11. **Novelty against published Terminal-Bench tasks, enforced early** (README novelty rule; Tmax and Meta-Task decontamination).
    - **Reference corpus: every published Terminal-Bench set on the Harbor hub, 425 tasks**, plus `examples/`. `make tb-reference` downloads them into git-ignored `data/tb-reference/` (~2 min) and keeps only `instruction.md` + `task.toml` per task (3.6 MB):
      - `terminal-bench/terminal-bench@latest`: 66 tasks, the current release. That matches Terminal-Bench **4.0** (Aug 2026, 66 tasks) and shares no task with 2.x.
      - `terminal-bench/terminal-bench-2-1`: 89 tasks (2.1 supersedes 2.0, with the same task names).
      - `terminal-bench-pro`: 200 tasks.
      - `terminal-bench-science`: 70 tasks.

      We compare against all of them, not one "target" version, because the README forbids reusing or adapting *any* public task.
    - **Three layers.** Text overlap alone only catches copied wording, not the same task reworded.
      1. **Prevent at ideation.** The blueprint prompt includes a compact list of the TB task concepts (name plus one-line gist) with "don't build any of these or a variant of them".
      2. **Gate the blueprint, before any build or Opus spend.** Run 13-gram overlap and TF-IDF cosine of the blueprint's instruction draft and requirements against every reference instruction. Take the **top-3 nearest** and run a Sonnet **"same underlying task?"** judge on them (same core problem, same environment, same solution path → reject). A reject sends the spec back to resampling. Cheap: one small Sonnet call per blueprint.
      3. **Re-check the finished package before calibration**, since the authored instruction can drift from the blueprint. Same lexical + top-3 semantic check on the final `instruction.md` and environment summary.
    - The same semantic judge also runs **within our own batch** (near-duplicate tasks).
    - **Thresholds** are set on the reference corpus itself (TB tasks vs each other) so they flag real overlap without rejecting tasks that merely share a domain. The 13-gram rule: any shared 13-gram outside boilerplate → reject.
    - Stretch C reports the max/mean similarity to the TB corpus and the reject counts per layer.
12. **Stretch A additions.**
    - Log Sonnet's *predicted* pass rate at blueprint time (Foster & Foerster future work) and report its correlation with the observed band.
    - Use it as a pre-filter only if it proves predictive.
    - Expectation set by SkillSynth: ~1/3 of functionally correct tasks land in band before tuning, so plan for ~3 candidates per shipped task.
13. **Stretch D scores both sets with the same `harbor check` rubric.** Phase 0 found that Harbor's default rubric has **11 criteria**, not the 19-criterion TB review rubric Meta-Task describes. We use Harbor's 11 plus our additions on generated tasks and `examples/` alike (AfterQuery's `fix-git` already fails 4/11), alongside the blinded human-vs-generated discrimination test.

## Architecture

Keep the template's structure (`generator/`, `validator/`, `scripts/`, `output/`) and add an evaluator and analysis layer. Every stage is a pure function `TaskDir -> StageResult` and records an event in an append-only ledger.

```
spec sampler (inverse-freq) ─► blueprint (Sonnet, TB concept list) ─► rubric review + novelty gate vs 425 TB tasks ──reject──► resample
       ▲                                                     │ pass
       │                                                     ▼
 coverage stats            meta-task authoring: harbor run -a terminus-2 -m sonnet-4.6
       │                   (in-container build + self-validate, artifacts=/app/output)
       │                                                     │
       │        structural + lint + leak scan + alignment check (harbor check) + novelty re-check
       │                                                     │
       │        host gates: docker build, oracle=1 (3/3), nop=0 ──fail──► repair meta-task (≤2) / regenerate
       │                                                     │
       │        red-team: Sonnet hack-elicitation trial (1 run) ──exploit──► repair
       │                                                     │
       │        calibration: Opus 4.8 sequential trials (stop when decided)
       │                                                     │
       │        audit: pass audit (hacks) + failure judge (valid/invalid) per trajectory
       │                                                     │
       └── tuner: knob → lever → regenerate (≤2 rounds) ◄── band verdict ──► output/<task> + report
```

### Modules (new files unless noted)

- **`generator/config.py`** (extend): read `.env`; price table, budget caps, `MAX_TURNS=200`, concurrency, band params (the band params already exist and are reused).
- **`generator/spec.py`**: `TaskSpec` (pydantic) over the axes in delta 3. It also holds named **difficulty levers** (delta 4) and a **verifier kind** with its knob value. The inverse-frequency sampler draws from it.
- **`generator/blueprint.py`**: spec → `Blueprint` (instruction draft, internal hint, env/asset checklist, requirements, levers, verifier kind and knob, Sonnet-predicted pass rate). Followed by a rubric review that returns accept/reject with reasons.
- **`generator/metatask/`**: the meta-task Harbor package.
  - `instruction.md.j2`: Meta-Task Fig. 6 template, adapted with our rules, the blueprint, the canary and the `uvx` verifier convention.
  - `environment/Dockerfile`: synthesis base with Python, common build tools, procps and a task skeleton.
  - `tests/test.sh`: in-container structural self-check, so the reward means the package is complete.
  - `task.toml`: `artifacts = ["/app/output"]`.
  - **Role separation** (CLI-Universe): the instruction tells the agent to write `tests/` from the instruction and requirement list *before* writing `solve.sh`, and not to edit tests to fit the solution. A separate Sonnet alignment check enforces it afterwards.
- **`generator/author.py`**: renders a meta-task for a blueprint, runs it through `evaluator/harbor_runner.py`, extracts the package from `artifacts/`, and stamps canary and metadata. Repair mode adds the previous package plus gate logs to the meta-task env.
- **`generator/generate.py`** (implement the stub): keep the `generate_task(topic, output_dir) -> dict` signature. It runs spec/blueprint → author → returns the task dir and status.
- **`validator/validate.py`** (keep and reuse) plus **`validator/lint.py`**: canary placement, no `docker_image`, agent timeout ≥ 3600, instruction length/style, no source-grep or package-installed tests, `solve.sh` investigates before writing, plus the delta-10 lints.
- **`validator/leak_scan.py`**: build the image, extract distinctive tokens from `tests/` and `solution/`, and search the container filesystem plus `docker history` for them.
- **`validator/novelty.py`**:
  - Builds a cached index (13-gram sets + TF-IDF vectors) over `data/tb-reference/*/instruction.md` and `examples/`.
  - `nearest(text, k=3)` returns the closest reference tasks with scores. `concept_list()` returns the name + one-line gist list used in the blueprint prompt.
  - `judge_same_task(candidate, refs)` is the Sonnet semantic check, with structured output: same_task / variant / distinct, plus reasons.
  - Used by the blueprint gate, the pre-calibration re-check, and the diversity report.
- **`evaluator/harbor_runner.py`**: wraps `harbor run` for oracle, nop, terminus-2 (Sonnet meta-tasks and Opus calibration), `-k`, and `--ak max_turns=…`. It parses the job dir into `TrialResult` (reward, cost/tokens, duration, exit reason, trajectory path, artifacts path) and retries infra errors twice, then excludes them.
- **`evaluator/calibrate.py`**: exact **sequential curtailment** of the 5-run band test, run in waves of ≤3. It stops as soon as the verdict can't change:
  - Accept at ≥1 *legit* pass and ≥2 valid fails.
  - Reject as too easy at 4 passes.
  - Reject as too hard at 5 fails.

  Pure `decide(outcomes) -> Verdict | None`.
- **`evaluator/redteam.py`**: copy the task, append a Terminal-Wrench-style hack-elicitation paragraph, and run 1 Sonnet terminus-2 trial. A serious exploit goes to repair, with the exploit trajectory as feedback.
- **`analysis/judge.py`**: trajectory-level Sonnet judges with structured JSON output and the full trajectory, reasoning included. Prefer wrapping `harbor analyze` with custom rubrics; fall back to direct Sonnet calls.
  - (a) **Pass audit**: command scan, then Meta-Task Fig. 8 + Terminal Wrench labels.
  - (b) **Failure analysis**: the delta-8 taxonomy, mapped to valid/invalid.

  A task with any invalid failure is not shipped. It goes to the tuner as "fix spec".
- **`analysis/tuner.py`** (stretch B): knob → lever → regenerate (delta 5), ≤2 rounds, per-mutation effects logged.
- **`analysis/ledger.py`**: `runs/ledger.jsonl` event log (stage, task, cost, tokens, seconds, result) plus a **budget guard**.
- **`analysis/report.py`**: Part 3 funnel (generated → blueprint accepted → structurally valid → functionally correct → red-team clean → learnable), pass-count histogram, cost and time totals, cost-efficiency vs naive 5×, predicted-vs-observed pass rate, diversity, human-likeness. Writes `reports/summary.md` and JSON.
- **`analysis/diversity.py`** (stretch C): per-axis coverage and **balance score exp(H)/N**; difficulty spread; instruction uniqueness (TF-IDF cosine max/mean, Vendi over TF-IDF); **novelty report** from `validator/novelty.py` (similarity to the TB corpus and examples, rejects per layer); Sonnet "same underlying task?" check on the closest pairs within our batch. No embedding model, since only the two models are allowed.
- **`analysis/human_likeness.py`** (stretch D): TB 19-criterion rubric on both sets (via `harbor check`), a blinded "which is human-written?" discrimination test (≈50% means indistinguishable), and stylometrics.
- **`scripts/run_batch.py`** (+ `scripts/pipeline.sh`): `run_batch --n 12 --budget 150`, resumable from the ledger.
- **`tests/`** (unit tests for our code, not task tests): `decide()`, ledger and budget guard, lints, leak-scan token extraction, sampler coverage/inverse-frequency, the blueprint schema, and the job-dir and artifacts parser on a recorded fixture.

### Budget plan ($500 key; $380 authorized for the goal run; re-planned after Phase 0)

**Measured unit costs (Phase 0, 2026-10-12):**

| Unit | Measured | Notes |
|---|---|---|
| Opus 4.8 trial, Easy example (`fix-git`) | $0.117 | 11 turns, 85% cached input. Generated Medium/Hard tasks will run more turns; **assume $0.5-1.5** until measured in Phase 2 |
| Sonnet 4.6 authoring meta-task | **$2.75** | Hit the 80-turn cap; 5.07M input tokens (98% cached), 58k output; 25 min. The main cost lever to cut (see Phase 1) |
| DeepSeek authoring meta-task (dev) | ~$0.15-0.2 | 37 turns, 1.03M input, 230k output; ~47 min. Harbor reports `cost_usd: None` (no LiteLLM price) |
| `harbor check` (Sonnet reviewer) | $0.084 | ~1.5 min per task |

**Buckets (sum ≤ $380 authorization; the $75 reserve stays untouched):**

| Bucket | Cap | Basis |
|---|---|---|
| Phase 0 probing (done) | $3.2 | Actual |
| Blueprints + novelty judge + reviews (~45 candidates) | $10 | Small structured Sonnet calls |
| Meta-task authoring + repairs (~30 builds) | $90 | ~$2.5 per build now; target ≤$1.5 after the cost lever |
| `harbor check` + red-team + judges | $45 | check $0.08/task; red-team ≈ one Sonnet terminus run/task; judges per Opus trial |
| Opus calibration | $215 | ~25-40 tasks × ~3.5 trials (curtailment) at ~$1.5-2.5/trial worst case |
| Contingency inside the authorization | $17 | |

If an Opus trial costs more than ~$3, shrink the batch rather than cut the number of trials per task. Expect about a third of functionally correct tasks to land in band before tuning (SkillSynth base rate).

### Spend discipline

The $500 key is the only budget, and **it expires 2026-10-23 07:00 UTC**. Every rule below saves money **without** touching the work-trial constraints:
- Opus 4.8 + terminus-2 is the only difficulty benchmark.
- The band is defined on 5 runs.
- `timeout_sec = 3600`.
- No other models for generating, benchmarking, or ship/report decisions. Dev mode (below) is plumbing only.
- Only valid failures count.

**Dev mode: a cheap model for plumbing iterations**
- `DEV_MODE=1` routes every call (authoring, judges, red-team, and the terminus-2 eval agent) to `DEV_MODEL`, default **`deepseek/deepseek-v4.1-flash`**. That's $0.15/$0.60 per M tokens, vs Sonnet's $3/$15 and Opus's $5/$25, so ~20-40× cheaper. It's validated through both the OpenAI client and LiteLLM.
- **Use it for:** debugging the runner, job-dir and artifacts parsing, the meta-task wiring, the calibration loop and early-stop logic, ledger and budget guard, judge prompt plumbing (JSON shape, truncation), and report generation.
- **Never for:** difficulty or band verdicts, shipping decisions, tuning knobs, Part 3 metrics, or anything in `reports/`. Dev results go to `output-dev/` (git-ignored) and are tagged `dev` in the ledger. `config.assert_official_models()` makes ship/report steps refuse to run in dev mode.
- **Known limits:**
  - A different model behaves differently: small models are brittle with terminus-2's keystroke interface (Tmax). So a dev run only shows the plumbing works, not that a task is easy or hard.
  - It's a reasoning model, so very small `max_tokens` caps can return empty content.
- **Order of preference while developing:** fixtures and `--dry-run` (free) → `DEV_MODE=1` (cents) → official models (dollars), used only once the plumbing works.
- Dev spend is reported separately in `CHANGELOG.md`, for transparency. AfterQuery can see which models the key called.

**Tracking**
- `make usage` (OpenRouter `GET /api/v1/key`) is the source of truth for spend. Run it **before and after every phase and every batch**, and log the delta in `CHANGELOG.md` (the plan's budget table vs actual).
- The ledger records each call's estimated cost. Per-model prices come from OpenRouter `/models` `pricing`, or Harbor's reported cost. After each batch, the ledger total is reconciled against `make usage-json`. A gap of more than 10% means our accounting is wrong, so stop and fix it.
- The **budget guard** in `run_batch` reads `usage-json` before starting any Opus trial. It refuses to start new calibration once **remaining < $75**, the protected reserve.

**Hard limits (configurable in `generator/config.py`, enforced in code)**

| Limit | Value | Why |
|---|---|---|
| Protected reserve | $75 | Final re-verification, a 5× naive spot-check, and AfterQuery follow-ups |
| Per-batch cap | `--budget` flag (e.g. $150) | Stop mid-batch instead of overspending |
| Opus concurrency | ≤3 trials | Limits burn rate and local resource contention (Tmax saw local contention cause timeouts) |
| Opus `max_turns` | 200 | Caps runaway trials (README allows it). Hitting it is an *invalid* failure, never a valid one |
| Meta-task `max_turns` | e.g. 80 | Authoring isn't constrained by the README, so cap it tighter |
| Repair rounds | ≤2, then regenerate | Bad first drafts rarely recover (SkillSynth) |
| Phase caps | Budget table above | A phase that hits its cap stops and gets re-planned, not silently extended |

**Spend Opus only on tasks that can ship**
1. **All cheap gates first.** No Opus trial until the task has passed every one of these: structural, lints, leak scan, alignment check, oracle 3/3, nop, and the Sonnet red-team. Each costs cents or nothing; an Opus trial costs dollars.
2. **Exact curtailment** (`decide()`): stop as soon as the 5-run verdict can't change. Accept at ≥1 legit pass and ≥2 fails (the maximum final passes is then 5 − fails ≤ 3). Reject at 4 passes or 5 fails. **The verdict is identical to running all 5.** For transparency, every report entry shows `k/n` and states that the verdict is guaranteed. If the budget allows at the end, shipped tasks are topped up to a full 5/5 record.
3. **Judge as you go.** Run the failure judge and pass audit after *each* Opus trial, not at the end. An *invalid* failure (spec ambiguity, test overreach, env issue, turn cap) or a hacked pass means the task can't ship as-is. **Stop calibrating it immediately** and send it to repair. Don't spend the remaining trials on a broken task.
4. **Order by promise.** Calibrate the candidates whose blueprint has the best alignment and rubric scores (and Sonnet-predicted pass rate near 0.5) first, so the budget goes to the likeliest learnable tasks.
5. **Target-driven batches.** Stop generating once the target number of learnable tasks is reached (README: 10+). Don't run a fixed N if the target is already met.

**Scale in steps, not all at once**
- Batch sizes go 1 (Phase 0 spike) → 3 (pilot) → ~10 → ~12-15. After each step, compute **cost per learnable task** and the funnel yield, and decide the next batch size from those numbers.
- If the pilot shows >$40 per learnable task, stop and fix the generator (difficulty levers, gates) before generating more.

**Don't pay twice**
- Each stage result is cached in the ledger under a **content hash of the task directory**. Re-running the pipeline skips stages whose inputs didn't change, so resuming after a crash or code change costs nothing.
- Development and unit tests use **recorded job-dir fixtures** and a fake runner (`--dry-run`), with no API calls. End-to-end plumbing checks use `DEV_MODE=1`. Only official batches spend real money.
- Check in Phase 0 whether OpenRouter reports **cached prompt tokens** for terminus-2 runs. If caching is active, long trajectories are much cheaper than the per-token estimate. Record this in the cost model either way.

**What we must not do to save money**
- Change Opus's sampling or thinking settings, the agent, or the 3600 s timeout. That would change what "learnable" means.
- Use any other model as a cheap proxy for difficulty.
- Ship a task on fewer than the trials its verdict needs.
- Count a turn-cap or timeout failure as valid.

## Work checklist

Tick an item (`- [x]`) in the same commit that completes it, and add a `CHANGELOG.md` entry. Each item names its output and how we know it's done. Items marked 💲 call a model, so run `make usage` before and after, and ask the user first if one is expected to cost more than ~$10 (see `AGENTS.md`).

**Progress: 57 / 83 items** (update this line when ticking items; `make plan` or `bash scripts/track-plan.sh` prints overall and per-phase counts, `--remaining` lists open items with line numbers)

### Phase 0: setup and spike

Environment and repo
- [x] uv project with pinned `harbor==0.24.0`, Python 3.13, scripts via `uv run` (`086928a`)
- [x] Fix `validate.sh` relative-path bug; all 6 examples pass the validator with the Harbor cross-check
- [x] Credentials in git-ignored `.env` + `.env.example`; key validated on Sonnet 4.6 and Opus 4.8; `config.py` defaults to OpenRouter (`181ac72`)
- [x] `make usage` / `make usage-json` for spend tracking (`38fe483`)
- [x] Plan + full-text research notes in `docs/research/` (`92fa03d`)
- [x] Spend-discipline rules in the plan (`8f92630`)
- [x] `AGENTS.md` / `CLAUDE.md` with constraints and conventions; timestamped `CHANGELOG.md` (`554fc8c`, `26d6649`)
- [x] Conventional-commit history
- [x] Checklist-format plan (this section)
- [x] Dev mode: `DEV_MODE=1` → `deepseek/deepseek-v4.1-flash` for plumbing; `output-dev/`; `config.assert_official_models()` guard

Harbor spike (learn the real mechanics before writing pipeline code)
- [x] Run `oracle` and `nop` on all 6 examples. Record the pass/fail table, run times, and whether verify-time `uvx` installs ever fail (no API cost).
- [x] Inspect a job dir. Document the layout, `result.json` fields (reward, cost/tokens, timing, exceptions), trajectory format and where `artifacts/` lands (in `docs/harbor-notes.md`).
- [x] 💲 Run 1 Opus 4.8 terminus-2 trial on one example. Record the **real cost per trial**, the turn count, and whether OpenRouter reports cached prompt tokens.
- [x] Confirm `-k`, `-n`, `--ak max_turns=200` behave as expected and Docker image caching works across trials.
- [x] 💲 Dev-mode meta-task spike (`DEV_MODE=1`, DeepSeek): one hand-written meta-task run. Get the wiring right (prompt rendering, `artifacts` collection, in-container test) for cents.
- [x] 💲 Meta-task spike: one hand-written meta-task run with Sonnet 4.6. Confirm `artifacts = ["/app/output"]` arrives on the host, record the authoring cost, and check that in-container self-validation works without Docker. **Go/no-go:** if it fails, switch to the custom `docker exec` loop.
- [x] 💲 Try `harbor check` on 1 example with Sonnet 4.6 through our gateway. Done: it works for $0.084 per task, the default rubric has 11 criteria (not 19), and the decision is to wrap it with a custom rubric.
- [x] Re-plan the budget table from the measured costs (Opus trial, authoring run, judge call).
- [x] Save 1 oracle, 1 nop, 1 Opus and 1 meta-task job dir as test fixtures under `tests/fixtures/` (secrets stripped).

### Phase 1: Part 1, valid tasks

Spike follow-ups (found in Phase 0)
- [x] Pipeline-owned `tests/test.sh`: the authored one called `uvx` without installing it, so the oracle failed 3/3 in the real build even though in-container self-checks passed. Now the standard `generator/metatask/standard_test.sh` ships in the synthesis image, `collect_package()` always overwrites `tests/test.sh` with it, and the author self-checks with the exact verifier command. Re-gated: Sonnet's package passes oracle 3/3 and nop 0, and so does DeepSeek's.
- [x] 💲 Cut authoring cost from $2.75/task toward ≤$1.5. Sonnet hit the 80-turn cap with ~63k context per call. Levers (authoring only; Opus calibration settings untouched): **Outcome (measured):** summarization fired (2× on an 80-turn run) and cut total input 25% (5.07M→3.82M), but each summary breaks the prompt cache (uncached input 0.10M→0.35M), and the new ~800-2,000-line environments doubled output (58k→100k). A fresh build now costs **$3.86**, and a repair-style round **$0.91**. The target was missed for fresh builds because tasks are deliberately larger; the budget ($90 for ~25 builds) still fits. Summarization is kept, since it bounds context on long runs.
  - terminus-2 `proactive_summarization_threshold` so long contexts get summarized.
  - A compact format spec in the instruction instead of reading the whole reference task.
  - Asking for whole-file writes per command.

  Measure turns, cost and gate pass-rate on 2 blueprints.
- [x] Cost accounting for models LiteLLM can't price (DeepSeek reports `cost_usd: None`): compute from tokens with OpenRouter `/models` pricing in the ledger. Done: `TrialResult.priced_cost()` uses OpenRouter `/models` prices (cached in `runs/prices.json`).


Foundations
- [x] `generator/config.py`: price table, budget caps ($75 reserve, per-batch cap), `MAX_TURNS`, concurrency; reads `.env` values. Done: prices come from OpenRouter `/models` via `analysis/openrouter.py`.
- [x] `analysis/ledger.py`: append-only `runs/ledger.jsonl` (stage, task, inputs hash, cost, tokens, seconds, result) plus content-hash cache lookup. Unit-tested.
- [x] Budget guard: reads `make usage-json` data and refuses new model work below the reserve or per-batch cap. Unit-tested.
- [x] `evaluator/harbor_runner.py`: run oracle/nop/terminus-2 jobs and parse them into `TrialResult`; retry infra errors twice, then exclude. Supports `--dry-run` with fixtures. Unit-tested on fixtures. Done: smoke-tested live (2 oracle trials). `--dry-run` lives at the batch level (fake runner over fixtures), wired in `run_batch`.

Generation
- [x] `generator/spec.py`: `TaskSpec` with the taxonomy axes, difficulty levers, verifier kind and knob, plus an inverse-frequency sampler. Unit-tested for coverage behavior.
- [x] 💲 `generator/blueprint.py`: spec → `Blueprint` (instruction draft, internal hint, env checklist, requirements, levers, verifier knob, predicted pass rate) via Sonnet structured output, plus a rubric review returning accept/reject with reasons. Done: official Sonnet blueprints for every pilot and Batch 1 spec; the review's scores are enforced in code (every score ≥3, mean ≥3.6).
- [x] `generator/metatask/`: meta-task package (instruction template adapted from Meta-Task Fig. 6, synthesis Dockerfile, in-container `tests/test.sh` completeness check, `task.toml` with `artifacts`).
- [x] 💲 `generator/author.py`: render a meta-task from a blueprint, run it, extract the package from `artifacts/`, stamp canary and metadata; repair mode with previous package + gate logs. Done: repair rounds bake the failed package into `/app/previous` and append the gate findings. The canary is enforced by the in-container check plus lint rather than stamped afterwards.
- [x] `generator/generate.py`: implement `generate_task(topic, output_dir)` end to end (spec → blueprint → author), keeping the template signature. Done: the topic becomes a hint on a sampled spec.

Gates
- [x] `validator/lint.py`: canary placement, no `docker_image`, timeout ≥ 3600, instruction style/length, no source-grep or package-installed tests, `solve.sh` investigates first, no COPY of `solution/`/`tests/`, COPY sources exist, no suggestive comments, test helpers only in `tests/`. Unit-tested on good/bad fixtures.
- [x] `validator/leak_scan.py`: build the image and search its filesystem plus `docker history` for distinctive tokens from `tests/` and `solution/`. Unit-tested on a planted-leak fixture. Done: blocking leaks are answer-like tokens (hashes, long numbers); quoted strings found in the image are non-blocking notes. ~2 s per task.
- [x] `make tb-reference`: download all published TB sets (latest/4.0, 2.1, Pro, Science = 425 tasks) into git-ignored `data/tb-reference/`, keeping instruction + task.toml only (verified).
- [x] `validator/novelty.py`: 13-gram + TF-IDF index over the 425-task TB corpus + `examples/`, `nearest(k=3)`, `concept_list()`. Thresholds calibrated on TB-vs-TB similarity. Unit-tested: a lightly reworded TB instruction is caught, and an unrelated one isn't. Done: 425 unique refs after de-duplication. Threshold set at cosine 0.70 (distinct-task p90 = 0.52; known variant pairs ≥ 0.75).
- [x] 💲 Novelty gate in blueprint review: TB concept list in the blueprint prompt, plus the Sonnet "same underlying task?" judge on the top-3 nearest TB tasks. A reject resamples the spec. Unit-tested with a planted near-copy blueprint. Done: runs on every official blueprint (TF-IDF + 13-gram over 425 TB tasks and our own candidates, then the Sonnet judge on the top-3); planted copies tested in `test_blueprint.py` / `test_novelty.py`. A reject gets one blueprint retry told why (not a spec resample: the spec was fine, the idea drifted), and our own earlier tasks are in the prompt's must-not-resemble list.
- [x] 💲 Novelty re-check on the finished package before calibration (instruction can drift from the blueprint). Done: `gate_novelty` in `stage_gates`; ran on both official `ledger-reconcile` packages (nearest TB task 0.086).
- [x] 💲 Alignment check: every test maps to an instruction requirement and every requirement has a test (via `harbor check` with a custom rubric, or direct Sonnet). Done: `harbor check` with `generator/quality_rubric.toml` (11 Harbor + 5 work-trial criteria; 9 blocking). The spike task passes 16/16 for $0.13.
- [x] Functional gates: Docker build, oracle 3/3, nop 0, chained in order with early exit.
- [x] `scripts/run_batch.py` (+ `make` target): spec → blueprint → author → gates for N candidates, resumable from the ledger, with `--budget` and `--dry-run`. Done: resumable via each candidate's `status.json`; `--dry-run` runs the real gates on fixtures for free (37 s).

Part 1 milestone
- [ ] 💲 Dev-mode dry run (`DEV_MODE=1`): 2-3 candidates end to end through generation and gates, to shake out plumbing bugs before official spend. Results stay in `output-dev/`.
- [ ] 💲 Pilot batch of 3 candidates through generation and gates. Record funnel and cost per task.
- [ ] 💲 Reach **≥5 tasks** that pass the structural validator and the functional gates (oracle 3/3, nop 0).
- [x] Hand-review 2 generated tasks side by side with `examples/` and the guideline rules. Tighten the meta-task template and lints from what's found. Done: review #1 (`ledger-reconcile`) is in `docs/reviews/hand-review.md` and led to three prompt fixes. Review #2 will be a pipeline-generated pilot task.

### Phase 2: Part 2, calibration

- [x] `evaluator/calibrate.py`: pure `decide(outcomes)` with exact curtailment (accept at ≥1 legit pass + ≥2 valid fails, reject at 4 passes or 5 fails). Exhaustively unit-tested against the full 5-run verdict. Done: tested on all 32 sequences. Expected 3.85-4.3 trials instead of 5 for p = 0.2-0.8.
- [x] Calibration runner: Opus trials in waves of ≤3, budget guard checked before every trial, outcomes written to the ledger. Done: waves are capped at the fewest trials that can still reach a verdict, so they never overshoot.
- [x] 💲 Try `harbor analyze` (built-in `reward_hacking` + `task_specification` rubrics) on real calibration trajectories. Decide wrap vs build for both judges. Done: on 2 real Opus passes it agreed with our audit (reward_hacking and task_specification both pass), but costs $0.13 per trial vs our judge's $0.012. **Decision: our judges are primary** (10× cheaper, structured labels for the tuner and report); `harbor analyze` stays an optional cross-check.
- [x] 💲 `analysis/judge.py` (a), pass audit: command scan plus a trajectory-level Sonnet judge (Meta-Task Fig. 8 + Terminal Wrench labels). Hacked passes don't count. Done: validated on 4 real Opus passes (all labelled legit, $0.012-0.013 each) and on the red-team run.
- [ ] 💲 `analysis/judge.py` (b), failure judge: the 9-mode taxonomy mapped to valid/invalid, with full reasoning kept.
- [x] Stop-early wiring: on the first invalid failure or hacked pass, stop calibrating the task and send it to repair.
- [x] Shipping step: copy learnable tasks into `output/<task>/` with a per-task calibration record (outcomes, judge labels, why the model fails). Done: `scripts/calibrate_candidates.py` writes `output/<slug>/README.md` (calibration plus judged failure reasons). Refuses to run in dev mode.
- [x] 💲 Dev-mode calibration loop (`DEV_MODE=1`): exercise waves, early stop, judges and ledger on 1-2 tasks before any Opus spend. Done: on `dev-9992cd0670d5` (DeepSeek, $0.31): wave sizing, an `AgentTimeoutError` trial counted as invalid (never a valid failure), the pass audit on the other trial, early stop with verdict `invalid`, all in the ledger. Also exercised a crash-resume of calibration.
- [ ] 💲 Calibrate the Phase 1 tasks (pilot). Record cost per learnable task. **Go/no-go:** above $40 per learnable task → fix generation before scaling.
- [ ] 💲 Batch 1: ~10 new candidates end to end through calibration.
- [ ] Read every failure-judge summary from Batch 1, and retune lever and knob defaults toward TB Medium/Hard. Record the before/after reasoning in `CHANGELOG.md`.

### Phase 3: stretch B + C and red-team

Red-team (part of "how we know tasks are good")
- [x] 💲 `evaluator/redteam.py`: hack-elicitation copy of the task + 1 Sonnet terminus-2 trial + judge. A serious exploit goes to repair, with the exploit trajectory as feedback. Done: ran officially on 3 packages (all honest, `hackable: false`); a beaten verifier returns the exploit as repair feedback.
- [x] Wire the red-team as a gate before Opus calibration, and record the hackable rate per batch. Done: last gate in `stage_gates` (runs alongside the quality check); a beaten verifier goes back to repair. `reports/summary.md` shows the hackable rate per batch.

Stretch B: difficulty tuning
- [x] `analysis/tuner.py`: knob → lever → regenerate (≤2 rounds), with each mutation and its effect logged. Done: `scripts/tune_candidates.py` runs it on near-misses whose failures were all valid, and ships tasks that land in band.
- [ ] 💲 Run the tuner on every Batch 1 near-miss (0/5 with valid failures, 4-5/5). Record how many moved into the band.

Stretch C: diversity
- [x] Coverage-steered sampling: the sampler reads ledger counts so it moves away from saturated cells. Done: `run_batch` samples inverse-frequency against every earlier candidate's spec.
- [x] Novelty report: per-task similarity to the TB corpus (by set) and `examples/` (max/mean, nearest task), plus rejects per novelty layer across all batches. Done: `analysis.report` shows nearest TB task, per-set max cosine and nearest `examples/` task per shipped task, plus rejects per layer (so far 2 blueprint-judge rejects of 9 checked: variants of our own Phase 0 task).
- [x] 💲 Near-duplicate check: Sonnet "same underlying task?" judge on the closest TF-IDF pairs. Done: the novelty gate indexes our own earlier candidates alongside the 425 published tasks (`novelty.gate_index`, excluding the candidate itself), at both the blueprint and final-package checks.
- [x] `analysis/diversity.py`: per-axis coverage, balance score exp(H)/N, difficulty spread, instruction uniqueness (TF-IDF cosine, Vendi). Done: difficulty spread added (blueprint labels, predicted pass-rate quartiles, observed pass rates).

Batch 2
- [ ] 💲 Batch 2: ~12-15 candidates with the red-team gate, tuner and coverage-steered sampler on.
- [ ] Reach the **README target of 10+ generated tasks** in the Part 3 batch, plus the learnable tasks shipped in `output/`.

### Phase 4: Part 3 + stretch A and D, write-up

Part 3: pipeline metrics
- [x] `analysis/report.py`: funnel (generated → blueprint accepted → structurally valid → functionally correct → red-team clean → learnable), pass-count histogram, total cost and wall time. Writes `reports/summary.md` + JSON. Done: funnel, histogram, cost/time, per-batch table, diversity, novelty, curtailment, human-likeness; regenerated from evidence on every run.
- [ ] Reconcile ledger spend against `make usage-json` (within 10%), and state the total in the report.

Stretch A: cost-efficient evaluation
- [ ] Curtailment savings: trials run vs naive 5× per task, in $ and %.
- [ ] Simulation over the observed per-task p: expected savings and the effect of the optional aggressive 0/3 early reject (reported only, not used for shipping).
- [ ] Predicted-vs-observed pass rate: correlation of Sonnet's blueprint-time prediction with the Opus outcome, and whether it would work as a pre-filter.

Stretch D: human-likeness
- [ ] 💲 Score generated tasks and `examples/` with the same TB 19-criterion rubric (`harbor check`), shown side by side.
- [ ] 💲 Blinded "which is human-written?" discrimination test, with accuracy reported (≈50% means indistinguishable).
- [ ] Stylometrics: instruction length, bullets, headers and emphasis words, ours vs examples.
- [ ] `analysis/human_likeness.py` section in the report.

Verification (see "Verification" below)
- [ ] `uv run pytest` and `uv run ruff check .` pass.
- [ ] Every task in `output/` passes `bash scripts/validate.sh`, and an independent oracle (3/3) and nop re-run.
- [ ] Every shipped task has its calibration record and a valid-failure explanation in `reports/summary.md`.
- [ ] 💲 Spot-check reproducibility: rerun one shipped task 5× naively (budget permitting).
- [ ] 💲 If budget remains above the reserve, top up shipped tasks to full 5-run records.

Deliverables
- [ ] `CHANGELOG.md` complete: every phase, measured numbers, spend per phase, tradeoffs, honest failures.
- [x] `README.md` usage section: setup (`uv sync`, `.env`), `make` targets, running a batch, reading the report. Done: "Running this implementation" (setup, `make` targets, parallel/auto-calibrating batches, report).
- [ ] Final cleanup: remove dead code, check secrets aren't anywhere in history, all commits pushed.
- [ ] Final `make usage` recorded in `CHANGELOG.md` (total spend and remaining credit).

## Key tradeoffs (to document in the CHANGELOG)

- **Authoring harness.** The Harbor meta-task reuses terminus-2, logging and cost tracking, and matches how AfterQuery reviewers run tasks. The cost is no Docker inside the synthesis container, so real builds and oracle runs happen in the host gates and feed back through repair rounds. The fallback is the custom `docker exec` loop.
- **Repair vs regenerate.** Repair ≤2 rounds, then regenerate from the blueprint, since bad first drafts rarely recover (SkillSynth).
- **Verifier.** Keep the examples' verify-time `uvx` isolated interpreter (resists stdlib patching) and accept the network and latency cost. Revisit only if Phase 0 shows flakiness.
- **Turn cap.** `max_turns=200` caps runaway cost. A run that hits the cap is an *invalid* failure: rerun once, otherwise exclude the task.
- **Calibration rule.** Exact curtailment is lossless versus 5 full runs. An optional aggressive early-reject after 0/3 is reported only as a measured tradeoff, not used for shipping.
- **"Don't cheat" line.** Not in instructions by default (it shifts pass rates). Defense comes from the leak scan, red-team and pass audit.
- **Writing styles.** Meta-Task varies instruction styles for diversity, but the guideline paper favors terse instructions. We restrict to terse-compatible styles and let human-likeness scores decide.
- **Models.** Sonnet is used for authoring, blueprinting, judging and red-teaming, and Opus only for calibration. Using Sonnet as a judge or hacker is the only interpretation of the model rule we rely on, and it's noted explicitly.

## Verification

- `uv run pytest tests/`: unit tests for `decide()`, ledger and budget, lints, leak-scan extraction, sampler, blueprint schema, and the runner/artifacts parser on fixtures.
- `bash scripts/validate.sh output/<task>` passes for every shipped task.
- `harbor run -p output/<task> -a oracle` gives reward 1 (3/3) and `-a nop` gives 0, re-run independently of the pipeline for every shipped task.
- For each shipped task, the ledger shows its pass distribution and the judge labels for every trial, and `reports/summary.md` explains why the model fails it (valid failure modes only).
- Spot-check: rerun one shipped task 5× naively and confirm it lands in band (estimate reproducibility, budget permitting).
- Check that total spend in the ledger matches the gateway's reported usage, if the gateway exposes it.

## Critical files

- Already updated for the uv environment: `pyproject.toml`, `uv.lock`, `.python-version`, `scripts/*.sh`, `generator/requirements.txt`, `validator/requirements.txt`.
- Modify: `generator/generate.py`, `generator/config.py` (read `.env`, price table, budget), `pyproject.toml` (dependencies via `uv add`), `scripts/*.sh` (new entry points), `CHANGELOG.md`, `README.md` (uv-based usage section).
- Reuse: `validator/validate.py` (`validate_task()`), `generator/config.py` constants (`CANARY_LINE`, band params), `examples/*` (format reference only), the Harbor reward contract (`harbor/src/harbor/verifier/verifier.py`), `strip_canary` (`harbor/src/harbor/models/task/task.py`), Harbor `artifacts` collection (`harbor/trial/artifact_handler.py` in the installed package), and the `harbor check` / `harbor analyze` commands.
- New: `generator/{spec,blueprint,author}.py`, `generator/metatask/`, `validator/{lint,leak_scan,novelty}.py`, `evaluator/{harbor_runner,calibrate,redteam}.py`, `analysis/{judge,tuner,ledger,report,diversity,human_likeness}.py`, `scripts/run_batch.py`, `tests/`, `docs/research/README.md`.
