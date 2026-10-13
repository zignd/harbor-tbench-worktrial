#!/bin/bash
set -euo pipefail

SVC=/app/entropy_service
cd "$SVC"

git config --global user.email "ci@entropy-audit.internal"
git config --global user.name "CI Bot"
git config --global init.defaultBranch main

if [ -d .git ]; then
    echo "Git repo already initialised"
    exit 0
fi

git init

# Commit 1
git add requirements.txt
git commit -m "init: add requirements"

# Commit 2
git add ingestion.py
git commit -m "feat: add byte stream reader and window segmenter"

# Commit 3
git add schema.py
git commit -m "feat: add schema definitions for audit results"

# Commit 4
git add utils.py
git commit -m "feat: add utility functions and rolling stats"

# Commit 5 - reference DSP with CORRECT implementation
# Save the buggy dsp.py and create a correct version
cp dsp.py /tmp/_dsp_buggy.py

python3 - << 'PYEOF'
with open('dsp.py') as f:
    lines = f.readlines()

# Find the _compute_stft_vectorized function and replace its body
# with the correct implementation (center before Hann, float64 throughout)
start = None
end = None
for i, line in enumerate(lines):
    if 'def _compute_stft_vectorized(' in line:
        start = i
    elif start is not None and line.startswith('def ') and i > start + 2:
        end = i
        break

assert start is not None and end is not None, f'bounds: {start} {end}'

correct_body = '''def _compute_stft_vectorized(windows, hann):
    """
    Vectorized STFT path for large batches.

    Performance-optimized path that processes all windows simultaneously
    using numpy broadcasting.

    Parameters
    ----------
    windows : np.ndarray
        Shape (n_windows, window_size), dtype float64.
    hann : np.ndarray
        Hann window coefficients, shape (window_size,), dtype float64.

    Returns
    -------
    np.ndarray
        Magnitude spectra, shape (n_windows, N_FREQ_BINS).
    """
    # Center each window before applying the Hann window
    means = windows.mean(axis=1, keepdims=True)
    w = windows - means
    w = w * hann
    spectra = np.fft.rfft(w, n=FFT_SIZE, axis=1)
    magnitudes = np.abs(spectra[:, 1:N_FREQ_BINS+1])
    return magnitudes


'''

new_lines = lines[:start] + [correct_body] + lines[end:]
with open('dsp.py', 'w') as f:
    f.writelines(new_lines)
print(f'Wrote correct dsp.py (replaced lines {start}-{end})')
PYEOF

git add dsp.py
git commit -m "feat: add reference STFT spectral entropy implementation"

# Commit 6
git add monitor.py
git commit -m "feat: add continuous monitoring daemon stub"

# Commit 7
git add reporter.py
git commit -m "feat: add entropy reporter and calibration manager"

# Commit 8
git add audit_runner.py
git commit -m "feat: add audit_runner CLI entrypoint"

# Commit 9
git add tests/
git commit -m "test: add CI test suite for DSP pipeline"

# Commit 10
git add rng_feed_03/
git commit -m "data: add rng_feed_03 HWRNG sample data"

# Commit 11
git add calibration/
git commit -m "feat: add empty calibration directory"

# Commit 12
cat > .ci_config.yml << 'CIEOF'
pipeline:
  name: entropy-audit
  version: 1.3.0
  stages:
    - lint
    - test
    - audit
  test_command: "python -m pytest tests/ -q"
  audit_sources:
    - rng_feed_03
  max_windows: 200
  alert_on_degenerate: true
CIEOF
git add .ci_config.yml
git commit -m "chore: update CI pipeline configuration"

# Commit 13
git commit --allow-empty -m "refactor: reorganize ingestion module"

# Commit 14 - THE REGRESSION: restore the buggy dsp.py
cp /tmp/_dsp_buggy.py dsp.py
git add dsp.py
git commit -m "perf: vectorize STFT window batch for large inputs"

# Commit 15
printf '1.3.0\n' > VERSION
git add VERSION
git commit -m "chore: bump version to 1.3.0"

# Commit 16
cat > README.md << 'RDEOF'
# Entropy Audit Pipeline

Audits hardware RNG entropy sources using spectral analysis.

## Usage

    python audit_runner.py --source rng_feed_03 --report
    python audit_runner.py --source <id> --calibrate --input <file.bin>
    python audit_runner.py --source <id> --report --input <file.bin> --apply-cal

## Calibration workflow

1. Obtain a reference file of known-good entropy bytes.
2. Run --calibrate to compute and store an offset.
3. Run --report --apply-cal to apply the stored offset.
RDEOF
git add README.md
git commit -m "docs: update README with calibration workflow"

# Commit 17
cat > nightly.sh << 'NEOF'
#!/bin/bash
set -e
cd /app/entropy_service
python audit_runner.py --source rng_feed_03 --report
echo "Nightly check complete"
NEOF
chmod +x nightly.sh
git add nightly.sh
git commit -m "ci: add nightly data-quality checks"

# Commit 18
git commit --allow-empty -m "fix: handle edge case in stream reader"

echo "Git history created: $(git rev-list --count HEAD) commits"
git log --oneline
