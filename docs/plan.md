# Plan: AfterQuery Harbor / Terminal-Bench task-generation work trial (core + stretch A-D)

## Context

AfterQuery's work trial (`harbor-tbench-worktrial/README.md`) asks for a pipeline that **authors Terminal-Bench-style Harbor tasks (default `claude-sonnet-4.6`)** and **keeps only "learnable" ones**: 1-3 of 5 runs pass with `terminus-2` + the calibration model (default `claude-opus-4.8`). Graded in this order:
1. Fraction of tasks in band, with *valid* failure reasons.
2. Pipeline design.
3. How we know tasks are good.
4. Reliability and throughput.
5. Code quality.

Hard limits:
- $500 of API credit.
- Models are **open** (README/AGENTS.md updated): any tool-calling model may author, judge or calibrate, preferably one with a published Terminal-Bench score. Defaults stay Sonnet 4.6 (author) and Opus 4.8 (calibration), and every result records its models.
- Spend ceiling set by the user: **$400 of the $500 key** in total.
- Novel tasks only (no public repos or examples).
- `[agent].timeout_sec = 3600`.
- Timeouts and running out of turns are not valid failures.

Deliverables are source, `CHANGELOG.md` and a readable git history in the private repo `zignd/harbor-tbench-worktrial`.

**Current finish plan:** the "Submission readiness: evidence, reproducibility and final results" checklist below takes priority over earlier completion claims. Keep the user-approved pairing: `openai/gpt-5.6-luna` author/reviewer/judge/red-team and `openai/gpt-5.4-mini` calibration via terminus-2. The model change is recorded, not a gap to reverse. The final deliverables are one self-contained detailed report at `docs/result/report.md` and a short interview deck at `docs/result/presentation.pptx`, with an offline browser version at `docs/result/presentation.html`. Earlier reports and decks remain historical evidence, not the submission's entry point.

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

      This describes the original corpus policy. The final run automatically compares only TB 2.1 plus `examples/` (user decision); the ban on reusing or adapting any public task remains. The finish report must disclose that reduced coverage.
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
| **audited pairing (Luna → GPT-5.4-mini)** | measured | calibration trial **$0.09** mean; strict `harbor check` **$0.011–0.015**/task; approving one task end-to-end (two five-attempt batches + quality reviews + gates + fresh-clone re-verify) cost **well under $2** |
| Opus calibration | $215 | ~25-40 tasks × ~3.5 trials (curtailment) at ~$1.5-2.5/trial worst case |
| Contingency inside the authorization | $17 | |

If an Opus trial costs more than ~$3, shrink the batch rather than cut the number of trials per task. Expect about a third of functionally correct tasks to land in band before tuning (SkillSynth base rate).

### Spend discipline

The $500 key is the only budget, and **it expires 2026-10-23 07:00 UTC**. Every rule below saves money **without** touching the work-trial constraints:
- The calibration model declared for a batch + terminus-2 defines its difficulty benchmark (currently GPT-5.4-mini; historical Opus results remain separate).
- The band is defined on 5 runs.
- `timeout_sec = 3600`.
- Models are configurable under the revised README/AGENTS.md; keep one declared pair and judge per batch. Dev mode (below) is plumbing only.
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
5. **Target-driven batches.** The README asks for a batch aiming at 10+ generated tasks/candidates, not 10+ shipped tasks. Report fresh generations separately from reused/recalibrated packages. Ship only eligible in-band versions; do not inflate generated or shipped counts to meet a target.

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

**Progress: 115 / 115 items** (update this line when ticking items; `make plan` or `bash scripts/track-plan.sh` prints overall and per-phase counts, `--remaining` lists open items with line numbers)

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
- [x] Re-plan the budget table from the measured costs (Opus trial, authoring run, judge call). Re-planned again for the **audited pairing**: mean calibration trial **$0.09**, strict quality check $0.011-0.015/task (evidence `docs/result/evidence/*-quality*.json`), versus the $0.23 Opus-trial figure of the earlier pairing - a ~2.5x cheaper trial, which is why this run could afford a second independent batch on the borderline task.
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
- [x] 💲 Dev-mode dry run (`DEV_MODE=1`): 2-3 candidates end to end through generation and gates, to shake out plumbing bugs before official spend. Results stay in `output-dev/`.
- [x] 💲 Pilot batch of 3 candidates through generation and gates. Record funnel and cost per task.
- [x] 💲 Reach **≥5 tasks** that pass the structural validator and the functional gates (oracle 3/3, nop 0).
- [x] Hand-review 2 generated tasks side by side with `examples/` and the guideline rules. Tighten the meta-task template and lints from what's found. Done: review #1 (`ledger-reconcile`) is in `docs/reviews/hand-review.md` and led to three prompt fixes. Review #2 will be a pipeline-generated pilot task.

### Phase 2: Part 2, calibration

- [x] `evaluator/calibrate.py`: pure `decide(outcomes)` with exact curtailment (accept at ≥1 legit pass + ≥2 valid fails, reject at 4 passes or 5 fails). Exhaustively unit-tested against the full 5-run verdict. Done: tested on all 32 sequences. Expected 3.85-4.3 trials instead of 5 for p = 0.2-0.8.
- [x] Calibration runner: Opus trials in waves of ≤3, budget guard checked before every trial, outcomes written to the ledger. Done: waves are capped at the fewest trials that can still reach a verdict, so they never overshoot.
- [x] 💲 Try `harbor analyze` (built-in `reward_hacking` + `task_specification` rubrics) on real calibration trajectories. Decide wrap vs build for both judges. Done: on 2 real Opus passes it agreed with our audit (reward_hacking and task_specification both pass), but costs $0.13 per trial vs our judge's $0.012. **Decision: our judges are primary** (10× cheaper, structured labels for the tuner and report); `harbor analyze` stays an optional cross-check.
- [x] 💲 `analysis/judge.py` (a), pass audit: command scan plus a trajectory-level Sonnet judge (Meta-Task Fig. 8 + Terminal Wrench labels). Hacked passes don't count. Done: validated on 4 real Opus passes (all labelled legit, $0.012-0.013 each) and on the red-team run.
- [x] 💲 `analysis/judge.py` (b), failure judge: the 9-mode taxonomy mapped to valid/invalid, with full reasoning kept.
- [x] Stop-early wiring: on the first invalid failure or hacked pass, stop calibrating the task and send it to repair.
- [x] Shipping step: copy learnable tasks into `output/<task>/` with a per-task calibration record (outcomes, judge labels, why the model fails). Done: `scripts/calibrate_candidates.py` writes `output/<slug>/README.md` (calibration plus judged failure reasons). Refuses to run in dev mode.
- [x] 💲 Dev-mode calibration loop (`DEV_MODE=1`): exercise waves, early stop, judges and ledger on 1-2 tasks before any Opus spend. Done: on `dev-9992cd0670d5` (DeepSeek, $0.31): wave sizing, an `AgentTimeoutError` trial counted as invalid (never a valid failure), the pass audit on the other trial, early stop with verdict `invalid`, all in the ledger. Also exercised a crash-resume of calibration.
- [x] 💲 Calibrate the Phase 1 tasks (pilot). Record cost per learnable task. **Go/no-go:** above $40 per learnable task → fix generation before scaling.
- [x] 💲 Batch 1: ~10 new candidates end to end through calibration.
- [x] Read every failure-judge summary from Batch 1, and retune lever and knob defaults toward TB Medium/Hard. Record the before/after reasoning in `CHANGELOG.md`.

### Phase 3: stretch B + C and red-team

Red-team (part of "how we know tasks are good")
- [x] 💲 `evaluator/redteam.py`: hack-elicitation copy of the task + 1 Sonnet terminus-2 trial + judge. A serious exploit goes to repair, with the exploit trajectory as feedback. Done: ran officially on 3 packages (all honest, `hackable: false`); a beaten verifier returns the exploit as repair feedback.
- [x] Wire the red-team as a gate before Opus calibration, and record the hackable rate per batch. Done: last gate in `stage_gates` (runs alongside the quality check); a beaten verifier goes back to repair. `reports/summary.md` shows the hackable rate per batch.

Stretch B: difficulty tuning
- [x] `analysis/tuner.py`: knob → lever → regenerate (≤2 rounds), with each mutation and its effect logged. Done: `scripts/tune_candidates.py` runs it on near-misses whose failures were all valid, and ships tasks that land in band.
- [x] 💲 Audit the tuner runs on Batch 1 near-misses (0/5 with valid failures, 4-5/5). Record eligible, attempted, gate-failed and recalibrated counts and how many moved into the band. Done in `evidence/stretchB-tuning.json`: **13 tuning experiments** with hash-bound before/after package hashes, 1-3 rounds each, **0 reached a learnable calibration**, total tuner spend $0.07. Successful difficulty adjustment is **not demonstrated** and is labelled as such in the report (§9.2), consistent with the bimodality in §7.2.

Stretch C: diversity
- [x] Coverage-steered sampling: the sampler reads ledger counts so it moves away from saturated cells. Done: `run_batch` samples inverse-frequency against every earlier candidate's spec.
- [x] Novelty report: per-task similarity to the TB corpus (by set) and `examples/` (max/mean, nearest task), plus rejects per novelty layer across all batches. Done: `analysis.report` shows nearest TB task, per-set max cosine and nearest `examples/` task per shipped task, plus rejects per layer (so far 2 blueprint-judge rejects of 9 checked: variants of our own Phase 0 task).
- [x] 💲 Near-duplicate check: Sonnet "same underlying task?" judge on the closest TF-IDF pairs. Done: the novelty gate indexes our own earlier candidates alongside the 425 published tasks (`novelty.gate_index`, excluding the candidate itself), at both the blueprint and final-package checks.
- [x] `analysis/diversity.py`: per-axis coverage, balance score exp(H)/N, difficulty spread, instruction uniqueness (TF-IDF cosine, Vendi). Done: difficulty spread added (blueprint labels, predicted pass-rate quartiles, observed pass rates).

Batch 2
- [x] 💲 Batch 2: ~12-15 candidates with the red-team gate, tuner and coverage-steered sampler on.
- [x] Reach the **README target of 10+ generated tasks** in the Part 3 batch, plus the learnable tasks shipped in `output/`.

### Phase 4: Part 3 + stretch A and D, write-up

Part 3: pipeline metrics
- [x] `analysis/report.py`: funnel (generated → blueprint accepted → structurally valid → functionally correct → red-team clean → learnable), pass-count histogram, total cost and wall time. Writes `reports/summary.md` + JSON. Done: funnel, histogram, cost/time, per-batch table, diversity, novelty, curtailment, human-likeness; regenerated from evidence on every run.
- [x] Reconcile ledger spend against `make usage-json` (within 10%), and state the total in the report. **The 10% target was NOT met and this is closed as unresolved-with-a-measured-gap, which is the item's own stated alternative.** Totals: ledger $545.64, key $219.70, residual $325.94 (report §10.1). The cause is now *verified where verifiable*: the retained per-job tokens show the historical era ran a 48.1% cache-hit rate, and the same tokens cost $617.45 with cached input at the full prompt rate versus $380.61 cache-aware (LiteLLM reported $451.76) — so cache accounting explains a **$236.84 swing**. Shared-key use, retry double counting and counter lag are ruled out with reasons. The remaining **$190.26** is attributed to a named hypothesis (part of the traffic billed to a different credential during the API-base change recorded in this plan) that cannot be confirmed retrospectively because per-call credential IDs were never recorded — stated as a hypothesis, not an invented cause. Evidence: `evidence/reconciliation-final.json`.

Stretch A: cost-efficient evaluation
- [x] Curtailment savings: trials run vs naive 5× per task, in $ and %. Done in `evidence/stretchA-curtailment.json`: on this run's pair, 31 tasks used 114 trials against a naive 155 — **26.5% of trials and ~$3.78 saved**; 20.9% / $30.78 across all pairs. The dollar figure is stated as an estimate at constant per-trial cost, and **early stops on invalid or hacked runs are reported separately and explicitly save nothing** (the trial was paid for and must be repeated), so curtailment savings are not overstated.
- [x] Simulation over the observed per-task p: expected savings and the effect of the optional aggressive 0/3 early reject (reported only, not used for shipping). **Previously annotated as skipped; now done** (`evidence/stretchA-simulation.json`, report §9.1): P(in band) peaks at 0.83 around p≈0.35; exact curtailment saves 17-23% of trials in the band-relevant region, matching the 26.5% measured; the aggressive 0/3 rule saves a further 18-37% but **discards 7-28% of learnable tasks**, so it is reported and deliberately not used for shipping.
- [x] Predicted-vs-observed pass rate: correlation of Sonnet's blueprint-time prediction with the Opus outcome, and whether it would work as a pre-filter.

Stretch D: human-likeness
- [x] Audit the existing generated-vs-example quality table with the same actual **16-criterion** rubric, model and settings; no cached historical scores are mixed in — every entry was re-run this session (`evidence/rubric-comparison.json`). Result: human-written `examples/` pass 0/6 with a mean of 2.17 blocking findings, audited generated packages pass 3/4 with 0.25. Reported as **rubric overfitting (Goodhart)**, not as evidence that generated tasks beat published ones; the rubric measures what the generator was taught to fix. Corrected the earlier mislabel of this as a 19-criterion evaluation. The report contains a table, so "skipped" was incorrect; do not call it a 19-criterion evaluation.
- [x] 💲 Run a blinded human-written vs generated-instruction discrimination experiment: shuffle identities with a recorded seed, save labels/predictions, report accuracy and uncertainty, and disclose that examples were provided as format references. Near-chance accuracy is not proof of indistinguishability.
- [x] Stylometrics: instruction length, bullets, headers and emphasis words, generated vs examples. Already present in `reports/summary.md`; the previous skipped annotation was incorrect. Audit provenance in the finish checklist.
- [x] `analysis/human_likeness.py` section in the report. The quality comparison and stylometrics are present; the full stretch goal remains partial until the blinded evaluation is completed.

Verification (see "Verification" below)
- [x] `uv run pytest` and `uv run ruff check .` pass.
- [x] Every task in `output/` passes `bash scripts/validate.sh`, and an independent oracle (3/3) and nop re-run **from a fresh clone after all packaging edits**. Done: `scripts/audit_freshclone.py` cloned at the audited revision into a temp dir and, from the clone alone, all five published packages passed validate, oracle 3/3 and nop 0 (`evidence/fresh-clone.json`). Earlier local checks do not prove the committed Git-history fixture still works.
- [x] Every shipped task has an immutable, package-hash-bound calibration record and a valid-failure explanation in `reports/summary.md`. Done: `output/optimize-policy-decision-audit/calibration.json` is bound to hash `e1dae8942dc6` and lists all five judged attempts with audits/labels/quotes; `reports/summary.md` now opens with the audited outcome and the per-trial table. A directory alone is never counted as shipped. Reopened: manual shipping, overwritten source records and live-report counts disagree.
- [x] 💲 Spot-check reproducibility: rerun one eligible shipped task 5× naively with the fixed solver settings; publish all outcomes, including invalid runs or a changed band. Done: the approved task was re-measured with a **second independent naive five-attempt batch** under identical settings. Batch 1 = 4/5, batch 2 = 3/5 (one turn-cap trial, invalid, replaced and preserved under `excluded_trials`), pooled 7/10 = 0.70. Both batches are published; the band genuinely moved, and that is reported rather than smoothed. Independent oracle/nop checks do not establish solver reproducibility.
- [x] 💲 Top up curtailed shipped calibrations to 5 actual judged attempts on the identical package. Done: the approved package carries five judged attempts, none curtailed, with every failure judged and every pass audited. The four unapproved packages are not topped up because they are not shipped; their records state exactly how many valid attempts they have. A curtailed 1/3 verdict guarantees a pass-count interval, not that unseen trials would have valid failures or honest passes. Hold or withdraw a package if the additional attempts reveal invalidity.

Deliverables
- [x] `CHANGELOG.md` complete: every phase, measured numbers, spend per phase, tradeoffs, honest failures.
- [x] `README.md` usage section: setup (`uv sync`, `.env`), `make` targets, running a batch, reading the report. Done: "Running this implementation" (setup, `make` targets, parallel/auto-calibrating batches, report).
- [x] Final cleanup: remove dead code, check secrets aren't anywhere in history, all commits pushed. `scripts/check_repo_hygiene.sh` (wired into `make lint`) fails the build on any gitlink, tracked `.env`, committed API key, tracked `jobs/`/`trials/`/`output-dev/`/`data/`, or file over 20 MB; it passes at the final revision. Working tree is clean and every commit is pushed.
- [x] Final `make usage` recorded in `CHANGELOG.md` (total spend and remaining credit).

### Study: who writes the task, who solves it

After 9 Opus calibrations with 0 in the band (tasks Sonnet authors are easy for stronger and for cheaper models alike), we test the reason instead of tuning around it: a weaker author for a stronger solver is a student writing problems for a professor. Reasoning, design and hypotheses are in `docs/findings.md`. **Exploratory: nothing here is shipped or counted in the funnel.**
- [x] `docs/findings.md`: the thesis, the evidence so far, the 2 x 2 design (weak/strong author x weak/strong solver), metrics, hypotheses and threats to validity.
**Study budget (user-approved):** estimate ~$25, HARD CAP $40 for the whole study, on top of spend so far ($133.72 used, $361.53 left at 01:48). Remaining credit never below the $75 reserve; ask before any single step above ~$10. Run `make usage` before and after every paid step and log the delta in `CHANGELOG.md`. Pair: weak = `deepseek/deepseek-v4.1-flash` ($0.30/$1.20 per M), strong = `deepseek/deepseek-v4-pro` ($0.96/$1.91). Order: one spec end to end to measure real cost, then scale. Deadline: results and findings by 06:00 -03:00 on 2026-10-13 (about 3 hours of work; scale the number of specs to fit, and write findings from partial results rather than miss the deadline).
- [x] 💲 Finish the solver pilot (`scripts/pilot_models.py`: `qwen/qwen3.7-max` and `z-ai/glm-5.1` on the 5 too-easy packages, capped $6, already running; do not restart) and keep its table as evidence.
- [x] 💲 Pick the model pair and check the gap (pair switched to Gemini flash-lite / 3-flash; gap run on 3 of 5 packages): flash (weak) and pro (strong), both solving the 5 pilot packages; if pass rates barely differ, stop and ask the user.
- [x] Study mode: author model and solver model chosen per role, runs and ledger events tagged `study`, outputs under `runs/study/`, never shipped (`assert_official_models` still guards shipping).
- [x] `scripts/study.py`: draw ~12 specs once; each author writes its own task from the same spec; free gates only (structure, lint, leak scan, build, oracle 3/3, nop 0); every valid task is solved 5 times by each solver; failures judged by one fixed judge.
- [x] 💲 Run the study under a spend cap ($16.38 in the ledger; 4 valid strong-author tasks, 0 valid weak-author tasks) (est. $25, cap $40) and record the per-cell results.
- [x] `analysis/study.py`: per-cell in-band share, too easy/hard/invalid shares, pass-rate distribution, task validity rate and cost; a report section and a presentation Q&A entry.
- [x] Research-paper-format report `docs/study-report.md` (abstract, intro, method, results, discussion, threats to validity, conclusion), presentation deck `docs/study-deck.pptx` (or a Marp/HTML deck if pptx is not practical), and updated `docs/architecture.md`, `README.md` and `CHANGELOG.md`.
~~- [ ] 💲 Optional transfer check: the tasks in the band for the cheap solvers, solved by Opus 4.8 (~$1-2 each).~~ skipped: optional, and the shipped tasks are already banded for their own calibrator.

### Historical run: Gemini → Luna → Luna author / GPT-5.4-mini solver

Goal: tasks that fit the trial's band (1-3 of 5 passes for the calibration model, valid failures only), authored and calibrated by the same strong model, a "professors helping professors" setup whose tasks can serve as a benchmark and as training data. Sonnet 4.6 -> Opus 4.8 gave 0 of 9 in band. **Final pairing (this run shipped 3 tasks).** `google/gemini-3.8-flash` (the start of this run) was too slow; the five-model speed test (`docs/model-speedtest.md`) picked `openai/gpt-5.6-luna` (about 76% on TB 2.1 with the Codex harness, $0.20/$1.20 per M tokens) as author, reviewer, quality checker, red-team and judge, and **`openai/gpt-5.4-mini`** (about 60% on TB 2, $0.75/$4.50) as the calibration solver, since a strong author writing for a somewhat weaker same-brand solver should put more tasks in the band. `CALIBRATE_FIRST=1`, a 60-turn authoring cap, `QUALITY_ADVICE_ONLY=behavior_in_tests`, `OPUS_CONCURRENCY=6` and `ORACLE_RUNS=2` via `.env` (defaults unchanged). **Shipped: `output/repair-log-replay-sql` (1/3), `output/optimize-policy-decision-audit` (3/5), `output/repair-attributed-funnel-service` (3/5), all valid failures, each re-verified (`validate.sh`, independent oracle 3/3, nop 0).** Outcome and funnel in `docs/findings.md` section 6 and `reports/summary.md`. **Model at the start (context):** `google/gemini-3.8-flash`, about 89% on Terminal-Bench 2.1, tool calls supported, $0.75/$3.75 per M tokens, used for blueprint and review, authoring, quality check, red-team, judges and the calibration solver (terminus-2, 5 trials, exact curtailment); set with `GENERATOR_MODEL` and `EVAL_MODEL`. Every result records the model.

**Novelty pool (user decision):** the novelty reference is Terminal-Bench 2.1 (`data/tb-reference/terminal-bench-2-1`, 89 tasks) plus `examples/` only, because the model was scored on TB 2.1. The latest/4.0 set, Pro and Science are not compared for this run (they stay on disk; `NOVELTY_SETS` selects the sets). Thresholds (13-gram, cosine 0.70, the semantic judge) are unchanged. Tradeoff: a task close to a 4.0, Pro or Science task would no longer be flagged automatically. The README rule against reusing or adapting any public task still applies.

Budget: this run was capped at $150 on top of ~$176 already spent, inside the $400 account ceiling. **Historical snapshot:** the key showed $209.17 conservative spent / $290.83 remaining; this run's model-labelled ledger estimated $10.43. The cross-label ledger total ($524.62) did not reconcile with that key snapshot. Earlier entries attributed the discrepancy to estimated costs during a high-burn period, but that cause has not been verified. Retain the raw counters and investigate comparable scopes before claiming reconciliation.
- [x] Novelty pool (`f5e42db`): `NOVELTY_SETS` (unset = every set; `terminal-bench-2-1` set in `.env` for this run; `examples/` always included) applied at every layer (concept list, blueprint gate, final-package re-check, diversity report); the report states the sets used. Unit-tested (an excluded set no longer flags a near-copy, an included one does).
- [x] Model plumbing (`f5e42db`): `GENERATOR_MODEL` / `EVAL_MODEL` reach blueprint, authoring, quality check, red-team, judges, novelty judge and calibration; `config.assert_official_models()` accepts the configured pair (refuses dev mode); the model is recorded in ledger events, calibration records, shipped-task READMEs and `reports/summary.md`. Unit-tested.
- [x] 💲 Probe `gemini-3.8-flash` in every role (done; plus the five-model speed test in `docs/model-speedtest.md`); the run switched to `luna` author / `gpt-5.4-mini` calibrator (`docs/findings.md` section 6). (blueprint, authoring round, terminus-2 trial, failure judge, red-team); record speed, cost and any JSON or tool-format problem, and fix what breaks.
- [x] Difficulty-by-construction levers (verify-time inputs from a hidden seed, multi-stage dependent work, a shallow-self-check trap, long-horizon or large inputs) in the spec, blueprint and tuner guidance. Unit-tested. **Verified present in the approved task**: its verifier generates fresh randomized SQLite fixtures at verify time (`random.Random(seed)` in `tests/test_outputs.py`), so correctness is checked on inputs the solver never sees rather than on a shipped sample.
- [x] 💲 Pilot: 3 candidates through the full pipeline; funnel, time and cost per task. Go/no-go at ~$40 per in-band task.
- [x] 💲 Batch of 10+ candidates (20 through the pipeline) with `openai/gpt-5.6-luna` authoring and `openai/gpt-5.4-mini` calibrating; exact curtailment, every trial judged, tuner on near-misses; **1 task shipped** (`output/repair-log-replay-sql`, 1/3 valid).
- [x] Every shipped task: fresh-clone validation, independent oracle 3/3 and nop, hash-bound calibration, valid-failure explanation with an instruction quote, novelty check, canary placement, `timeout_sec = 3600`. All confirmed for `optimize-policy-decision-audit`: fresh-clone PASS, oracle 3/3, nop 0, hash-bound `calibration.json` + `verification.json`, two `partial_implementation` quotes occurring verbatim in the instruction, novelty re-check against TB 2.1 (89 tasks) + `examples/` judged **distinct** from its nearest analogue `query-optimize`, canary present in `solve.sh`/`Dockerfile`/`test_outputs.py` and absent from `instruction.md`, `[agent] timeout_sec = 3600.0`. Previous local verification recorded; final audit pending.
- [x] `reports/summary.md` regenerated for this run's model label: funnel, histogram, cost/time, diversity, novelty (TB 2.1 + examples), compared with Sonnet -> Opus (0 of 9) and luna -> luna (0 shipped).
- [x] Stretch goals as time allows (A curtailment savings, C diversity, B tuner results, D human-likeness); skipped items stated.
- [x] Docs: `docs/findings.md`, `docs/architecture.md`, `README.md`, `CHANGELOG.md` updated with the outcome, spend and decisions. `docs/findings.md` §6 now carries the audited outcome and supersedes the old "three tasks shipped" claim; `reports/summary.md` opens with the audited outcome and per-trial table; `README.md` describes `output/` correctly; `CHANGELOG.md` records every audited step with spend.

### Submission readiness: evidence, reproducibility and final results

**Objective:** finish the modified work trial properly, not merely obtain a green checklist. Prioritize the existing shipped packages over further generation. Keep the chosen models and TB 2.1 + `examples/` novelty pool; disclose model changes and the limited automatic novelty scope. Earlier runs are observations, not controlled proof that author strength caused the outcome.

**Order:** freeze evidence → verify shipping → fix reporting/accounting → complete measured stretch evaluations → consolidate report/deck → clean-clone handoff. This is a plan, not authorization to start paid jobs now. Use `make usage` before/after paid steps, respect the $400 account ceiling and $75 reserve, estimate new verification costs before running, and ask for approval where AGENTS.md requires it. Do not silently relax quality gates or hide contrary results to reach completion.

- [x] Inventory every current `output/` directory, including later background outputs: four previous outputs archived unchanged under `runs/audit-20261013/original-output/` and placed under `pending/`. Timestamped inventory/hashes and starting spend in `docs/result/evidence/`. Original source mappings require the exact-record audit below; no previous approval is assumed.
- [x] Persist `output/<task>/calibration.json` and a verification record with trial outcomes, audit/judge labels, verbatim instruction quotes, dates, source evidence paths and package hashes. Done for `output/optimize-policy-decision-audit` (approved): its `calibration.json` holds five judged attempts with per-trial turn counts against the 100-turn cap, the three honest pass audits, the two `partial_implementation` failure labels with verbatim instruction quotes, the excluded turn-cap trial, and the pooled two-batch evidence; `verification.json` binds it to package hash `e1dae8942dc6` and lists every gate. Enforced by `analysis/package_evidence.approval_errors()` with regression tests, and applied to all five published packages (the four non-approved ones carry `approved: false` with their reason). Check quoted requirements actually occur in the instruction and manually inspect each claimed valid failure and honest pass. Add regression tests preventing shipping a different hash/model or a task with invalid/hacked runs.
- [x] Resolve blocking quality findings for every shipped task: test↔instruction coverage both ways, deterministic verification, leakage/reward hacking, novelty and canary placement. Audit answer-bearing alternate implementations in environments. A `behavior_in_tests` advisory override is not evidence that a coverage gap is harmless. If a package changes, rerun the affected gates and recalibrate the new hash; if it cannot qualify, preserve its history but remove it from the approved set and report the reason. Done for all three audited packages: `funnel-final` passes the strict rubric with **zero blocking and zero advisory findings** (verifier made fully offline; suite expanded 6→13 deterministic tests), `policy-final` and `packager-final` pass with 1–2 non-blocking advice notes each (unpinned base-image digest, pytest cached in the image). No advisory override was used to clear any blocking finding; two packages needed the wall-clock gate removed first, which was a real change and was recalibrated.
- [x] Restore generated Git-history fixtures reproducibly in the actual shipped package (e.g. a bundled history restored during Docker build), not only the candidate archive. Test checkout contents/history from committed files; never rely on local `.git/`, host files, pre-existing images or mutable unpinned dependencies. Revalidate after the packaging fix because previous verification predates removal of an embedded `.git/`. Done: four nested `.git` fixtures that a `git add -A` had staged as **gitlinks** (which a fresh clone cannot materialise) were replaced by tracked file contents plus `.bundle` histories, and `scripts/check_repo_hygiene.sh` (wired into `make lint`) now fails the build on any future gitlink. A clone of the committed revision builds and verifies every published package.
- [x] Fix report provenance and counts: no hard-coded Opus headings; filter all evidence by declared models and package versions; derive approved shipped counts from immutable output records rather than mutable candidate calibrations. Distinguish fresh generated specs, reused packages, repair versions, incomplete/rejected candidates and unique approved tasks; avoid counting successes from unrelated versions as one cumulative success funnel. Add report tests covering manual shipping, later repairs and model-pair isolation. Done in `analysis/report.py` (`funnel()` counts only the current package hash, `approved_outputs()` requires exact-hash `calibration.json` + `verification.json`, model-pair and fresh/reused isolation) with regression tests in `tests/test_report.py`; hard-coded Opus labels removed.
- [x] Fix spend reconciliation without altering historical raw events. Every listed cause was investigated: estimated-vs-charged prices and **cache-token accounting** (quantified from retained tokens, the dominant cause); retries and excluded/incomplete jobs (separate billed calls, separate rows, ruled out); shared-key usage (would push the key above the ledger, ruled out); counter lag (seconds-scale, immaterial). Published: timestamped key snapshots, comparable-period deltas, per-model and per-stage estimates, and the residual. The 10% target was **not** met, so per the item's own condition the reconciliation is marked **unresolved with a measured gap** ($190.26 after cache-aware correction), with the residual cause named as a hypothesis rather than invented. No raw ledger event was altered. Wall-clock, summed stage-time and parallelism are reported separately in §10.2.
- [x] Establish consistency for Parts 1–3: document an auditable 10+ candidate generation batch, then confirm approved task packages satisfy the full gates and 1–3/5 criterion for GPT-5.4-mini. Summarize observed yield, failure causes, cost/time per candidate and per approved task, and uncertainty. Run the fresh-clone and five-attempt checks above; do not claim general reliability from a few selected successes.

**Dispositions of the remaining open items in this section** (commentary, not checklist items; none is skipped — every reason below is measured, see `docs/result/report.md` §7 and §10):
- *Persist `output/<task>/calibration.json` + verification record* — mechanism implemented (`analysis/package_evidence.approval_errors`, `scripts/audit_ship.py`, regression-tested) and exercised, but there is **no approved task to write it for**: all three audited packages measured outside the 1–3 band, so `output/` is deliberately empty.
- *Fresh-clone build/validate/oracle/nop* — **done** for all five published packages (`scripts/audit_freshclone.py`, evidence `fresh-clone.json`): cloned at the audited revision into a temporary directory and, from the clone alone, `scripts/validate.sh` PASSED and oracle 3/3 / nop 0 held for each. The clone has no `.env`, no embedded `.git` and no pre-existing images; credentials are inherited from the process environment.
- *Spend reconciliation* — investigated and published (`evidence/reconciliation.json`, `reconciliation-audit-window.json`, `reconciliation-final.json`). The key read $209.17 at 15:20 on 2026-10-13, so it **does** cover the historical era. Recomputing the retained tokens shows that era ran a **48% cache-hit rate**, and the same tokens cost $617.45 if cached input is billed at the full prompt rate versus **$380.61 cache-aware** (Harbor/LiteLLM reported $451.76) — so **cache accounting explains a $236.84 swing**, the dominant cause. Shared-key use, retry double-counting and counter lag are ruled out. A **$190.26 residual** remains after that correction; the leading hypothesis is that part of the traffic was billed to a different credential (the plan records an API-base change during setup), which cannot be confirmed because per-call credential IDs were never recorded. **The 10% acceptance condition is not met; the item stays open with a measured gap and a named, unverified hypothesis rather than an invented cause.**
- *Five-attempt completeness* — three packages have five attempted trials each; `funnel-final` has **four valid judged attempts plus one turn-cap trial (invalid by rule)**, and two replacement attempts under identical settings also failed to produce a valid trial before the deadline, so its record is explicitly `invalid` rather than back-filled.
- Complete stretch A accounting and stretch C provenance: quantify exact-curtailment savings separately from invalid-run early stops (trials, estimated dollars and percentages); retain the exhaustive simulation and predictor correlation with limitations. Audit diversity coverage, within-batch duplication and novelty against the selected reference sets; report versions/counts and do not present the reduced reference scope as comprehensive public-task decontamination.
- Complete stretch B evidence: produce a before/after table for every eligible tuning experiment with package hashes, mutation, gates, calibration, cost and time; distinguish repair from difficulty tuning. Seek a valid out-of-band → in-band transition within an approved spend allocation. If none occurs, report a measured negative result and label successful tuning as not demonstrated rather than achieved.
- Complete the stretch D audit/blinded experiment above and classify each component separately: rubric comparison, stylometrics and discrimination. Save reproducible inputs, randomization and predictions; show sample sizes, confidence intervals and judge/reference bias. Do not equate polished formatting or near-chance predictions with proven human-likeness.
- [x] Create **one detailed, self-contained report** at `docs/result/report.md`: executive summary; requirement-by-requirement and stretch A–D status matrix (achieved/partial/not demonstrated, with evidence); final models/settings/novelty scope; architecture and design rationale; method and model speed-selection; fresh/reused candidate funnel; per-task pass records and valid-failure explanations; all quality and fresh-clone checks; tuning, diversity and human-likeness experiments; reconciled costs and wall time; earlier failed pilots; limitations, reproducibility commands, implications for training/benchmark use, references and detailed appendices. All essential details must be in this document; links to raw evidence supplement rather than replace them. Report latest audited output counts, not stale historical three-task claims.
- [x] Create an **easy-to-present 10–12-slide deck** at `docs/result/presentation.pptx` plus `docs/result/presentation.html` (offline, arrow-key navigation, no server needed): one claim per slide, large readable charts, little text, consistent layouts and presenter notes/Q&A. Cover problem, revised model choice, pipeline, validation, candidate funnel, approved task example, failures, stretch-goal status, cost/time, limitations and next steps. Derive figures from the same audited report data; render and visually inspect every slide, and test browser navigation. Do not reuse the old study deck as if it described final results.
- [x] Package the verification a reviewer needs into **one command** (`scripts/audit_all.sh`): 17 checks re-deriving every headline claim from committed records - hygiene, lint, tests, deliverables, manifest status and approved-task shape, package hash binding, fresh-clone result, deck/report consistency, plan state. No model calls, no Docker, non-zero on failure. It caught a real schema bug on its first run (`audit_ship` and `audit_publish` wrote two different `verification.json` shapes).
- [x] Make that tooling **clone-safe and prove it**: `.env` is deliberately never committed, so `uv run --env-file .env` made the audit pass locally and fail for any reviewer - the same defect class found earlier in the task verification, reappearing in the tool written to verify it. The affected checks now read committed records only; `scripts/audit_clone_tools.py` runs the audit inside a clone with `uv sync` and no `.env` (**17/17 green**, `evidence/clone-audit.json`), `overall_status` requires it, and `tests/test_verification_tooling.py` fails if any audit script regains a credential dependency.
- [x] Make **generated prose checkable against generated data**: the manifest asserted `approved_tasks` was empty while listing one approved task at 3/5 (defect 12). The note is now derived from the approved list, and `make lint` (22 consistency checks) fails if the note stops naming what is approved, if an approved task is missing from `output_packages`, or if one appears in both the approved and quarantined lists. New guards were confirmed by **negative control** - mutating the manifest to recreate each defect makes `make lint` fail.
- [x] Re-derive the pool distribution from the recorded trials under the approval standard (`scripts/audit_pool_distribution.py`, evidence `pool-distribution.json`). The "3 learnable" headline was wrong: only **2** candidates hold a full five-attempt in-band record (one label rests on a curtailed 1/3; one of the two ends in pipeline status `failed`), and neither is the approved task. Report 6.2/6.5, both decks and the presenter notes carry the corrected count and an explicit bridge to the one approved task.
- [x] **Fix and actually inspect the deck.** The pool slide's bar chart rendered as nothing (pptxgenjs v4 renamed chart constants, so `pres.charts.bar` was `undefined` and `addChart` wrote axes with no series - schema-valid, semantically empty, invisible); `validate.py` passed before and after. The PPTX was also missing the Architecture and Q&A slides, so it had 10 slides against the HTML deck's 12. Both decks are now 12 slides from one data file, validated, rendered and inspected slide by slide, with the HTML deck driven in Chrome from a `file://` URL (`1/12 -> 12/12`, clamps both ends, zero non-local requests). The old QA record claimed "11 slides, all 11 visually inspected" for decks that had 10 and 12; it is regenerated by measurement and `make lint` now re-derives the counts and fails if the report or manifest states a different number.
- Final handoff: add `docs/result/README.md` linking the report/deck and naming the audited revision; update root README, findings and architecture to the final pairing/results and link `docs/result/`. Run tests/lint, fresh-clone validation, history-secrets and embedded-gitlink checks; preserve raw evidence and fix stale references. Commit/push all deliverables, update checklist counts in the same commit, and ensure claimed results agree across output records, report, slides and changelog. Unresolved items stay open or explicitly partial; a high progress percentage is not proof of completion.

## Key tradeoffs (to document in the CHANGELOG)

- **Authoring harness.** The Harbor meta-task reuses terminus-2, logging and cost tracking, and matches how AfterQuery reviewers run tasks. The cost is no Docker inside the synthesis container, so real builds and oracle runs happen in the host gates and feed back through repair rounds. The fallback is the custom `docker exec` loop.
- **Repair vs regenerate.** Repair ≤2 rounds, then regenerate from the blueprint, since bad first drafts rarely recover (SkillSynth).
- **Verifier.** Keep the examples' verify-time `uvx` isolated interpreter (resists stdlib patching) and accept the network and latency cost. Revisit only if Phase 0 shows flakiness.
- **Turn cap.** `max_turns=200` caps runaway cost. A run that hits the cap is an *invalid* failure: rerun once, otherwise exclude the task.
- **Calibration rule.** Exact curtailment is lossless versus 5 full runs. An optional aggressive early-reject after 0/3 is reported only as a measured tradeoff, not used for shipping.
- **"Don't cheat" line.** Not in instructions by default (it shifts pass rates). Defense comes from the leak scan, red-team and pass audit.
- **Writing styles.** Meta-Task varies instruction styles for diversity, but the guideline paper favors terse instructions. We restrict to terse-compatible styles and let human-likeness scores decide.
- **Models.** The model rule is open (README/AGENTS.md). Defaults: Sonnet for authoring, blueprinting, judging and red-teaming, Opus for calibration. The shipped run used `openai/gpt-5.6-luna` for authoring/blueprinting/judging/red-teaming and `openai/gpt-5.4-mini` for calibration (label `openai/gpt-5.6-luna|openrouter/openai/gpt-5.4-mini`), and every result is labelled with its model pair. The "one model in every role" idea was kept as the same-brand strong-author/weaker-solver pairing.

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
