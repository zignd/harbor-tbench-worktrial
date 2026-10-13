#!/usr/bin/env python3
"""Set up realistic git history for the audit-log service repository."""
import subprocess
import os
import sys

REPO_DIR = '/app'

def run(cmd, env=None):
    e = {**os.environ, 'GIT_AUTHOR_NAME': 'DevOps Bot',
         'GIT_AUTHOR_EMAIL': 'devops@example.com',
         'GIT_COMMITTER_NAME': 'DevOps Bot',
         'GIT_COMMITTER_EMAIL': 'devops@example.com'}
    if env:
        e.update(env)
    r = subprocess.run(cmd, shell=True, cwd=REPO_DIR, env=e,
                       capture_output=True, text=True)
    return r

def commit(msg, date, changes=None):
    """Apply changes dict {path: content} then commit."""
    e = {'GIT_AUTHOR_DATE': date, 'GIT_COMMITTER_DATE': date,
         'GIT_AUTHOR_NAME': 'DevOps Bot', 'GIT_AUTHOR_EMAIL': 'devops@example.com',
         'GIT_COMMITTER_NAME': 'DevOps Bot', 'GIT_COMMITTER_EMAIL': 'devops@example.com'}
    if changes:
        for path, content in changes.items():
            full = os.path.join(REPO_DIR, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'a') as f:
                f.write(content)
    run('git add -A', env=e)
    run(f'git commit --allow-empty -m "{msg}"', env=e)

def main():
    run('git config --global user.email "devops@example.com"')
    run('git config --global user.name "DevOps Bot"')
    # Remove existing git repo and start fresh
    subprocess.run('rm -rf .git', shell=True, cwd=REPO_DIR)
    run('git init')
    run('git checkout -b main')

    marker = 'audit_service/.gitkeep'

    commit('Initial project skeleton', '2025-04-01T09:00:00',
           {marker: ''})
    commit('chore: Add chain config and genesis seed', '2025-04-08T11:00:00',
           {'config/.gitkeep': ''})
    commit('feat: Add audit log file parser', '2025-04-15T14:30:00',
           {'audit_service/parser.py': ''})
    commit('docs: Add chain algorithm specification', '2025-04-22T10:00:00',
           {'tools/chain_spec.md': ''})
    commit('feat: Add compiled HMAC chain derivation module', '2025-05-01T09:15:00',
           {'audit_service/__init__.py': ''})
    commit('feat: Add log verifier using chain module', '2025-05-08T16:00:00',
           {'audit_service/verifier.py': ''})
    commit('feat: Add stdin/stdout protocol service', '2025-05-15T11:45:00',
           {'audit_service/service.py': ''})
    commit('tools: Add deterministic log generator', '2025-05-22T14:00:00',
           {'tools/generate_logs.py': ''})
    commit('chore: Add pre-generated sample log files', '2025-05-29T09:30:00',
           {'logs/.gitkeep': ''})
    commit('docs: Add README with service overview', '2025-06-05T10:00:00',
           {'README.md': ''})
    commit('refactor: Tighten header validation regex', '2025-06-15T15:00:00',
           {marker: '# v2\n'})
    commit('perf: Reduce allocations in chain verification loop', '2025-07-01T11:00:00',
           {marker: '# v3\n'})
    commit('refactor: Simplify chain key derivation lookup', '2025-08-01T14:30:00',
           {marker: '# v4\n'})
    commit('chore: Remove unused imports in verifier', '2025-08-15T10:00:00',
           {marker: '# v5\n'})
    commit('docs: Update chain spec with performance notes', '2025-09-01T09:00:00',
           {marker: '# v6\n'})
    commit('feat: Add structured logging to protocol handler', '2025-09-15T16:00:00',
           {marker: '# v7\n'})
    commit('style: Fix line length in parser module', '2025-10-01T11:00:00',
           {marker: '# v8\n'})

    r = run('git log --oneline | wc -l')
    count = r.stdout.strip()
    print(f'Git history created with {count} commits')

if __name__ == '__main__':
    main()
