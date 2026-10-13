#!/usr/bin/env bash
# Repository hygiene checks: no embedded git repositories, no committed secrets, no large blobs.
#
#   bash scripts/check_repo_hygiene.sh
#
# Exit 0 when clean, 1 otherwise. Embedded git repositories (gitlinks) break fresh clones:
# a clone of the outer repo does not contain the nested repository's contents, so a task whose
# environment depends on it would not build from a fresh clone. Nested histories are preserved
# as .bundle files instead.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0

gitlinks=$(git ls-files -s | awk '$1 == "160000" { print $4 }')
if [ -n "$gitlinks" ]; then
  echo "FAIL: embedded git repositories in the index (gitlinks):"
  echo "$gitlinks" | sed 's/^/  /'
  fail=1
else
  echo "ok: no embedded git repositories (gitlinks)"
fi

# Secrets that must never be committed.
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "FAIL: .env is tracked"
  fail=1
else
  echo "ok: .env is not tracked"
fi

leaks=$(git grep -nIE '(OPENROUTER|ANTHROPIC|OPENAI)_API_KEY[[:space:]]*=[[:space:]]*["'"'"']?[A-Za-z0-9_-]{16,}' -- \
  ':!*.example' ':!.env.example' 2>/dev/null | head -5)
if [ -n "$leaks" ]; then
  echo "FAIL: possible API key in tracked files:"
  echo "$leaks" | sed 's/^/  /'
  fail=1
else
  echo "ok: no API keys in tracked files"
fi

# Run outputs must stay out of the repository.
for d in jobs trials output-dev data; do
  if git ls-files --error-unmatch "$d" >/dev/null 2>&1; then
    echo "FAIL: $d/ is tracked"
    fail=1
  fi
done
echo "ok: jobs/, trials/, output-dev/ and data/ are not tracked"

# Oversized tracked files (the pipeline must not commit Docker layers or PDFs).
big=$(git ls-files -z | xargs -0 stat -f '%z %N' 2>/dev/null | awk '$1 > 20000000 { print $1, $2 }' | head -5)
if [ -n "$big" ]; then
  echo "FAIL: tracked files larger than 20 MB:"
  echo "$big" | sed 's/^/  /'
  fail=1
else
  echo "ok: no tracked file larger than 20 MB"
fi

exit "$fail"
