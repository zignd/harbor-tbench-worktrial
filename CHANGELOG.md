# Changelog

What we did, why, and the design tradeoffs. Newest first. Each entry is stamped `### HH:MM ±HH:MM · Title` under its `## YYYY-MM-DD` day: local time with its UTC offset, taken from when the change was committed. Spend figures come from `make usage` (OpenRouter `/api/v1/key`).

## 2026-10-12

### 22:24 -03:00 · Malformed model JSON no longer sinks a candidate
- **7 candidates of the 12-wide batch crashed** with `JSONDecodeError` within minutes. Under parallel load, Sonnet's blueprint and review replies sometimes held two JSON objects ("Extra data") or trailing commas. The parser took one greedy `{...}` span and parsed it strictly, so one bad draft out of four parallel ones crashed the whole candidate (~$0.6-0.8 of drafts each).
- **`extract_json`** now scans for the first `{` that starts a decodable object (prose before it or a second object after it don't matter) and retries each position with trailing commas removed. This applies to every judge and reviewer, since they all share the parser. Tested on prose + trailing commas, two fenced blocks, and a non-JSON brace before the real object.
- **A draft whose reply still can't be parsed twice** becomes a skipped draft (logged as an `error` event), not a crashed candidate.
- **Evidence fix:** every draft in a round is saved, including those after the accepted one: `blueprint_rejected_<n>.json`, or `blueprint_unused_<n>.json` for a second accepted draft. Before, drafts after the accepted one were dropped.
- The 7 crashed candidates were reset and re-run. 123 tests pass.

### 22:09 -03:00 · More parallelism: parallel blueprint drafts, gate slots, eager calibration, automatic tuning
1. **Parallel blueprint drafts.** The difficulty review rejects most drafts (7 of 8 in the first validation batch), and up to 4 sequential tries took ~8 min per candidate. `stage_blueprint` now drafts and reviews `BLUEPRINT_DRAFTS` (4) at once and keeps the first accepted. If none passes, the next round gets every rejection reason (`BLUEPRINT_ROUNDS` 2, so up to 8 drafts). Every rejected draft is still saved as `blueprint_rejected_<n>.json`.
2. **Wider batches with a machine-wide gate cap.** A 12-candidate batch runs with 10 workers. Authoring is API-bound (containers idle at ~0% CPU), but the image build + leak scan + oracle ×3 + nop are CPU-heavy, and a CPU-starved oracle looks flaky. That block now holds one of `GATE_CONCURRENCY` (3) machine-wide slots. The flock slot lock is shared with Opus trials (`evaluator/slots.py`).
3. **Eager calibration** (`CALIBRATION_EAGER`, default on): every remaining trial runs in one wave, and `OPUS_CONCURRENCY` goes 3 → 5. Each task container is capped at 1 CPU, so 5 trials use at most 5 of Docker's 10. The verdict is the same as with exact-curtailment waves, which never pay for a trial that can't change it (`CALIBRATION_EAGER=0`). The tradeoff is more trials for a faster wall clock. The report still computes what curtailment would have saved, from the full 5-run records.
4. **Automatic tuning:** `run_batch --calibrate --tune` sends a too-easy or too-hard task straight into the tuner (`tune_one`, up to 2 rounds, with round history) in the same worker, and ships it if it lands in band.
- **Memory:** the host has 36 GB but was already compressing heavily (44% free), while containers used 0.6 GB of Docker's 14.6 GB. So Docker's memory was **not** raised. A watcher logs host-free % and container memory every minute (`jobs/memwatch.log`) and alerts below 20% free or above 11 GB.
- Running batches were restarted on the new code: seeds 2 and 4 (`8a6e`'s calibration resumes from its finished trials), plus the new seed-5 batch (12 specs, 9 domains, 6 languages, mostly the new levers).
- 122 tests pass (new: parallel drafts keep one accepted and record the rest, eager wave sizes). Dry run with `--calibrate --tune`: 2/2 gated.

### 20:54 -03:00 · Validation batch: the review rejects 7 of 8 blueprints; generator self-checks
- **First validation batch (4 specs, new levers):** the stricter review rejected 7 of 8 blueprints (two tries each, ~$0.30 per rejected candidate, no builds). The reasons repeat the old failure in new clothes: the generator claims an investigation-heavy lever but puts the defect in readable source. Examples: an "opaque" cipher shipped with its `decrypt.go`, "profiling needed" where the bad call site is visible, speedruns of 9-15 commands. One more was rejected as a variant of our own `93f5`. **1 accepted:** `sensor-rollup-calibration-fix` (genuine_difficulty 4), now being authored.
- **The review gate is cheap, so the generator gets more tries:** `BLUEPRINT_TRIES` 2 → 4. A blueprint costs ~$0.13 and a build ~$4-6, so even 1 in 8 accepted is ~$1 per accepted blueprint.
- **The generator runs the speedrun on itself** before answering, and redesigns if ≤ ~20 commands would work. A lever has to be real in the environment (an opaque component ships as a binary or black-box service, never next to its source).
- Retries continue numbering after earlier rejections, so `blueprint_rejected_<n>.json` evidence is never overwritten. The 3 rejected candidates were re-queued under the new logic.

### 20:48 -03:00 · Go/no-go: fix generation (difficulty) before scaling
**The numbers:** $113.92 spent (`spent*`), 0 learnable tasks. Every calibrated task was too easy:
- `ledger-reconcile`: 4/4, 4/4, 4/4 (original + 2 tuning rounds).
- `2f50` C audit service: 4/5 (tuning round 1 failed the quality gate twice).

Under the plan's rule (more than $40 per learnable task → fix generation before scaling) that's a no-go for scaling. The user approved: finish what's nearly done, start nothing new, retune generation for difficulty, then run a small validation batch.

**Diagnosis:** all three too-easy tasks share one shape, "a few bugs in readable source". Opus reads the code, spots each bug and patches it in 9-25 commands. The blueprints predicted a 25% pass rate; the observed rate was 80-100%. The blueprint review scored their `genuine_difficulty` 4-5, so it wasn't predictive.

**Changes:**
- **Blueprint prompt:** cites the measured results, says that bugs visible by reading are not difficulty however many there are, and requires at least one source of difficulty that reading can't shortcut:
  - causes that only show when the system runs on data or history;
  - substantial construction checked on hidden inputs;
  - a stated quantitative bar;
  - a long ordered procedure where an early mistake silently corrupts later steps;
  - domain reasoning that is subtly wrong on unseen cases.

  It also asks for predicted pass rates calibrated against that evidence.
- **Four new levers** for those sources: `observe_not_read`, `build_component`, `opaque_component`, `ordered_procedure`. They have zero history, so the inverse-frequency sampler favours them.
- **Review "speedrun":** the reviewer writes the shortest plausible command path to a solution and counts the commands. A path of ~20 or fewer caps `genuine_difficulty` at 2, and acceptance now needs `genuine_difficulty ≥ 4` (`MIN_DIFFICULTY`), enforced in code. The review's token budget went 2000 → 4000, because the speedrun list truncated the JSON on the first try.
- **Validation of the review before spending** (`review_validation` events, ~$0.22 total): it rejects both known too-easy blueprints (speedruns of 13 and 7 commands), and it rejects **all 8 in-flight candidates** it could check (difficulty 2, speedruns of 9-18 commands).
- **In-flight builds stopped:** the plan was to let in-flight candidates finish, but with every one predicted too easy, more repairs and calibrations (~$20-30) would mostly confirm "too easy". They're marked `stopped` with the reason, and their evidence stays on disk. **Exception:** `1091` (WAF rule sync, which had passed its quality check) finishes its gates and is calibrated, to test the review's negative prediction (~$3). Batch 2's 4 unstarted specs are `held`.
- **Resume gap fixed:** an attempt interrupted after authoring (package hash on the author event, or on its first gate event) now goes straight back to its gates. Before, `3bbd` re-authored a package that had already passed oracle/nop (~$1.5 wasted).
- **Leak scan:**
  - the file-name search was unpruned and ran 19 min on a Rust image, and its container outlived the CLI timeout. It now reuses the pruned directory list, and both searches run under an in-container `timeout 300`, so the container always exits. A real scan of `2f50` takes 2.3 s.
  - `0cd6` had errored on exactly this timeout.
- 120 tests pass.

### 20:08 -03:00 · Repo hygiene: no vendored deps in git or tasks; leak-scan cache false positive; dev calibration loop done
- **Vendored third-party code was getting into the repo.** One Batch 2 Rust package vendored **68 MB** of crates (`framecodec/vendor/`, not yet committed), and a Node package's 553 `node_modules` files were already committed. The generator didn't write that code, it's reproducible from the lockfiles, and it bloats the repo AfterQuery clones.
  - `.gitignore` now excludes `node_modules/`, `vendor/`, `target/` and `__pycache__/` inside `runs/candidates/`, and the committed `node_modules` files were untracked. They stay in history, since rewriting it would need a force-push.
  - The authored packages, `failed_a*` repair snapshots and `before_tune_*` snapshots stay committed: they make the repair and tuning history auditable, and they total ~5 MB.
- **Vendoring is also a cost and quality problem:** `harbor check` reads the whole environment, so that `node_modules` tree made one quality check cost **$2.24** instead of ~$0.13.
  - Lint now rejects vendored dependency dirs (`node_modules`, `vendor`, `site-packages`) and environments over 20 MB.
  - The meta-task instruction says to commit the lockfile and fetch pinned versions in the Dockerfile.
- **Leak-scan false positive:** test tokens "matched" files in pip's HTTP cache (`/root/.cache/pip/http-v2/...`). Package-manager caches (`/root/.cache`, `.npm`, `.cargo/registry`, `go/pkg/mod`) are now pruned from the scan.
- **Dev-mode calibration loop: done** on the dev package (DeepSeek, $0.31). One trial hit the 60-min agent timeout and was counted **invalid**, never a valid failure. The other passed and was audited, and calibration stopped early with verdict `invalid`. It also exercised crash-resume. Progress 57/83.
- Seen in the gates: the novelty judge (now seeing our own nearest tasks) rejected Batch 1's `48eb` package as a variant of one of our tasks. Rust `aac9`'s oracle failed 0/3 because `solve.sh` doesn't leave the service running (repair feedback). Its vendored crates also triggered dozens of vendored-code findings.
- 118 tests pass.

### 19:55 -03:00 · First task through every gate; checklist catch-up (56/83)
- **`2f50` (C audit service, Batch 1) passed every gate** after 3 attempts: two repairs for answer tokens leaked into image files. It is the first pipeline-built task to get there and is now calibrating. It's a Phase 1 task, so its result goes into the pilot go/no-go number (cost per learnable task). Batch 2 calibration still waits for that decision.
- **Migration to the new code:** 5 of 6 old processes moved at attempt boundaries (`ae2e`, `1091`/`3bbd`, `48eb`, `93f5`), and one finished on its own. Cost: `3bbd`'s in-progress quality/novelty/red-team gates restarted, with no authoring lost.
- **Ticked 5 finished items:** red-team wired as a gate with hackable rate per batch, the novelty report, `diversity.py` difficulty spread, `report.py`, and the README usage section (now also showing `--workers` and `--calibrate`). Most of the 27 left need calibrated or shipped tasks: the go/no-go, Batch 1/2 calibration, tuner runs, report numbers, human-likeness, final verification.

### 19:43 -03:00 · Tuning round 2 still too easy; a $13 Opus trial explained; first pipeline tasks pass functional gates
- **Tuning round 2 on `ledger-reconcile`:** a third interacting bug plus nastier verify-time cases. It re-gated cleanly (16/16 quality, novelty ok, red-team honest), then Opus went **4/4 again**. The task has used its 2 tuning rounds and is closed as too easy. Lesson for the presentation: on a ~300-line codebase, more bugs don't make it harder. Opus fixed three interacting bugs in 9-13 turns. Difficulty has to come from investigation depth, which the 800-2,000-line rule is for.
- **One Opus trial cost $13.45 (48 turns, 48.5 min)**, vs $0.21-0.24 for the other three:
  - It produced 300k output tokens. Every early response ran far past its JSON command, and terminus-2 warned "Extra text detected before/after JSON object" each turn. In that extra text Opus **imagined command outputs**, including whole alternate versions of the codebase, then reasoned about "the environment cycling between versions".
  - The real terminal output stayed consistent, and Docker isolation was checked and is fine: images are content-hash tagged and each trial has its own compose project. After a context summarization the agent re-checked everything, solved it, and was judged legit.
  - It's model behaviour that we may not change (no Opus/terminus-2 settings changes), so it stays a **tail cost risk** (~60× a normal trial), and the budget guard's per-trial pre-check doesn't bound it. It's covered by headroom: $62.72 spent of $380, $437.28 remaining. Spend rose ~$29 in 25 min, from this trial plus ~10 parallel authorings.
- **Funnel progress:** three pipeline-generated candidates passed structure + lint + functional (oracle 3/3, nop 0): `ae2e` Rust codec (pilot, after 2 repairs), `3bbd` EMA engine (Batch 1, first build), `2f50` C audit service (Batch 1, after 2 repairs for leaked tokens). With `ledger-reconcile`, that's 4 tasks past the validator + functional gates.
- **Lint false positive:** the suggestive-comment check scanned **vendored** third-party code (`node_modules/ajv-formats/...: // hint to the UI…`). Directories like `node_modules`, `vendor`, `site-packages`, `.git` and `target` are now skipped. Tradeoff: an author could in principle hide a hint there, but the leak scan still covers answer tokens anywhere in the image.
- **Authoring guard:** one build spent 30+ turns stuck at a shell `>` continuation prompt (an unclosed quote). The meta-task instruction now says to send `C-c` and rewrite with a quoted heredoc.
- 117 tests pass.

### 19:40 -03:00 · Six more speed-ups; scale Q&A for the presentation
1. **Calibration starts as soon as a task passes its gates.** `run_batch --calibrate` calls the new `calibrate_one`, also used by `scripts.calibrate_candidates`: red-team if it never ran, calibrate, ship if learnable. A gated task no longer waits for a separate run. A resumed batch also calibrates tasks gated before a crash.
   - Several processes can now calibrate at once, so `opus_slots` (flock'd slot files under `jobs/.opus-slots/`) caps **machine-wide** Opus trials at `OPUS_CONCURRENCY`. A wave takes all its slots or none (no deadlock), and a crashed holder frees its slots. Tested with 4 concurrent waves: peak ≤ 3, all complete.
   - Only the pilot batch runs with `--calibrate`, because the pilot calibration *is* the go/no-go measurement. Batches 1 and 2 wait for that decision.
2. **Old builders move to the new code.** Six batch processes started before these changes still had the 80-turn cap and stop-at-first-failure gates. A one-off watcher stops each process tree when one of its candidates has just started a new authoring attempt (<90 s of work at stake), removes any leftover authoring containers, and relaunches its batch with the new code, which resumes after the last finished attempt. A process that finishes on its own is relaunched too. Batch 2 is left alone: it already has the main yield changes, and its calibration waits for the go/no-go.
3. **Prompt caching verified, no change needed:** 96.5% of a recent authoring run's input tokens were cache reads (1.97M of 2.04M). Of that build's $1.51, output was ~$0.65, cache reads ~$0.59 and uncached input ~$0.22. The next cost lever is output length, which the "fewer, denser turns" rules already target.
4. **Toolchain recipes** (`generator/metatask/environment/recipes/{rust,go,node,c}.dockerfile`: Rust 1.82.0, Go 1.22.5, Node 20.17.0, gcc). The authoring image installs toolchains with the recipes' exact lines (enforced by `tests/test_recipes.py`), so Sonnet stops spending turns installing them. The meta-task instruction tells it to paste the matching recipe into the task's Dockerfile, so tasks stay self-contained (no custom base image) and their builds share Docker's layer cache. Both the authoring image and a bare base image with all four recipes were built and checked. Tradeoff: the authoring image grows to 2.4 GB, a one-time build.
5. **Quality check runs in parallel with novelty → red-team** once a package has built and passed oracle/nop and lint. That saves ~5-10 min per candidate. The red-team (~$0.2-2) may be paid for and then discarded when quality fails, but its findings still go into the repair.
6. **Repairs and tuning rounds capped at 70 turns** (`METATASK_REPAIR_MAX_TURNS`). A repair patches `/app/previous`; fresh builds keep 140.
- **`docs/architecture.md`:** new "Throughput and scale" Q&A for the presentation: what limited speed and what changed, why the README's rules weren't relaxed, and a 10,000-task design (queue per stage, remote sandboxes, image registry/cache, Postgres ledger, rate limits, LSH dedup, coverage quotas, sampled audits, a learned difficulty pre-filter), with a Mermaid diagram. Updated facts elsewhere: squared sampler weights, caching, self-dedup. All 10 diagrams render with mermaid-cli 11.
- 116 tests pass. Dry run with `--calibrate`: 1/1 gated.

### 19:24 -03:00 · Self-dedup gaps: in-flight candidates and short instructions
- **Noticed:** Batch 2 blueprint `rust-codec-regression-service` was accepted next to the pilot's `rust-codec-deploy-regression`, but the pilot never reached the judge. Two gaps:
  1. `own_tasks` indexed only authored `instruction.md` files. The pilot was being re-authored at that moment, so it had none.
  2. The judge sees only the top 3 by cosine. Outcome-only instructions are short, so the two Rust tasks scored just 0.092.
- **Fixes:**
  - A candidate without an instruction is indexed by its **accepted blueprint** (rejected blueprints don't count).
  - The judge always also sees the **2 nearest of our own tasks**, however low their cosine. Our corpus is small, so it costs little.
- **Re-check of the accepted blueprint** (both logged as `blueprint_recheck`, ~$0.02): with the fixed index, and then directly against the pilot, the verdict was **distinct**. The pilot is a performance regression recovered from git history. The new one is correctness bugs (endianness, zero-length frames) in an HTTP codec service. It keeps building.
- 113 tests pass.

### 19:18 -03:00 · Sampler steers harder; Batch 2 restarted on a diverse plan
- Batch 2's first plan (seed 3) drew **"file formats and recovery" 4 of 8 times and SQL 4 of 8**. A simulation over 300 seeds showed this was a ~1.3% draw. Still, plain inverse frequency, `1/(count+1)`, is soft: 18% of 8-spec batches repeat a domain 3+ times, and 38% repeat a language.
- **`STEER_POWER = 2`**: weights are now `base / (count + 1)^2`. That cuts domain 3+ repeats to 5% and language to 12%, and keeps the draw random.
- Batch 2 was stopped about a minute in, while its first 4 blueprint calls were in flight. They finished no stage, so there are no ledger events, and the 4 empty claim dirs and the plan file were removed. The OpenRouter spend for those calls (~$0.4) is unrecorded and will show as a small gap in the ledger-vs-gateway reconciliation.
- The new Batch 2 plan covers 7 domains and 5 languages in 8 specs. It's running with 4 workers.

### 19:17 -03:00 · First-pass yield: longer authoring, all cheap gates in one round, overgenerate
No fresh official candidate had passed every gate on its first build. The measured causes and the three fixes:
1. **Authoring turn cap 80 → 140** (`METATASK_MAX_TURNS`). The pilot's first build hit the 80-turn cap with a broken Dockerfile ($3.86, 42 min), then needed a repair (~$0.9, ~30 min each). Finishing the first build costs less than repairing it. 140 turns can run past an hour, so the **authoring meta-task's** agent timeout goes 3600 → 7200 s. Generated tasks keep `timeout_sec = 3600` (`make_task_toml`, enforced by lint). That rule is the README's, about the tasks Opus is calibrated on.
2. **Every cheap gate runs in the same round.** `stage_gates` used to stop at the first failing group, so a package could fail, get repaired, then fail the next gate, one round at a time. Example: the C candidate's first build failed the leak scan (answer tokens baked into `/app/etc/audit.key` and `seed.sql`), and its oracle and quality results were never seen. Now:
   - structure + lint + build/leak scan always run;
   - oracle/nop run whenever the image builds;
   - `harbor check` runs whenever the structure is valid (~$0.13, vs ~$0.9 per extra repair round).

   All findings go into one repair. Novelty and the red-team (~$0.2-2) still run only on a package that passes everything else.
3. **Overgenerate.** With parallel builds, more candidates cost the same wall-clock time, and spend isn't the limit ($33.71 spent, $466.29 left). Batch 2's generation starts now (8 candidates, 4 workers, under the new cap and gates). Its **calibration waits for the pilot go/no-go** (cost per learnable task vs $40), so the checkpoint still gates Opus spend.
- The already-running builders keep the old code until they exit. Only new processes use the 140 cap and the aggregated gates.
- 111 tests pass (new: one round reports leak + oracle + quality findings together; gates that can't run are skipped). Dry run: 1/1 gated through all five gates.

### 19:05 -03:00 · Self-duplication caught; blueprint retry; report gains per-batch, novelty-layer and difficulty sections
- **Finding:** the novelty judge rejected 2 of 8 official blueprints as **variants of our own Phase 0 task** (`ledger-reconcile`). One was a data-processing/SQLite spec ("ledger-aggregation-pipeline-drift"), the other a networking/algorithmic spec ("settlement-aggregator-consistency-bug"). Sonnet drifts toward ledger reconciliation even when the spec points elsewhere. The self-dedup layer (our candidates indexed next to the 425 published tasks) is what caught it. Without it, two near-copies would have reached Opus.
- **Why it cost two batch slots:** a rejected blueprint ended the candidate, while the plan said a reject should resample. Resampling the spec is the wrong fix, since the spec was fine and the *idea* drifted. Now:
  1. Our own earlier tasks are listed in the blueprint prompt's "must not resemble" section (they were only in the gate).
  2. A rejected blueprint gets **one retry** with the reason (judge verdicts, lexical overlaps, review scores), saved as `blueprint_rejected_<n>.json`. ~$0.13 per retry vs ~$4 for a full build that a later gate would throw away.

  The two rejected candidates were relaunched under the new logic. Their first rejections are kept as `blueprint_rejected_0.json`.
- **Report** (`analysis/report.py`, `analysis/diversity.py`):
  - **per batch:** candidates, gated, learnable, red-team hackable rate, USD.
  - **novelty rejects per layer:** blueprint lexical / blueprint judge / package lexical / package judge. So far 7 blueprints and 2 packages checked, 2 judge rejects.
  - **per shipped task:** max cosine per TB set plus the nearest of `examples/`.
  - **difficulty spread:** blueprint labels, predicted pass-rate quartiles, observed pass rates. Every blueprint so far is labelled "hard" with predicted p 0.25-0.4, while the only calibrated task was observed at 1.0. That's the gap calibration and the tuner exist to close.
- 109 tests pass.

### 19:02 -03:00 · Candidates build in parallel (the throughput bottleneck)
- **Bottleneck:** `run_batch` built one candidate at a time. A Sonnet authoring run takes 25-45 min (up to 80 turns) and is API-bound: its container idles at 0-1% CPU. Two batch processes gave ~2-3 candidates per hour, so the ~25 candidates still needed would have taken 10+ h. Spend was never the limit ($21 of $380).
- **`run_batch --workers N`** (default 3) builds candidates on a thread pool. Each candidate still runs its stages in order. CPU-heavy work (oracle runs, Opus trials) stays bounded by the gates' and calibrator's own concurrency.
- **Cross-process claims:** a candidate's `status.json` is `{"status": "building", "pid": N}` while it's in progress. Other batch processes skip it, and a claim whose process is dead (crash, reboot) is taken over and resumed. The two in-flight builds from the pre-fix processes were claimed under their pids, so new parallel processes took the 4 waiting candidates without killing them and without losing any paid authoring. **6 candidates are now building at once** (was 2).
- **Ledger appends take an exclusive `flock`**, so concurrent writers (threads and processes) can't interleave a long judge event.
- **Dry-run fix:** every dry-run candidate is the same fixture package, so the novelty gate (correctly) rejected each one as a copy of its dry-run siblings. Dry runs now index only the published corpus. The parallel dry run passes: 2/2 gated, $0.
- Ticked 4 checklist items whose official runs now exist: blueprint + review, the blueprint novelty gate, the final-package novelty re-check, and the red-team. Progress 51/83.

### 18:52 -03:00 · Crash recovery: every stage resumes without repaying; tuner sees its own history
- **What happened:** the machine rebooted at ~21:40 UTC with 4 jobs in flight: pilot repair a2 (Rust), Batch 1 authoring a1 (C), tuning round 2's Opus calibration (2 legit passes recorded, 2 trials in flight), and the dev calibration. Every Docker container died.
- **Resume gaps found:**
  1. `run_batch` re-sampled specs with a history that now included the batch's own candidates, so a rerun would have drawn **different** specs.
  2. `build_candidate` re-ran the blueprint (paid, and possibly different) and restarted at attempt 1.
  3. `calibrate` and the tuner started over.
- **Fixes:**
  - **Saved batch plans:** each batch's sampled specs go to `runs/batches/seed<S>-n<N>.json` and are reloaded on rerun. The plans for the two crashed batches were rebuilt by replaying the history each started with. The spec ids match the candidates on disk.
  - **`build_candidate`** reuses an accepted saved blueprint and continues after the last finished attempt (`failed_a<k>/`). Gate feedback is now saved as `feedback_a<k>.json`; older attempts fall back to the last failing gate's findings in the ledger.
  - **`calibrate`** keeps judged trials of a run that never reached its verdict. A finished run is never reused. New wave numbers don't overwrite the old job dirs.
  - **`tune_candidate`** restores finished rounds from the ledger. A round whose new package already passed every gate (the content hash matches a clean red-team record and differs from the round's `before_tune_r<n>` snapshot) goes straight to calibration. Plans are saved as `tune_plan_r<n>.json`. Round 2's plan was recovered from its rendered meta-task instruction.
  - **Net loss from the crash:** the C candidate's partial first build (no finished attempt to resume from) and 2 in-flight Opus trials (~$0.5).
- **Tuner bug found during recovery:** round 2's plan was round 1's again ("add a third interacting bug"). The planner sees only the original blueprint, not what earlier rounds changed. `plan_mutation` now gets the round history (plan → verdict, outcomes) and a rule not to repeat a change that didn't move the pass rate. Pass summaries now include the audit's description of *how* Opus solved the task, not just turns and minutes. Round 2 keeps its plan, since it's already authored and gated.
- **The dev quality gate did its job:** the dev package (`fix-inhouse-pinmux-planner`) passed oracle 3/3 and nop, then was blocked by `deterministic_tests` and `valid_failure_modes`. A test asserted wall-clock time under 90 s, and the instruction didn't state the time limit. No calibration money was spent on a flaky task.
- 107 tests pass (new: resume point, blueprint reuse, exact-package gating, unfinished trials, tuner round restore, history in the plan prompt).
- Spend at restart: $20.81 (`spent*`), $479.19 remaining.

### 18:26 -03:00 · Dev mode found a crash; per-candidate error isolation
- **Bug, found by the dev-mode batch:** the leak scan's `grep` matched inside a **binary** file in the image (a SQLite db), and `docker run … cat <file>` output that wasn't UTF-8 made `subprocess.run(text=True)` raise `UnicodeDecodeError`. That took down the whole batch process after 47 minutes of authoring.
- **Fixes:**
  1. Docker output is decoded with `errors="replace"`.
  2. `run_batch` now isolates failures: an exception in one candidate marks it `error` (status + ledger event) and the batch continues. `BudgetExceeded` stops the batch cleanly.

  The rescan of the crashed dev task completes: no blocking leaks, 3 notes from binary db files.
- The pilot and Batch 1 processes started before this fix and are still exposed until they finish.
- **This is what dev mode is for:** the crash cost ~$0.03 of DeepSeek instead of a $3-4 Sonnet build. Its gates and a dev-mode calibration loop are now running on the existing package.

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
