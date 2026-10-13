"""
Logbin Engine Wrapper

This module provides a Python interface to logbin_engine.so, a compiled
shared library for fast columnar windowed aggregations over time-series data.

Public API
----------
load_series(service, metric, timestamps, values) -> handle
    Load a time-series into the engine. Returns an opaque integer handle.
    timestamps: list or array of float seconds since epoch
    values: list or array of float metric values

compute_window(handle, window_secs, agg_type) -> list of (bucket_start, value)
    Compute windowed aggregations over a loaded series.
    window_secs: bucket size in seconds (must be positive)
    agg_type: one of 'sum', 'mean', 'p50', 'p95', 'p99'
    Returns a list of (bucket_start_ts, aggregated_value) tuples.

    Windowing semantics: buckets are aligned to the Unix epoch. Each bucket
    covers a window of window_secs seconds, inclusive on both ends. Bucket
    timestamps represent the START of each window interval. Data points are
    assigned to the bucket whose interval contains the timestamp.

release_handle(handle)
    Free engine resources for a previously loaded series.

Notes
-----
- The engine requires numpy arrays internally; plain lists are converted.
- Aggregation types map to: sum=0, mean=1, p50=2, p95=3, p99=4
- Bucket timestamps in returned tuples are float seconds since epoch, aligned
  to multiples of window_secs.
- NaN values in the output indicate missing or invalid data for that bucket.
  This can happen when underlying data is unavailable.
- Thread safety: each handle is independent; concurrent calls with different
  handles are safe. Do not share handles across threads.
"""

import ctypes
import os
import threading
import numpy as np

_lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logbin_engine.so')
_lib = None
_lib_lock = threading.Lock()

AGG_MAP = {
    'sum': 0,
    'mean': 1,
    'p50': 2,
    'p95': 3,
    'p99': 4,
}

MAX_BUCKETS = 1_000_000


def _get_lib():
    global _lib
    if _lib is None:
        with _lib_lock:
            if _lib is None:
                lib = ctypes.CDLL(_lib_path)

                lib.load_series.restype = ctypes.c_int64
                lib.load_series.argtypes = [
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.c_int64,
                ]

                lib.compute_window.restype = ctypes.c_int64
                lib.compute_window.argtypes = [
                    ctypes.c_int64,
                    ctypes.c_double,
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.c_int64,
                ]

                lib.release_handle.restype = None
                lib.release_handle.argtypes = [ctypes.c_int64]

                _lib = lib
    return _lib


def load_series(service, metric, timestamps, values):
    """
    Load a time-series into the engine.

    Parameters
    ----------
    service : str
        Service name (used for logging/debugging only; not passed to engine).
    metric : str
        Metric name (used for logging/debugging only; not passed to engine).
    timestamps : array-like of float
        Unix timestamps in seconds.
    values : array-like of float
        Metric values corresponding to each timestamp.

    Returns
    -------
    int
        Opaque handle to the loaded series.

    Raises
    ------
    ValueError
        If timestamps and values have different lengths.
    RuntimeError
        If the engine fails to load the series.
    """
    ts_arr = np.asarray(timestamps, dtype=np.float64)
    val_arr = np.asarray(values, dtype=np.float64)
    if len(ts_arr) != len(val_arr):
        raise ValueError(f"timestamps and values must have the same length, got {len(ts_arr)} vs {len(val_arr)}")
    count = len(ts_arr)
    lib = _get_lib()
    if count == 0:
        ts_ptr = (ctypes.c_double * 0)()
        val_ptr = (ctypes.c_double * 0)()
    else:
        ts_ptr = ts_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        val_ptr = val_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
    handle = lib.load_series(ts_ptr, val_ptr, ctypes.c_int64(count))
    if handle < 0:
        raise RuntimeError(f"Engine failed to load series for {service}/{metric}")
    return handle


def compute_window(handle, window_secs, agg_type):
    """
    Compute windowed aggregations.

    Parameters
    ----------
    handle : int
        Handle returned by load_series.
    window_secs : float
        Bucket size in seconds.
    agg_type : str
        Aggregation type: 'sum', 'mean', 'p50', 'p95', 'p99'.

    Returns
    -------
    list of (float, float)
        List of (bucket_start_timestamp, aggregated_value) tuples.
        Bucket timestamps are aligned to multiples of window_secs from epoch.
        Windows are inclusive on both ends — data at exactly the bucket start
        timestamp is included in that bucket.
        Values may be NaN for buckets with insufficient data.

    Raises
    ------
    ValueError
        If agg_type is not recognized.
    RuntimeError
        If the engine returns an error.
    """
    if agg_type not in AGG_MAP:
        raise ValueError(f"Unknown agg_type '{agg_type}'. Must be one of {list(AGG_MAP.keys())}")
    agg_int = AGG_MAP[agg_type]
    lib = _get_lib()
    out_starts = (ctypes.c_double * MAX_BUCKETS)()
    out_values = (ctypes.c_double * MAX_BUCKETS)()
    n = lib.compute_window(
        ctypes.c_int64(handle),
        ctypes.c_double(window_secs),
        ctypes.c_int(agg_int),
        out_starts,
        out_values,
        ctypes.c_int64(MAX_BUCKETS),
    )
    if n < 0:
        raise RuntimeError(f"Engine compute_window failed (handle={handle})")
    results = []
    for i in range(n):
        results.append((float(out_starts[i]), float(out_values[i])))
    return results


def release_handle(handle):
    """
    Release engine resources for a loaded series.

    Parameters
    ----------
    handle : int
        Handle returned by load_series.
    """
    lib = _get_lib()
    lib.release_handle(ctypes.c_int64(handle))
