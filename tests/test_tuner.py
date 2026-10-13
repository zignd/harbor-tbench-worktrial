import json
from pathlib import Path

from analysis import tuner
from analysis.llm import Reply

CAL_EASY = {
    "verdict": "too_easy",
    "outcomes": ["pass", "pass", "pass", "pass"],
    "trials": [{"outcome": "pass", "turns": 18, "minutes": 6.0, "audit": {"label": "legit"}}] * 4,
}
CAL_HARD = {
    "verdict": "too_hard",
    "outcomes": ["fail"] * 5,
    "trials": [
        {"outcome": "fail", "failure": {"mode": "capability_gap", "explanation": "never found it"}}
    ]
    * 5,
}


def _fake(plan: dict, seen: dict):
    def chat_fn(prompt, **kwargs):
        seen["prompt"] = prompt
        return Reply(json.dumps(plan), "m", 10, 0, 10, 0.03, 0.1)

    return chat_fn


def test_plan_for_too_easy_task_mentions_result_and_levers():
    seen = {}
    plan = {"kind": "knob", "direction": "harder", "change": "add 3x more cases"}
    got, cost = tuner.plan_mutation("blueprint md", CAL_EASY, chat_fn=_fake(plan, seen))
    assert got == plan and cost == 0.03
    assert "4/4 judged runs passed" in seen["prompt"] and "too easy" in seen["prompt"]
    assert "shallow_check_trap" in seen["prompt"]


def test_plan_for_too_hard_task_includes_failure_reasons():
    seen = {}
    plan = {"kind": "lever", "direction": "easier", "change": "surface the error"}
    tuner.plan_mutation("bp", CAL_HARD, chat_fn=_fake(plan, seen))
    assert "capability_gap: never found it" in seen["prompt"]


def test_unknown_kind_falls_back_to_knob():
    got, _ = tuner.plan_mutation("bp", CAL_EASY, chat_fn=_fake({"kind": "magic"}, {}))
    assert got["kind"] == "knob"


def test_directive_keeps_fairness_rules():
    text = tuner.directive({"kind": "knob", "direction": "harder", "change": "more cases"})
    assert "too easy" in text and "every requirement the tests check" in text


def test_plan_sees_earlier_rounds_so_it_does_not_repeat_them():
    seen = {}
    rounds = [{"round": 1, "plan": {"change": "add a third bug"}, "result": "too_easy",
               "outcomes": ["pass"] * 4}]  # fmt: skip
    tuner.plan_mutation("bp", CAL_EASY, rounds, chat_fn=_fake({"kind": "knob"}, seen))
    assert "round 1: add a third bug -> too_easy" in seen["prompt"]


def test_resume_rounds_restores_finished_rounds_from_the_ledger(tmp_path):
    from analysis.ledger import Event, Ledger

    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append(Event("calibration_trial", "c-t1", {"outcome": "pass", "turns": 9}))
    ledger.append(Event("tune", "c", {"round": 1, "plan": {}, "result": "too_easy",
                                      "outcomes": ["pass"] * 4}))  # fmt: skip
    rounds, cal = tuner._resume_rounds("c", ledger)
    assert [r["round"] for r in rounds] == [1]
    assert cal["verdict"] == "too_easy" and cal["trials"] == [{"outcome": "pass", "turns": 9}]
    assert tuner._resume_rounds("other", ledger) == ([], None)


def test_invalid_calibration_gets_a_spec_fix_plan_from_the_judged_failures():
    cal = {"verdict": "invalid", "outcomes": ["invalid"] * 2, "trials": [
        {"outcome": "invalid", "failure": {"valid": False, "mode": "test_overreach",
                                           "requirement": "tied rows in SQLite order",
                                           "explanation": "order of ties is unstated"}},
        {"outcome": "invalid", "failure": {"valid": False, "mode": "test_overreach",
                                           "requirement": "tied rows in SQLite order",
                                           "explanation": "order of ties is unstated"}},
    ]}  # fmt: skip
    plan = tuner.fix_spec_plan(cal)
    assert plan["kind"] == "fix_spec" and plan["change"].count("tied rows") == 1  # deduplicated
    text = tuner.directive(plan)
    assert "Spec fix" in text and "every solution the instruction allows passes" in text


def test_spec_fix_round_snapshots_the_package_and_saves_its_plan(tmp_path, monkeypatch):
    import shutil

    from analysis.ledger import Ledger

    fixture = Path(__file__).parent / "fixtures" / "harbor_jobs" / "p0-metatask-sonnet"
    task = next(fixture.glob("*/artifacts/app/output"))
    cand_dir = tmp_path / "official-x"
    shutil.copytree(task, cand_dir / "task")
    spec = {"domain": "d", "skill_type": "s", "capabilities": ["a", "b"], "pillar": "p",
            "persona": "x", "language": "any", "fixture": "f", "verifier": "service_probe",
            "levers": ["hidden_invariant", "edge_case_inputs"], "style": "minimal"}  # fmt: skip
    bp = json.loads((Path(__file__).parent / "fixtures" / "blueprint_ledger.json").read_text())
    (cand_dir / "spec.json").write_text(json.dumps(spec))
    (cand_dir / "blueprint.json").write_text(json.dumps(bp))
    (cand_dir / "calibration.json").write_text(json.dumps({"verdict": "invalid", "outcomes": ["invalid"],
        "trials": [{"outcome": "invalid", "failure": {"valid": False, "mode": "test_overreach",
        "requirement": "tie order", "explanation": "unstated"}}]}))  # fmt: skip
    from generator import pipeline

    monkeypatch.setattr(pipeline, "CANDIDATES_DIR", tmp_path)  # Candidate.dir resolves here
    seen = {}

    def fake_retune(cand, ledger, rnd, plan, previous):
        seen["previous_exists"] = previous.exists()
        seen["plan"] = plan
        return ["stop here"]  # gates fail: ends the round without a calibration

    monkeypatch.setattr(tuner, "_retune", fake_retune)
    tuner.tune_candidate(cand_dir, Ledger(tmp_path / "l.jsonl"), max_rounds=1)
    assert seen["previous_exists"] and seen["plan"]["kind"] == "fix_spec"
    assert (cand_dir / "tune_plan_r1.json").exists()


def test_an_infra_failed_authoring_is_not_a_tuning_round(tmp_path):
    from analysis.ledger import Event, Ledger

    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append(Event("tune", "c", {"round": 1, "plan": {}, "gate_problems": ["authoring failed"],
                                      "result": "gates_failed"}))  # fmt: skip
    assert tuner._resume_rounds("c", ledger) == ([], None)  # redone, not counted
    ledger.append(Event("tune", "c", {"round": 1, "plan": {}, "gate_problems": ["oracle 0/3"],
                                      "result": "gates_failed"}))  # fmt: skip
    rounds, cal = tuner._resume_rounds("c", ledger)
    assert [r["round"] for r in rounds] == [1] and cal["verdict"] == "gates_failed"
