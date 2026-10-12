#!/bin/bash
set -e

cd /app

git config --global user.email "eng@dataplatform.internal"
git config --global user.name "Data Platform Bot"
git config --global init.defaultBranch main

git init -q

# Commit 1: Initial scaffold
git add pipeline/__init__.py pipeline/schema.py pipeline/utils.py
GIT_AUTHOR_DATE="2023-06-01T09:00:00" GIT_COMMITTER_DATE="2023-06-01T09:00:00" \
  git commit -q -m "Initial pipeline scaffold with schema and utils"

# Commit 2: Add chunker
git add pipeline/chunker.py
GIT_AUTHOR_DATE="2023-06-15T10:30:00" GIT_COMMITTER_DATE="2023-06-15T10:30:00" \
  git commit -q -m "Add CSV chunker module"

# Commit 3: Add transform
git add pipeline/transform.py
GIT_AUTHOR_DATE="2023-07-02T14:00:00" GIT_COMMITTER_DATE="2023-07-02T14:00:00" \
  git commit -q -m "Add transform module with schema validation"

# Commit 4: Add assembler
git add pipeline/assembler.py
GIT_AUTHOR_DATE="2023-07-20T11:00:00" GIT_COMMITTER_DATE="2023-07-20T11:00:00" \
  git commit -q -m "Add assembler module"

# Commit 5: Add run_pipeline.py
git add run_pipeline.py
GIT_AUTHOR_DATE="2023-08-05T09:30:00" GIT_COMMITTER_DATE="2023-08-05T09:30:00" \
  git commit -q -m "Add CLI driver run_pipeline.py"

# Commit 6: Add data fixtures and tests
git add data/
GIT_AUTHOR_DATE="2023-08-20T16:00:00" GIT_COMMITTER_DATE="2023-08-20T16:00:00" \
  git commit -q -m "Add sample data fixtures"

# Commit 7: Add verify script
git add verify_output.py
GIT_AUTHOR_DATE="2023-09-10T13:00:00" GIT_COMMITTER_DATE="2023-09-10T13:00:00" \
  git commit -q -m "Add output verification script"

# Commit 8: README
cat > /app/README.md << 'HEREDOC'
# CSV Chunk Recovery Pipeline

A production ETL pipeline for processing large CSV files in configurable chunks.

## Usage

```bash
python run_pipeline.py --input data/sample.csv --output out/result.csv
```

## Components

- `pipeline/chunker.py`: Splits input CSV into fixed-size chunk files
- `pipeline/transform.py`: Applies schema validation and type coercion
- `pipeline/assembler.py`: Reassembles processed chunks into final output
- `run_pipeline.py`: CLI driver
- `verify_output.py`: Output quality checker
HEREDOC
git add README.md
GIT_AUTHOR_DATE="2023-09-25T10:00:00" GIT_COMMITTER_DATE="2023-09-25T10:00:00" \
  git commit -q -m "Add README"

# Commit 9: Performance note in chunker
python3 -c "
with open('/app/pipeline/chunker.py', 'a') as f:
    f.write('\n# Performance note: chunk size tuned for L2 cache efficiency on target hardware\n')
"
git add pipeline/chunker.py
GIT_AUTHOR_DATE="2023-10-15T09:00:00" GIT_COMMITTER_DATE="2023-10-15T09:00:00" \
  git commit -q -m "Tune chunk size for cache performance"

# Commit 10: Add .gitignore
cat > /app/.gitignore << 'HEREDOC'
__pycache__/
*.pyc
.pytest_cache/
out/
output/
previous/
recipes/
*.egg-info/
HEREDOC
git add .gitignore
GIT_AUTHOR_DATE="2023-11-01T14:00:00" GIT_COMMITTER_DATE="2023-11-01T14:00:00" \
  git commit -q -m "Add .gitignore"

# Commit 11: Add schema version constant
python3 -c "
with open('/app/pipeline/schema.py', 'r') as f:
    content = f.read()
# Add version after DATE_FORMAT line
content = content.replace(
    'DATE_FORMAT = \"%Y-%m-%d\"',
    'DATE_FORMAT = \"%Y-%m-%d\"\n\nSCHEMA_VERSION = \"1.0\"'
)
with open('/app/pipeline/schema.py', 'w') as f:
    f.write(content)
"
git add pipeline/schema.py
GIT_AUTHOR_DATE="2023-12-01T11:00:00" GIT_COMMITTER_DATE="2023-12-01T11:00:00" \
  git commit -q -m "Add schema version constant"

# Commit 12: Schema version bump to 1.1
python3 -c "
with open('/app/pipeline/schema.py', 'r') as f:
    content = f.read()
content = content.replace('SCHEMA_VERSION = \"1.0\"', 'SCHEMA_VERSION = \"1.1\"')
with open('/app/pipeline/schema.py', 'w') as f:
    f.write(content)
"
git add pipeline/schema.py
GIT_AUTHOR_DATE="2024-01-15T09:00:00" GIT_COMMITTER_DATE="2024-01-15T09:00:00" \
  git commit -q -m "Bump schema version to 1.1"

# Commit 13: Add requirements.txt
cat > /app/requirements.txt << 'HEREDOC'
pandas==2.2.3
click==8.1.7
HEREDOC
git add requirements.txt
GIT_AUTHOR_DATE="2024-02-01T10:00:00" GIT_COMMITTER_DATE="2024-02-01T10:00:00" \
  git commit -q -m "Add requirements.txt"

# Commit 14: Document chunker self-contained chunk design
python3 -c "
with open('/app/pipeline/chunker.py', 'r') as f:
    content = f.read()
old = '        The header is written unconditionally so that each chunk file\n        is self-describing and can be processed independently by\n        external consumers that do not share state.'
new = '        The header is written unconditionally so that each chunk file\n        is self-describing and can be processed independently by\n        external consumers that do not share state.\n\n        Note: downstream assemblers must account for the header present\n        in every chunk file when reassembling results.'
content = content.replace(old, new)
with open('/app/pipeline/chunker.py', 'w') as f:
    f.write(content)
"
git add pipeline/chunker.py
GIT_AUTHOR_DATE="2024-03-10T14:00:00" GIT_COMMITTER_DATE="2024-03-10T14:00:00" \
  git commit -q -m "Document chunker self-contained chunk design"

# Commit 15: Document dedup column subset rationale in transform
python3 -c "
with open('/app/pipeline/transform.py', 'r') as f:
    content = f.read()
old = '        Deduplication is performed on the business-key columns that\n        identify logically equivalent records within a delivery batch.\n        When duplicates are found, the first occurrence is kept.'
new = '        Deduplication is performed on the business-key columns that\n        identify logically equivalent records within a delivery batch.\n        When duplicates are found, the first occurrence is kept.\n\n        Using a subset of columns rather than the full row improves\n        performance on wide DataFrames and matches business semantics.'
content = content.replace(old, new)
with open('/app/pipeline/transform.py', 'w') as f:
    f.write(content)
"
git add pipeline/transform.py
GIT_AUTHOR_DATE="2024-04-01T09:00:00" GIT_COMMITTER_DATE="2024-04-01T09:00:00" \
  git commit -q -m "Document dedup column subset rationale"

echo "Git repository initialized with 15 commits."
git log --oneline
