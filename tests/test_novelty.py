import json
from pathlib import Path

from analysis.llm import Reply
from validator import novelty
from validator.novelty import Index, RefTask

ROOT = Path(__file__).resolve().parents[1]


def _example_index() -> Index:
    """Index over the 6 examples only, so tests don't need `make tb-reference`."""
    refs = tuple(
        RefTask(f"examples/{d.name}", (d / "instruction.md").read_text(), d.name)
        for d in sorted((ROOT / "examples").iterdir())
        if d.is_dir()
    )
    return Index(refs)


LOG_TASK = (ROOT / "examples" / "log-summary-date-ranges" / "instruction.md").read_text()


def test_verbatim_copy_is_flagged_by_ngrams_and_cosine():
    flags = novelty.lexical_flags(LOG_TASK, _example_index())
    assert any("13-gram" in f for f in flags)
    assert any("cosine" in f and "log-summary" in f for f in flags)


def test_light_rewording_is_still_nearest():
    reworded = LOG_TASK.replace("log files", "logfiles").replace("severity", "level")
    ref, score = _example_index().nearest(reworded, k=1)[0]
    assert ref.ref_id == "examples/log-summary-date-ranges"
    assert score >= novelty.COSINE_REJECT


def test_unrelated_task_is_clean():
    text = (
        "The nightly backup job for our Postgres replica silently skips tables created "
        "after Tuesday's migration. Make the backup script include every table and keep "
        "existing retention rules."
    )
    assert novelty.lexical_flags(text, _example_index()) == []


def test_concept_list_has_one_line_per_reference():
    idx = _example_index()
    lines = novelty.concept_list(idx).splitlines()
    assert len(lines) == len(idx.refs) and lines[0].startswith("- examples/")


def test_judge_marks_variant_as_not_novel():
    def fake_chat(prompt, **kwargs):
        assert "examples/log-summary-date-ranges" in prompt
        text = (
            '{"verdicts": [{"ref_id": "examples/log-summary-date-ranges", "verdict": "variant",'
            ' "reason": "same log aggregation"}, {"ref_id": "a", "verdict": "distinct",'
            ' "reason": "x"}, {"ref_id": "b", "verdict": "distinct", "reason": "y"}]}'
        )
        return Reply(text, "m", 10, 0, 10, 0.01, 0.1)

    result = novelty.judge_same_task(LOG_TASK, _example_index(), chat=fake_chat)
    assert result["novel"] is False and result["cost_usd"] == 0.01


def test_judge_all_distinct_is_novel():
    def fake_chat(prompt, **kwargs):
        verdicts = ",".join(
            '{"ref_id": "r", "verdict": "distinct", "reason": "different"}' for _ in range(3)
        )
        return Reply('{"verdicts": [' + verdicts + "]}", "m", 1, 0, 1, 0.0, 0.0)

    assert novelty.judge_same_task("backup job", _example_index(), chat=fake_chat)["novel"]


def test_own_tasks_are_indexed_but_never_compared_with_themselves(tmp_path):
    for cand, text in [("official-a", LOG_TASK), ("official-b", "Fix the nightly backup job.")]:
        (tmp_path / cand / "task").mkdir(parents=True)
        (tmp_path / cand / "task" / "instruction.md").write_text(text)
    refs = novelty.own_tasks(tmp_path, exclude="official-a")
    assert [r.ref_id for r in refs] == ["ours/official-b"]
    index = Index(_example_index().refs + novelty.own_tasks(tmp_path, exclude="official-b"))
    assert index.nearest(LOG_TASK, k=1)[0][0].ref_id in {
        "examples/log-summary-date-ranges",
        "ours/official-a",
    }


def test_candidate_without_instruction_is_indexed_by_its_accepted_blueprint(tmp_path):
    bp = {"title": "Rust codec regression", "scenario": "a framing codec broke",
          "instruction_draft": "fix the codec", "requirements": ["round-trips frames"]}  # fmt: skip
    for name, accepted in [("official-a", True), ("official-r", False)]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "blueprint.json").write_text(json.dumps(bp))
        (tmp_path / name / "blueprint_gate.json").write_text(json.dumps({"accepted": accepted}))
    refs = novelty.own_tasks(tmp_path)
    assert [r.ref_id for r in refs] == ["ours/official-a"]  # rejected blueprints don't count
    assert "round-trips frames" in refs[0].instruction


def test_judge_always_sees_our_nearest_own_tasks_even_at_low_cosine():
    seen = {}

    def fake_chat(prompt, **kwargs):
        seen["prompt"] = prompt
        return Reply('{"verdicts": []}', "m", 1, 0, 1, 0.0, 0.0)

    own = novelty.RefTask("ours/official-x", "rust packet codec latency regression", "g")
    index = Index(_example_index().refs + (own,))
    result = novelty.judge_same_task("backup job for a postgres database", index, chat=fake_chat)
    assert "[ours/official-x]" in seen["prompt"]
    assert ("ours/official-x", 0.0) in [(r, round(c, 1)) for r, c in result["nearest"]]
