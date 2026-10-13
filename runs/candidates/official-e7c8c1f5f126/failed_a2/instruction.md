You are auditing the entropy-quality pipeline at /app/entropy_service/. The pipeline ingests streams of raw bytes from hardware RNG sources, segments them into overlapping windows, computes a Short-Time Fourier Transform (STFT) over each window, and derives a per-window spectral entropy estimate. Healthy HWRNG sources should produce consistent spectral entropy estimates; a degenerate or biased source produces measurably lower values.

Running the pipeline against the included rng_feed_03 source produces garbage entropy estimates (near-zero values) for a subset of windows, even though rng_feed_03 is a confirmed healthy source. This is a false alarm caused by a regression in the pipeline code.

Your tasks:

1. Investigate the git history at /app/entropy_service/ and identify what changed and why certain windows produce near-zero entropy estimates on healthy input. Fix the pipeline so that audit_runner.py --source rng_feed_03 --report produces spectral entropy estimates in a consistent range (no near-zero values) for all windows.

2. Implement the --calibrate mode in audit_runner.py. When invoked as audit_runner.py --calibrate --source <source_id> --input <file.bin>, the pipeline must compute spectral entropies for all windows in the given file, compute the calibration offset defined as mean(spectral_entropies) - 8.0, and write the offset as a float with exactly 4 decimal places to calibration/<source_id>.cal. The offset is stored with its sign.

3. Ensure that when audit_runner.py --report --source <source_id> --input <file.bin> --apply-cal is run after calibration, every window's spectral entropy estimate is within +/-0.15 bits of 8.0 for any 1 MB block of uniform-random bytes.

4. The existing CI tests in tests/ must continue to pass.

The spectral entropy formula used throughout the pipeline is: H = -sum(p * log2(p)) where p = |FFT|^2 / sum(|FFT|^2) computed over the 256 positive-frequency bins (bins 1 through 256) of a 512-point FFT. This formula must remain unchanged.

The verifier will supply its own reference files and source streams not present in the repository.
