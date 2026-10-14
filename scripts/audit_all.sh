#!/usr/bin/env bash
# One-command verification of the audited submission.
#
#   bash scripts/audit_all.sh
#
# Runs every check that backs the claims in docs/result/report.md and
# docs/result/verification.json. Makes NO model calls and starts NO Docker builds, so it costs
# nothing and is safe to run at any time. Exits non-zero if any check fails, so it can gate CI.
set -uo pipefail
cd "$(dirname "$0")/.."

pass=0
fail=0
declare -a FAILED=()

check() {                     # check <name> <command...>
  local name="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    printf 'ok   %s\n' "$name"; pass=$((pass + 1))
  else
    printf 'FAIL %s\n' "$name"; fail=$((fail + 1)); FAILED+=("$name")
    printf '%s\n' "$out" | tail -5 | sed 's/^/       /'
  fi
}

echo "== repository hygiene (no gitlinks, no tracked secrets, no run outputs, no large blobs)"
check "repo hygiene" bash scripts/check_repo_hygiene.sh

echo "== code quality"
check "ruff lint" uv run --quiet ruff check . --exclude validator/validate.py
check "unit tests" uv run --quiet pytest -q

echo "== deliverables exist and are non-empty"
for f in docs/result/report.md docs/result/presentation.pptx docs/result/presentation.html \
         docs/result/verification.json docs/result/README.md output/README.md; do
  check "present: $f" test -s "$f"
done

echo "== the audit manifest"
check "manifest status is passed" \
  grep -Eq '"overall_status"[[:space:]]*:[[:space:]]*"passed"' docs/result/verification.json
check "exactly one approved task" \
  uv run --env-file .env python -c "
import json,sys
d=json.load(open('docs/result/verification.json'))
t=d['approved_tasks']
assert len(t)==1, t
assert t[0]['calibration']['verdict']=='learnable'
assert t[0]['calibration']['n_trials']==5
assert 1 <= t[0]['calibration']['legit_passes'] <= 3
assert all(t[0]['checks'].values()), t[0]['checks']
print(t[0]['task'], t[0]['package_hash'][:12], t[0]['calibration']['legit_passes'], 'of 5')
"
check "spend reconciliation is NOT claimed as met" \
  uv run --env-file .env python -c "
import json,sys
d=json.load(open('docs/result/verification.json'))
assert d['requirements']['spend reconciliation detail']['acceptance_met'] is False
print('unresolved, measured gap')
"

echo "== the approved package itself"
check "package hash matches its records" \
  uv run --env-file .env python -c "
from pathlib import Path
import json
from analysis.package_evidence import package_hash, approval_errors
from generator.config import MODEL_LABEL
t=next(p for p in sorted(Path('output').iterdir()) if p.is_dir()
       and json.loads((p/'verification.json').read_text()).get('status') == 'passed')
cal=json.loads((t/'calibration.json').read_text())
assert package_hash(t)==cal['package_hash']==json.loads((t/'verification.json').read_text())['package_hash']
assert approval_errors(t,cal,MODEL_LABEL)==[], approval_errors(t,cal,MODEL_LABEL)
print(t.name,'hash-bound, approval errors empty')
"
check "fresh-clone verification passed" \
  uv run python -c "
import json
d=json.load(open('docs/result/evidence/fresh-clone.json'))
assert d['all_ok'], d
print('clone', d['revision'][:12], 'all', len(d['tasks']), 'packages ok')
"

echo "== numbers in the deck and report trace to evidence"
check "deck/report consistency" uv run --quiet python -m scripts.audit_deck_consistency

echo "== the plan"
check "plan has no remaining items" bash -c "! bash scripts/track-plan.sh --remaining 2>/dev/null | grep -q 'docs/plan.md:'"

echo
echo "=============================================="
printf 'passed %d, failed %d\n' "$pass" "$fail"
if [ "$fail" -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED[@]}"
  exit 1
fi
echo "ALL CHECKS PASSED"
