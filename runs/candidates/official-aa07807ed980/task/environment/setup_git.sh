#!/bin/bash
set -e

cd /app

git config --global user.email "datateam@example.com"
git config --global user.name "Data Team"
git config --global init.defaultBranch main

# Create .gitignore to exclude non-pipeline files
cat > .gitignore << EOF
__pycache__/
*.pyc
*.pyo
.pytest_cache/
out/
*.egg-info/
dist/
build/
fixes/
output/
recipes/
setup_git.sh
EOF

git init
git add pipeline/ data/ run_pipeline.py verify_output.py tests/ .gitignore
GIT_AUTHOR_DATE="2023-04-01T10:00:00" GIT_COMMITTER_DATE="2023-04-01T10:00:00"   git commit -m "Initial commit: pipeline scaffold"

# Simulate 14 more commits over 18 months
GIT_AUTHOR_DATE="2023-05-15T14:30:00" GIT_COMMITTER_DATE="2023-05-15T14:30:00"   git commit --allow-empty -m "pipeline: add schema validation module"

GIT_AUTHOR_DATE="2023-06-20T09:15:00" GIT_COMMITTER_DATE="2023-06-20T09:15:00"   git commit --allow-empty -m "chunker: support configurable chunk size"

GIT_AUTHOR_DATE="2023-07-10T16:45:00" GIT_COMMITTER_DATE="2023-07-10T16:45:00"   git commit --allow-empty -m "transform: add date normalisation step"

GIT_AUTHOR_DATE="2023-08-22T11:00:00" GIT_COMMITTER_DATE="2023-08-22T11:00:00"   git commit --allow-empty -m "utils: add Timer context manager"

GIT_AUTHOR_DATE="2023-09-05T13:20:00" GIT_COMMITTER_DATE="2023-09-05T13:20:00"   git commit --allow-empty -m "assembler: initial concat implementation"

GIT_AUTHOR_DATE="2023-10-18T15:10:00" GIT_COMMITTER_DATE="2023-10-18T15:10:00"   git commit --allow-empty -m "tests: add unit tests for transform module"

GIT_AUTHOR_DATE="2023-12-01T10:30:00" GIT_COMMITTER_DATE="2023-12-01T10:30:00"   git commit --allow-empty -m "pipeline: wire CLI driver with click"

GIT_AUTHOR_DATE="2024-01-14T09:00:00" GIT_COMMITTER_DATE="2024-01-14T09:00:00"   git commit --allow-empty -m "chunker: write header to every chunk for external consumers"

GIT_AUTHOR_DATE="2024-02-28T14:00:00" GIT_COMMITTER_DATE="2024-02-28T14:00:00"   git commit --allow-empty -m "schema: tighten record_id validation rules"

GIT_AUTHOR_DATE="2024-04-03T11:45:00" GIT_COMMITTER_DATE="2024-04-03T11:45:00"   git commit --allow-empty -m "transform: switch dedup to business-key subset"

GIT_AUTHOR_DATE="2024-06-17T16:00:00" GIT_COMMITTER_DATE="2024-06-17T16:00:00"   git commit --allow-empty -m "assembler: refactor chunk reader helper"

GIT_AUTHOR_DATE="2024-08-09T10:15:00" GIT_COMMITTER_DATE="2024-08-09T10:15:00"   git commit --allow-empty -m "pipeline: add rejected rows output path option"

GIT_AUTHOR_DATE="2024-10-22T13:30:00" GIT_COMMITTER_DATE="2024-10-22T13:30:00"   git commit --allow-empty -m "utils: add progress_bar helper"

GIT_AUTHOR_DATE="2024-12-31T17:00:00" GIT_COMMITTER_DATE="2024-12-31T17:00:00"   git commit --allow-empty -m "docs: update README for v1.4 release"

echo "Git history initialized with $(git log --oneline | wc -l) commits"
