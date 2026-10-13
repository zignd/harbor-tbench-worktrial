"""Figure for the study report: verdict shares per author -> solver cell (docs/figures/).

    uv run python -m analysis.study_figure
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analysis.study import RESULTS, VERDICTS
from generator.config import REPO_ROOT

COLORS = {"in_band": "#2a9d8f", "too_easy": "#e9c46a", "too_hard": "#264653", "invalid": "#c0392b"}
OUT = Path(REPO_ROOT) / "docs" / "figures" / "study-2x2.png"


def draw(summary: dict, out: Path = OUT) -> Path:
    cells = summary["cells"]
    names = list(cells)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bottoms = [0.0] * len(names)
    for verdict in VERDICTS:
        shares = []
        for n in names:
            c = cells[n]
            shares.append(c["verdicts"][verdict] / c["valid"] if c["valid"] else 0.0)
        ax.bar(names, shares, bottom=bottoms, color=COLORS[verdict], label=verdict.replace("_", " "))
        bottoms = [b + s for b, s in zip(bottoms, shares, strict=True)]
    for i, n in enumerate(names):
        c = cells[n]
        mean = f"{c['mean_pass_rate']:.2f}" if c["mean_pass_rate"] is not None else "n/a"
        ax.text(i, 1.03, f"n={c['valid']}\nmean pass {mean}", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("share of valid tasks")
    ax.set_title("Who writes the task, who solves it (exploratory study)", fontsize=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, fontsize=8)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    return out


if __name__ == "__main__":
    print(draw(json.loads(RESULTS.read_text())["summary"]))
