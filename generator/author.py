"""Authoring via a Harbor meta-task (see docs/plan.md, "Changes from the full papers" 1).

The authoring model runs as terminus-2 inside the synthesis container described
by generator/metatask/, writes a task package to /app/output, and Harbor copies
it to <trial>/artifacts/ (task.toml `artifacts`). This module renders that
meta-task for one blueprint.

    uv run python -m generator.author render BLUEPRINT.md SLUG OUT_DIR
"""

import shutil
import sys
from pathlib import Path
from string import Template

from generator.config import CANARY_LINE, EXAMPLES_DIR

TEMPLATE_DIR = Path(__file__).parent / "metatask"
STANDARD_TEST_SH = TEMPLATE_DIR / "standard_test.sh"
TASK_ORG = "zignd"
DEFAULT_REFERENCE = "openssl-selfsigned-cert"  # format reference only, never content


REPAIR_SECTION = """

## Repair round

A previous attempt at this package is in `/app/previous/` and failed the pipeline's checks.
Start from it: `cp -r /app/previous/. /app/output/`, then fix the problems below. Keep what
already works, and re-run every check in "Before you finish" before you stop.

Problems found:
{feedback}
"""


def render_metatask(
    blueprint: str,
    slug: str,
    out_dir: Path,
    reference: str = DEFAULT_REFERENCE,
    previous: Path | None = None,
    feedback: list[str] | None = None,
) -> Path:
    """Write a runnable meta-task for `blueprint` into `out_dir` and return it.

    With `previous` (a failed package) and `feedback`, render a repair round: the
    old package is baked into the synthesis image at /app/previous.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(
        TEMPLATE_DIR, out_dir, ignore=shutil.ignore_patterns("*.tmpl", "standard_test.sh")
    )
    shutil.copytree(Path(EXAMPLES_DIR) / reference, out_dir / "environment" / "reference")
    shutil.copy(STANDARD_TEST_SH, out_dir / "environment" / "standard_test.sh")

    instruction = Template((TEMPLATE_DIR / "instruction.md.tmpl").read_text())
    (out_dir / "instruction.md").write_text(
        instruction.substitute(
            BLUEPRINT=blueprint.strip(),
            TASK_NAME=f"{TASK_ORG}/{slug}",
            CANARY_LINE=CANARY_LINE,
        )
    )
    task_toml = out_dir / "task.toml"
    task_toml.write_text(
        Template(task_toml.read_text()).substitute(TASK_NAME=f"{TASK_ORG}/metatask-{slug}")
    )
    if previous is not None:
        shutil.copytree(previous, out_dir / "environment" / "previous")
        dockerfile = out_dir / "environment" / "Dockerfile"
        dockerfile.write_text(dockerfile.read_text() + "COPY previous /app/previous\n")
        items = "\n".join(f"- {item}" for item in (feedback or ["(no details recorded)"]))
        with (out_dir / "instruction.md").open("a") as f:
            f.write(REPAIR_SECTION.format(feedback=items))
    return out_dir


def collect_package(trial_dir: Path, dest: Path) -> Path:
    """Copy the authored package out of a finished meta-task trial's artifacts."""
    src = trial_dir / "artifacts" / "app" / "output"
    if not src.is_dir():
        raise FileNotFoundError(f"no authored package in {src}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    )
    # The verifier entry point is pipeline-owned: always replace whatever the author left.
    shutil.copy(STANDARD_TEST_SH, dest / "tests" / "test.sh")
    return dest


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "render":
        sys.exit(__doc__)
    _, _, blueprint_path, slug, out = sys.argv
    print(render_metatask(Path(blueprint_path).read_text(), slug, Path(out)))
