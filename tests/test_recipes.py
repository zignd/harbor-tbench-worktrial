"""Toolchain recipes: the synthesis image must install toolchains with the recipes' exact lines."""

from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / "generator" / "metatask" / "environment"


def test_synthesis_image_runs_each_recipes_toolchain_install_verbatim():
    dockerfile = (ENV / "Dockerfile").read_text()
    recipes = sorted((ENV / "recipes").glob("*.dockerfile"))
    assert {r.stem for r in recipes} == {"c", "go", "node", "rust"}
    for recipe in recipes:
        lines = [ln for ln in recipe.read_text().splitlines() if ln.startswith(("RUN", "ENV"))]
        toolchain = [ln for ln in lines if "apt-get" not in ln]  # apt deps differ by design
        for line in toolchain:
            assert line in dockerfile, f"{recipe.name}: {line}"
