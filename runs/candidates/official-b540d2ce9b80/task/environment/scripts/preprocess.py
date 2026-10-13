
import json
import sys


def compute_passes(module):
    """
    Compute optimization passes for a module descriptor.

    Module descriptor fields:
      id: str
      type: str  (util, lib, app, vendor, ...)
      complexity_score: int
      has_side_effects: bool

    Rules:
      dead_code_elimination: type in [util, lib] AND NOT has_side_effects
      const_folding: complexity_score < 40
      scope_hoisting: type == lib OR (type == util AND complexity_score < 20)
    """
    passes = []
    mod_type = module.get("type", "")
    score = module.get("complexity_score", 0)
    side_effects = module.get("has_side_effects", False)

    if mod_type in ("util", "lib") and not side_effects:
        passes.append("dead_code_elimination")

    if score < 40:
        passes.append("const_folding")

    if mod_type == "lib" or (mod_type == "util" and score < 20):
        passes.append("scope_hoisting")

    return passes


def process_modules(descriptors):
    results = []
    for desc in descriptors:
        results.append({
            "id": desc["id"],
            "passes": compute_passes(desc)
        })
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: preprocess.py <descriptors.json>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    with open(input_path, "r") as f:
        descriptors = json.load(f)

    results = process_modules(descriptors)
    print(json.dumps(results, indent=2))
