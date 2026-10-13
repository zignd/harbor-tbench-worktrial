"""Control flow of generator.pipeline.build_candidate with every paid stage faked."""

import json
import shutil
from pathlib import Path

import pytest

from analysis.ledger import Ledger
from generator import pipeline
from generator.blueprint import Blueprint
from generator.spec import sample_specs

FIX = Path(__file__).parent / "fixtures"
TASK = FIX / "harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"
BLUEPRINT = Blueprint(**json.loads((FIX / "blueprint_ledger.json").read_text()))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CANDIDATES_DIR", tmp_path / "candidates")
    # Gate slots are machine-wide locks under JOBS_DIR: a test must never wait on (or hold)
    # the live pipeline's slots.
    monkeypatch.setattr(pipeline, "JOBS_DIR", str(tmp_path / "jobs"))
    calls = {"author": [], "gates": 0}

    def fake_blueprint(cand, ledger):
        cand.blueprint = BLUEPRINT
        return True

    def fake_author(cand, ledger, attempt, feedback=None, previous=None):
        calls["author"].append({"attempt": attempt, "feedback": feedback, "previous": previous})
        if cand.task_dir.exists():
            shutil.rmtree(cand.task_dir)
        shutil.copytree(TASK, cand.task_dir)
        return True

    monkeypatch.setattr(pipeline, "stage_blueprint", fake_blueprint)
    monkeypatch.setattr(pipeline, "stage_author", fake_author)
    return calls, Ledger(tmp_path / "ledger.jsonl")


def test_first_attempt_passes(env, monkeypatch):
    calls, ledger = env
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a, **kw: [])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=3)[0]), ledger)
    assert cand.status == "gated"
    assert [c["attempt"] for c in calls["author"]] == [1]
    assert json.loads((cand.dir / "status.json").read_text())["status"] == "gated"


def test_repair_gets_feedback_and_previous_package(env, monkeypatch):
    calls, ledger = env
    results = iter([["oracle passed 1/3"], []])
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a, **kw: next(results))
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=4)[0]), ledger)
    assert cand.status == "gated"
    second = calls["author"][1]
    assert second["feedback"] == ["oracle passed 1/3"]
    assert second["previous"].name == "failed_a1" and (second["previous"] / "task.toml").exists()


def test_repairs_then_one_regeneration_then_failed(env, monkeypatch):
    calls, ledger = env
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a, **kw: ["still broken"])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=5)[0]), ledger)
    assert cand.status == "failed"
    # (1 build + MAX_REPAIRS repairs) x (original + one regeneration)
    assert len(calls["author"]) == 2 * (1 + pipeline.MAX_REPAIRS)
    fresh = [c for c in calls["author"] if c["previous"] is None]
    assert len(fresh) == 2  # the regeneration starts from the blueprint, not the failed package


def test_rejected_blueprint_stops_early(env, monkeypatch):
    calls, ledger = env

    def reject(cand, ledger):
        cand.status = "rejected"
        return False

    monkeypatch.setattr(pipeline, "stage_blueprint", reject)
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=6)[0]), ledger)
    assert cand.status == "rejected" and calls["author"] == []


def test_resume_reuses_blueprint_and_continues_after_last_finished_attempt(env, monkeypatch):
    calls, ledger = env
    spec = sample_specs(1, seed=7)[0]
    first = pipeline.Candidate(spec)
    first.save("blueprint.json", BLUEPRINT.model_dump())
    first.save("blueprint_gate.json", {"accepted": True})
    shutil.copytree(TASK, first.dir / "failed_a1")  # attempt 1 finished; attempt 2 was cut off
    first.save("feedback_a1.json", ["docker build failed"])
    monkeypatch.setattr(pipeline, "stage_blueprint", lambda c, l: pytest.fail("re-blueprinted"))
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a, **kw: [])
    cand = pipeline.build_candidate(pipeline.Candidate(spec), ledger)
    assert cand.status == "gated" and cand.blueprint.slug == BLUEPRINT.slug
    assert calls["author"] == [
        {"attempt": 2, "feedback": ["docker build failed"], "previous": first.dir / "failed_a1"}
    ]


def test_already_gated_matches_the_exact_package(env):
    from analysis.ledger import Event, hash_dir

    _, ledger = env
    cand = pipeline.Candidate(sample_specs(1, seed=8)[0])
    shutil.copytree(TASK, cand.task_dir)
    assert not pipeline.already_gated(cand, ledger)
    h = hash_dir(cand.task_dir)
    ledger.append(Event("gate_redteam", cand.cand_id, {"hackable": False}, inputs_hash=h))
    assert pipeline.already_gated(cand, ledger)
    (cand.task_dir / "instruction.md").write_text("changed")
    assert not pipeline.already_gated(cand, ledger)


def test_rejected_blueprint_is_retried_once_with_the_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(pipeline.budget, "check", lambda expected: None)
    monkeypatch.setattr(pipeline.novelty, "gate_index", lambda d, e="": None)
    monkeypatch.setattr(pipeline.novelty, "concept_list", lambda index=None: "- ours/x: ledger")
    prompts = []

    def fake_make(spec, concepts, feedback=None):
        prompts.append((concepts, feedback))
        return BLUEPRINT, 0.1

    variant = {"verdict": "variant", "ref_id": "ours/x", "reason": "same ledger bug"}
    decisions = iter([
        {"accepted": False, "review": {"accepted": True, "scores": {}},
         "novelty": {"lexical_flags": [], "judge": {"verdicts": [variant]}, "novel": False},
         "cost_usd": 0.01},
        {"accepted": True, "review": {"accepted": True, "scores": {}},
         "novelty": {"lexical_flags": [], "judge": {"verdicts": []}, "novel": True},
         "cost_usd": 0.01},
    ])  # fmt: skip
    monkeypatch.setattr(pipeline, "make_blueprint", fake_make)
    monkeypatch.setattr(pipeline, "gate_blueprint", lambda bp, spec, index: next(decisions))
    monkeypatch.setattr(pipeline, "BLUEPRINT_DRAFTS", 1)  # one draft per round: ordered calls
    cand = pipeline.Candidate(sample_specs(1, seed=9)[0])
    assert pipeline.stage_blueprint(cand, Ledger(tmp_path / "l.jsonl"))
    assert prompts[0] == ("- ours/x: ledger", None)
    assert "variant of ours/x (same ledger bug)" in prompts[1][1]
    assert (cand.dir / "blueprint_rejected_1.json").exists()


def _gate_env(monkeypatch, static, functional, quality):
    calls = []
    monkeypatch.setattr(pipeline, "gate_static", lambda d, tag: (calls.append("static"), static)[1])
    monkeypatch.setattr(
        pipeline, "gate_functional", lambda d, n: (calls.append("functional"), functional)[1]
    )
    monkeypatch.setattr(pipeline, "run_check", lambda d, n: (calls.append("quality"), quality)[1])
    monkeypatch.setattr(pipeline.budget, "check", lambda expected: None)
    monkeypatch.setattr(pipeline, "stage_redteam", lambda *a: (calls.append("redteam"), [])[1])
    return calls


QUALITY_FAIL = {"ok": False, "outcomes": {}, "blocking_failures": ["typos: x"],
                "advice": ["fix the typo"], "cost_usd": 0.1}  # fmt: skip


def test_gates_report_every_cheap_finding_in_one_round(env, monkeypatch):
    _, ledger = env
    calls = _gate_env(
        monkeypatch,
        (["leak: answer in /app/x"], True, True),
        (["oracle passed 2/3"], {"oracle": [], "nop": [], "excluded": 0}),
        QUALITY_FAIL,
    )
    cand = pipeline.Candidate(sample_specs(1, seed=10)[0])
    shutil.copytree(TASK, cand.task_dir)
    problems = pipeline.stage_gates(cand, ledger, 1)
    assert problems == ["leak: answer in /app/x", "oracle passed 2/3", "typos: x", "fix the typo"]
    assert calls == ["static", "functional", "quality"]  # no novelty/red-team on a broken package


def test_gates_skip_what_cannot_run(env, monkeypatch):
    _, ledger = env
    calls = _gate_env(monkeypatch, (["structure: no tests/"], False, False), None, None)
    cand = pipeline.Candidate(sample_specs(1, seed=11)[0])
    shutil.copytree(TASK, cand.task_dir)
    assert pipeline.stage_gates(cand, ledger, 1) == ["structure: no tests/"]
    assert calls == ["static"]  # no image to run, no valid structure to review


def test_clean_package_runs_quality_alongside_novelty_and_redteam(env, monkeypatch):
    _, ledger = env
    calls = _gate_env(
        monkeypatch, ([], True, True), ([], {"oracle": [], "nop": [], "excluded": 0}), QUALITY_FAIL
    )
    monkeypatch.setattr(pipeline.novelty, "gate_index", lambda d, exclude="": None)
    monkeypatch.setattr(pipeline, "stage_difficulty", lambda cand, ledger, h: [])
    monkeypatch.setattr(pipeline.novelty, "lexical_flags", lambda text, index: [])
    monkeypatch.setattr(
        pipeline.novelty, "judge_same_task",
        lambda text, index: {"novel": True, "verdicts": [], "nearest": [], "cost_usd": 0.0},
    )  # fmt: skip
    cand = pipeline.Candidate(sample_specs(1, seed=12)[0])
    shutil.copytree(TASK, cand.task_dir)
    assert pipeline.stage_gates(cand, ledger, 1) == ["typos: x", "fix the typo"]
    assert sorted(calls) == ["functional", "quality", "redteam", "static"]


def test_attempt_interrupted_after_authoring_goes_back_to_its_gates(env, monkeypatch):
    from analysis.ledger import Event, hash_dir

    calls, ledger = env
    spec = sample_specs(1, seed=13)[0]
    first = pipeline.Candidate(spec)
    first.save("blueprint.json", BLUEPRINT.model_dump())
    first.save("blueprint_gate.json", {"accepted": True})
    shutil.copytree(TASK, first.task_dir)  # authored, then the gates were cut off
    h = hash_dir(first.task_dir)
    ledger.append(Event("author", first.cand_id, {"attempt": 1, "outcome": "pass"}))
    ledger.append(Event("gate_static", first.cand_id, {"problems": []}, inputs_hash=h))
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a, **kw: [])
    cand = pipeline.build_candidate(pipeline.Candidate(spec), ledger)
    assert cand.status == "gated" and calls["author"] == []  # no re-authoring


def test_changed_package_is_not_mistaken_for_the_authored_one(env):
    from analysis.ledger import Event

    _, ledger = env
    cand = pipeline.Candidate(sample_specs(1, seed=14)[0])
    shutil.copytree(TASK, cand.task_dir)
    ledger.append(Event("author", cand.cand_id, {"attempt": 1, "outcome": "pass"}, inputs_hash="x"))
    assert not pipeline.authored_unchanged(cand, ledger, 1)


def test_parallel_drafts_keep_an_accepted_one_and_record_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CANDIDATES_DIR", tmp_path / "candidates")
    monkeypatch.setattr(pipeline.budget, "check", lambda expected: None)
    monkeypatch.setattr(pipeline.novelty, "gate_index", lambda d, e="": None)
    monkeypatch.setattr(pipeline.novelty, "concept_list", lambda index=None: "")
    monkeypatch.setattr(pipeline, "make_blueprint", lambda spec, c, feedback=None: (BLUEPRINT, 0.1))
    calls = iter(range(100))

    def gate(bp, spec, index):
        ok = next(calls) == 2  # exactly one of the four parallel drafts is accepted
        return {"accepted": ok, "review": {"accepted": ok, "scores": {}},
                "novelty": {"lexical_flags": [], "judge": {"verdicts": []}, "novel": True},
                "cost_usd": 0.0}  # fmt: skip

    monkeypatch.setattr(pipeline, "gate_blueprint", gate)
    cand = pipeline.Candidate(sample_specs(1, seed=15)[0])
    ledger = Ledger(tmp_path / "l.jsonl")
    assert pipeline.stage_blueprint(cand, ledger)
    assert len(list(cand.dir.glob("blueprint_rejected_*.json"))) == 3
    assert len(ledger.events(stage="blueprint_gate")) == 4


def test_a_too_easy_built_package_goes_back_to_repair_without_a_red_team(env, monkeypatch):
    _, ledger = env
    calls = _gate_env(monkeypatch, ([], True, True), ([], {"oracle": [], "nop": [], "excluded": 0}),
                      {"ok": True, "outcomes": {}, "blocking_failures": [], "advice": [],
                       "cost_usd": 0.0})  # fmt: skip
    monkeypatch.setattr(pipeline.novelty, "gate_index", lambda d, exclude="": None)
    monkeypatch.setattr(pipeline.novelty, "lexical_flags", lambda text, index: [])
    monkeypatch.setattr(
        pipeline.novelty, "judge_same_task",
        lambda text, index: {"novel": True, "verdicts": [], "nearest": [], "cost_usd": 0.0},
    )  # fmt: skip
    monkeypatch.setattr(pipeline, "DIFFICULTY_GATE_BLOCKS", True)
    monkeypatch.setattr(pipeline, "review_package", lambda task_dir, intended: {
        "accepted": False, "difficulty": 2, "speedrun_commands": 6, "cost_usd": 0.05,
        "promised_difficulty_present": False, "reasons": "bugs sit in one readable file",
        "fixes": ["ship the component as a binary"]})  # fmt: skip
    cand = pipeline.Candidate(sample_specs(1, seed=16)[0])
    cand.blueprint = BLUEPRINT
    shutil.copytree(TASK, cand.task_dir)
    problems = pipeline.stage_gates(cand, ledger, 1)
    assert len(problems) == 1 and problems[0].startswith("difficulty:")
    assert "missing from the environment" in problems[0] and "ship the component" in problems[0]
    assert "redteam" not in calls  # no red-team spend on a package that goes back to repair
    assert ledger.events(stage="gate_difficulty")[0].result["speedrun_commands"] == 6


def _fake_cal(verdict, trials=None):
    from evaluator.calibrate import Calibration

    cal = Calibration(task="x", outcomes=["pass"] * 4 if verdict == "too_easy" else ["pass", "fail"],
                      trials=trials or [])  # fmt: skip
    cal.verdict = verdict
    return cal


def _gates_returning(monkeypatch, per_attempt):
    """stage_gates stub: (problems, calibration verdict) per attempt, set like the real one."""
    queue = iter(per_attempt)

    def gates(cand, ledger, attempt, calibrate=False):
        problems, verdict = next(queue)
        cand.calibration = _fake_cal(verdict) if verdict else None
        return problems

    monkeypatch.setattr(pipeline, "stage_gates", gates)


def test_calibrate_first_a_too_easy_candidate_ends_without_repair(env, monkeypatch):
    calls, ledger = env
    _gates_returning(monkeypatch, [(["lint: x", "quality: y"], "too_easy")])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=17)[0]), ledger)
    assert cand.status == "calibrated" and len(calls["author"]) == 1  # no repair rounds
    saved = json.loads((cand.dir / "status.json").read_text())
    assert saved["verdict"] == "too_easy" and saved["pending_findings"] == ["lint: x", "quality: y"]


def test_calibrate_first_a_learnable_candidate_is_repaired_for_its_findings(env, monkeypatch):
    calls, ledger = env
    _gates_returning(monkeypatch, [(["quality: needs a fix"], "learnable"), ([], "learnable")])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=18)[0]), ledger)
    assert cand.status == "gated" and len(calls["author"]) == 2
    assert calls["author"][1]["feedback"] == ["quality: needs a fix"]


def test_calibrate_first_an_invalid_candidate_gets_a_spec_fix_directive(env, monkeypatch):
    calls, ledger = env
    trial = {"outcome": "invalid", "failure": {"valid": False, "mode": "test_overreach",
                                               "requirement": "tie order", "explanation": "unstated"}}  # fmt: skip
    queue = iter([(["lint: x"], "invalid"), ([], "learnable")])

    def gates(cand, ledger, attempt, calibrate=False):
        problems, verdict = next(queue)
        cand.calibration = _fake_cal(verdict, [trial] if verdict == "invalid" else None)
        return problems

    monkeypatch.setattr(pipeline, "stage_gates", gates)
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=19)[0]), ledger)
    assert cand.status == "gated"
    feedback = calls["author"][1]["feedback"]
    assert feedback[0].startswith("Spec fix:") and feedback[1] == "lint: x"


def test_stage_gates_calibrates_only_a_package_that_passed_oracle_and_nop(env, monkeypatch):
    _, ledger = env
    seen = []
    monkeypatch.setattr(pipeline, "_calibrate_package",
                        lambda cand, ledger, attempt, h: (seen.append(attempt), _fake_cal("learnable"))[1])  # fmt: skip
    monkeypatch.setattr(pipeline, "_remaining_gates", lambda *a: [])
    cand = pipeline.Candidate(sample_specs(1, seed=20)[0])
    shutil.copytree(TASK, cand.task_dir)
    ok = ([], True, True)
    monkeypatch.setattr(pipeline, "gate_static", lambda d, tag: ok)
    monkeypatch.setattr(pipeline, "gate_functional",
                        lambda d, n: ([], {"oracle": [], "nop": [], "excluded": 0}))  # fmt: skip
    assert pipeline.stage_gates(cand, ledger, 1, calibrate=True) == []
    assert seen == [1] and cand.calibration.verdict == "learnable"
    monkeypatch.setattr(pipeline, "gate_functional",
                        lambda d, n: (["oracle passed 2/3"], {"oracle": [], "nop": [], "excluded": 0}))  # fmt: skip
    pipeline.stage_gates(cand, ledger, 2, calibrate=True)
    assert seen == [1] and cand.calibration is None  # an oracle failure is never calibrated
    pipeline.stage_gates(cand, ledger, 3)  # calibrate off by default (tuner path)
    assert seen == [1]
