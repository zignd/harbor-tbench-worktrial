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

mkdir -p src tests benches

python3 /app/write_repo_files.py "$REPO" initial

git add -A
git commit -m "initial project scaffold: packet-codec library"

python3 /app/write_repo_files.py "$REPO" add_tests
git add -A
git commit -m "add comprehensive unit tests for codec and frame modules"

python3 /app/write_repo_files.py "$REPO" add_readme
git add -A
git commit -m "add criterion benchmark harness for throughput measurement"

git checkout -b old-pipeline
git commit -m "old-pipeline: stable release with verified roundtrip performance" --allow-empty

git checkout main

python3 /app/write_repo_files.py "$REPO" apply_bugs
git add -A
git commit -m "harden codec bounds checks and update frame delimiter logic"

python3 /app/write_repo_files.py "$REPO" degrade_profile
git add -A
git commit -m "update Cargo config for new CI pipeline requirements"

python3 /app/write_repo_files.py "$REPO" add_migration_notes
git add -A
git commit -m "migrate build pipeline: add migration notes and update documentation"

git commit --allow-empty -m "expand integration test coverage for edge cases" --allow-empty

git log --oneline --all
