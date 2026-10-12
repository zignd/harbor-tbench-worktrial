#!/bin/bash
set -e

REPO=/app/repo
rm -rf "$REPO"
mkdir -p "$REPO"
cd "$REPO"

git init
git checkout -b main 2>/dev/null || git branch -m master main 2>/dev/null || true
git config user.email "dev@internal.example.com"
git config user.name "Platform Team"

mkdir -p src/bin tests benches

# Stage 1: initial project scaffold
python3 /app/write_repo_files.py "$REPO" initial
git add -A
git commit -m "initial project scaffold: packet-codec library"

# Stage 2: add test suite
python3 /app/write_repo_files.py "$REPO" add_tests
git add -A
git commit -m "add comprehensive unit tests for codec and frame modules"

# Stage 3: add benchmark harness and readme
python3 /app/write_repo_files.py "$REPO" add_readme
git add -A
git commit -m "add criterion benchmark harness for throughput measurement"

# Create old-pipeline branch from this stable, correct state
git checkout -b old-pipeline
git commit -m "old-pipeline: stable release with verified roundtrip performance" --allow-empty
git checkout main

# Stage 4: apply the bugs (main branch migration regressions)
python3 /app/write_repo_files.py "$REPO" apply_bugs
git add -A
git commit -m "harden codec bounds checks and update frame delimiter logic"

# Stage 5: degrade build profile
python3 /app/write_repo_files.py "$REPO" degrade_profile
git add -A
git commit -m "update Cargo config for new CI pipeline requirements"

# Stage 6: add migration notes (misdirection)
python3 /app/write_repo_files.py "$REPO" add_migration_notes
git add -A
git commit -m "migrate build pipeline: add migration notes and update documentation"

git commit --allow-empty -m "expand integration test coverage for edge cases"

git log --oneline --all
