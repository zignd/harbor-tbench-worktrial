"""Seeded, resumable blinded instruction-origin experiment (historical pre-audit packages)."""

import json
import math
import random
from pathlib import Path

from analysis.human_likeness import DISCRIMINATION_PROMPT, _canary_free, stylometrics
from analysis.llm import chat, extract_json


def main() -> None:
    path = Path("docs/result/evidence/blind.json")
    rng = random.Random(20261013)
    humans = sorted(p for p in Path("examples").iterdir() if (p / "instruction.md").exists())
    generated = sorted(Path("runs/audit-20261013/pending").iterdir())
    pairs = [(h, g) for h in humans for g in generated]
    rng.shuffle(pairs)
    inputs = []
    for i, (h, g) in enumerate(pairs):
        human_a = rng.random() < 0.5
        texts = [_canary_free((p / "instruction.md").read_text()) for p in (h, g)]
        if not human_a:
            texts.reverse()
        inputs.append(
            {
                "pair": i,
                "truth": "A" if human_a else "B",
                "example": h.name,
                "generated": g.name,
                "prompt": DISCRIMINATION_PROMPT.format(a=texts[0], b=texts[1]),
            }
        )
    data = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "seed": 20261013,
            "model": "openai/gpt-5.6-luna",
            "inputs": inputs,
            "rows": [],
            "caveats": [
                "Repeated task pairs are not independent.",
                "Author judges its family outputs.",
                "Examples were format references; pre-audit packages, not final revised tasks.",
            ],
        }
    )
    done = {r["pair"] for r in data["rows"]}
    for item in inputs:
        if item["pair"] in done:
            continue
        reply = chat(item["prompt"], model=data["model"], max_tokens=3000, temperature=0)
        result = extract_json(reply.text)
        guess = result.get("human")
        data["rows"].append(
            {
                "pair": item["pair"],
                "truth": item["truth"],
                "guess": guess,
                "correct": guess == item["truth"],
                "valid_prediction": guess in ("A", "B"),
                "reply": result,
                "cost": reply.cost_usd,
            }
        )
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(item["pair"], guess == item["truth"], flush=True)
    n = len(data["rows"])
    k = sum(r["correct"] for r in data["rows"])
    p = k / n
    z = 1.96
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    data.update(
        {
            "pairs": n,
            "correct": k,
            "accuracy": p,
            "wilson95": [center - half, center + half],
            "cost": sum(r["cost"] for r in data["rows"]),
        }
    )
    path.write_text(json.dumps(data, indent=2) + "\n")
    Path("docs/result/evidence/stylometrics.json").write_text(
        json.dumps(
            {
                "examples": {p.name: stylometrics(p) for p in humans},
                "pre_audit_generated": {p.name: stylometrics(p) for p in generated},
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
