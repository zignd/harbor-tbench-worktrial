import json

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
