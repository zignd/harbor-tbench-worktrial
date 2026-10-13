import json
from pathlib import Path

from analysis.llm import Reply
from generator import package_review

FIX = Path(__file__).parent / "fixtures"
TASK = FIX / "harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"


def _chat(review: dict):
    seen = {}

    def chat_fn(prompt, **kwargs):
        seen["prompt"] = prompt
        return Reply(json.dumps(review), "m", 10, 0, 10, 0.05, 0.1)

    return chat_fn, seen


def test_prompt_carries_the_promise_the_files_and_the_solution():
    chat_fn, seen = _chat({"difficulty": 4, "speedrun_commands": 40})
    package_review.review_package(TASK, "an opaque compiled component", chat_fn=chat_fn)
    prompt = seen["prompt"]
    assert "an opaque compiled component" in prompt and " lines)" in prompt
    assert (TASK / "solution" / "solve.sh").read_text()[:40] in prompt
    assert "ledger/" in prompt or "importer" in prompt  # the environment listing is included


def test_accepts_a_hard_package_and_rejects_a_speedrun_one():
    ok, _ = _chat({"difficulty": 4, "speedrun_commands": 40})
    assert package_review.review_package(TASK, "x", chat_fn=ok)["accepted"]
    easy, _ = _chat({"difficulty": 4, "speedrun_commands": 6})  # a short path overrides the score
    assert not package_review.review_package(TASK, "x", chat_fn=easy)["accepted"]
    low, _ = _chat({"difficulty": 2, "speedrun_commands": 30})
    assert not package_review.review_package(TASK, "x", chat_fn=low)["accepted"]


def test_vendored_dirs_are_not_listed(tmp_path):
    env = tmp_path / "environment"
    (env / "node_modules" / "a").mkdir(parents=True)
    (env / "node_modules" / "a" / "x.js").write_text("x")
    (env / "src").mkdir()
    (env / "src" / "app.py").write_text("print(1)\n")
    listing = package_review.environment_listing(tmp_path)
    assert "src/app.py" in listing and "node_modules" not in listing
