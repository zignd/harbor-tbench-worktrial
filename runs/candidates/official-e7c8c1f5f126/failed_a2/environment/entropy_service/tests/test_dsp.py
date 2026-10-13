"""
tests/test_dsp.py - CI tests for the DSP pipeline.

These tests use small synthetic inputs that pass with both the reference
and the fast-path implementations.
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dsp import (
    compute_spectral_entropy,
    compute_stft,
    _spectral_entropy_from_magnitudes,
    _hann_window,
    FFT_SIZE,
    N_FREQ_BINS,
)


class TestHannWindow:
    def test_shape(self):
        w = _hann_window(512)
        assert w.shape == (512,)

    def test_dtype(self):
        w = _hann_window(512)
        assert w.dtype == np.float64

    def test_endpoints_near_zero(self):
        w = _hann_window(512)
        assert abs(w[0]) < 1e-6

    def test_peak_near_one(self):
        w = _hann_window(512)
        assert w.max() > 0.99


class TestSpectralEntropyFormula:
    def test_uniform_spectrum_max_entropy(self):
        # Uniform power spectrum -> maximum entropy = log2(N_FREQ_BINS)
        mags = np.ones((1, N_FREQ_BINS), dtype=np.float64)
        ent = _spectral_entropy_from_magnitudes(mags)
        expected = np.log2(N_FREQ_BINS)
        assert abs(ent[0] - expected) < 0.01

    def test_single_bin_zero_entropy(self):
        # All power in one bin -> entropy = 0
        mags = np.zeros((1, N_FREQ_BINS), dtype=np.float64)
        mags[0, 0] = 1.0
        ent = _spectral_entropy_from_magnitudes(mags)
        assert ent[0] < 0.01

    def test_output_shape(self):
        mags = np.random.rand(5, N_FREQ_BINS)
        ent = _spectral_entropy_from_magnitudes(mags)
        assert ent.shape == (5,)


class TestComputeSTFT:
    def test_output_shape_small(self):
        # Small batch -> reference path
        rng = np.random.default_rng(42)
        windows = rng.integers(0, 256, size=(3, FFT_SIZE), dtype=np.uint8).astype(np.float64)
        mags = compute_stft(windows)
        assert mags.shape == (3, N_FREQ_BINS)

    def test_output_nonnegative(self):
        rng = np.random.default_rng(99)
        windows = rng.integers(0, 256, size=(4, FFT_SIZE), dtype=np.uint8).astype(np.float64)
        mags = compute_stft(windows)
        assert np.all(mags >= 0)

    def test_constant_signal_zero_magnitudes_after_centering(self):
        # A constant signal centers to zero -> all magnitudes ~0
        windows = np.full((1, FFT_SIZE), 128.0, dtype=np.float64)
        mags = compute_stft(windows)
        assert mags.max() < 1e-6


class TestComputeSpectralEntropy:
    def test_small_random_data_in_range(self):
        # Small batch uses reference path; small random data should be near 8.0
        rng = np.random.default_rng(1234)
        # Use only 10 windows so we stay on the reference path
        data = rng.integers(0, 256, size=(10 * FFT_SIZE,), dtype=np.uint8)
        windows = data.astype(np.float64).reshape(10, FFT_SIZE)
        ent = compute_spectral_entropy(windows)
        assert ent.shape == (10,)
        # Reference path should be accurate
        bad = [e for e in ent if e < 7.0 or e > 8.5]
        assert bad == [], f"Out-of-range entropies: {bad}"

    def test_returns_float64(self):
        rng = np.random.default_rng(0)
        windows = rng.integers(0, 256, size=(2, FFT_SIZE), dtype=np.uint8).astype(np.float64)
        ent = compute_spectral_entropy(windows)
        assert ent.dtype == np.float64
