import json

from analysis.llm import Reply
from generator import blueprint as bpmod
from generator.spec import sample_specs

SPEC = sample_specs(1, seed=11)[0]
BLUEPRINT = {
    "slug": "nightly-backup-skips-tables",
    "title": "Backup job skips new tables",
    "scenario": "A Postgres-like backup script misses tables created after a migration.",
    "instruction_draft": "Make the nightly backup include every table and keep retention rules.",
    "requirements": ["every table is backed up", "retention keeps 7 days"],
    "environment": ["sqlite db with 40 tables", "backup.sh with a stale table list"],
    "internal_hint": "The table list is cached at install time; read sqlite_master instead.",
    "trap": "Fixing only the cache misses tables in the attached secondary database.",
    "tests": ["create a new table at verify time and check it is backed up"],
    "verifier_knob": {"name": "tables created at verify time", "value": "5", "effect": "more"},
    "expected_failure_modes": ["fixes the cache but not the attached db"],
    "predicted_pass_rate": 0.35,
    "difficulty": "hard",
    "category": "system-administration",
    "tags": ["sqlite", "backup", "bash"],
}


def _reply(obj: dict, cost: float = 0.01) -> Reply:
    return Reply("```json\n" + json.dumps(obj) + "\n```", "m", 100, 0, 100, cost, 0.1)


def test_make_blueprint_parses_and_prompts_with_concepts(monkeypatch):
    seen = {}

    def fake_chat(prompt, **kwargs):
        seen["prompt"] = prompt
        return _reply(BLUEPRINT, cost=0.05)

    monkeypatch.setattr(bpmod, "chat", fake_chat)
    bp, cost = bpmod.make_blueprint(SPEC, concepts="- set/some-task: something")
    assert bp.slug == BLUEPRINT["slug"] and cost == 0.05
    assert "- set/some-task: something" in seen["prompt"]
    assert SPEC.domain in seen["prompt"]
    md = bp.to_markdown(SPEC)
    assert "Internal hint" in md and SPEC.levers[0] in md


def test_review_acceptance_is_enforced_by_scores_not_model_verdict(monkeypatch):
    bp = bpmod.Blueprint(**BLUEPRINT)
    low = {
        "scores": {
            "clarity": 5,
            "solvability": 5,
            "verifiability": 5,
            "genuine_difficulty": 2,
            "realism": 5,
        },
        "verdict": "accept",
    }
    monkeypatch.setattr(bpmod, "chat", lambda *a, **k: _reply(low))
    review, _ = bpmod.review_blueprint(bp, SPEC)
    assert review["accepted"] is False  # one score < 3, despite "accept"

    good = {"scores": {k: 4 for k in low["scores"]}, "verdict": "reject"}
    monkeypatch.setattr(bpmod, "chat", lambda *a, **k: _reply(good))
    review, _ = bpmod.review_blueprint(bp, SPEC)
    assert review["accepted"] is True


def test_gate_rejects_lexical_copy_without_calling_the_judge(monkeypatch):
    bp = bpmod.Blueprint(**BLUEPRINT)
    good = {
        "scores": {
            "clarity": 4,
            "solvability": 4,
            "verifiability": 4,
            "genuine_difficulty": 4,
            "realism": 4,
        }
    }
    monkeypatch.setattr(bpmod, "chat", lambda *a, **k: _reply(good))
    monkeypatch.setattr(bpmod.novelty, "lexical_flags", lambda text: ["TF-IDF cosine 0.91"])

    def no_judge(*a, **k):
        raise AssertionError("judge must not run when lexical flags already reject")

    monkeypatch.setattr(bpmod.novelty, "judge_same_task", no_judge)
    decision = bpmod.gate_blueprint(bp, SPEC)
    assert decision["accepted"] is False and decision["novelty"]["lexical_flags"]


def test_gate_accepts_novel_well_scored_blueprint(monkeypatch):
    bp = bpmod.Blueprint(**BLUEPRINT)
    good = {
        "scores": {
            "clarity": 4,
            "solvability": 4,
            "verifiability": 4,
            "genuine_difficulty": 4,
            "realism": 4,
        }
    }
    monkeypatch.setattr(bpmod, "chat", lambda *a, **k: _reply(good, cost=0.02))
    monkeypatch.setattr(bpmod.novelty, "lexical_flags", lambda text: [])
    monkeypatch.setattr(
        bpmod.novelty, "judge_same_task", lambda text: {"novel": True, "cost_usd": 0.01}
    )
    decision = bpmod.gate_blueprint(bp, SPEC)
    assert decision["accepted"] is True
    assert abs(decision["cost_usd"] - 0.03) < 1e-9
