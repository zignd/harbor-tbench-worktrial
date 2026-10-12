// stats.rs - Service statistics tracking
use serde::Serialize;
use std::sync::atomic::{AtomicU64, Ordering};

/// Atomic counters for service-level statistics.
#[derive(Debug, Default)]
pub struct ServiceStats {
    encodes: AtomicU64,
    encodes_ok: AtomicU64,
    decodes: AtomicU64,
    decodes_ok: AtomicU64,
    errors: AtomicU64,
}

#[derive(Debug, Serialize)]
pub struct StatsSnapshot {
    pub encodes: u64,
    pub encodes_ok: u64,
    pub decodes: u64,
    pub decodes_ok: u64,
    pub errors: u64,
    pub encode_error_rate: f64,
    pub decode_error_rate: f64,
}

impl ServiceStats {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn inc_encode(&self) {
        self.encodes.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_encode_ok(&self) {
        self.encodes_ok.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_decode(&self) {
        self.decodes.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_decode_ok(&self) {
        self.decodes_ok.fetch_add(1, Ordering::Relaxed);
    }

    pub fn inc_error(&self) {
        self.errors.fetch_add(1, Ordering::Relaxed);
    }

    pub fn snapshot(&self) -> StatsSnapshot {
        let encodes = self.encodes.load(Ordering::Relaxed);
        let encodes_ok = self.encodes_ok.load(Ordering::Relaxed);
        let decodes = self.decodes.load(Ordering::Relaxed);
        let decodes_ok = self.decodes_ok.load(Ordering::Relaxed);
        let errors = self.errors.load(Ordering::Relaxed);

        let encode_error_rate = if encodes > 0 {
            (encodes - encodes_ok) as f64 / encodes as f64
        } else {
            0.0
        };

        let decode_error_rate = if decodes > 0 {
            (decodes - decodes_ok) as f64 / decodes as f64
        } else {
            0.0
        };

        StatsSnapshot {
            encodes,
            encodes_ok,
            decodes,
            decodes_ok,
            errors,
            encode_error_rate,
            decode_error_rate,
        }
    }

    /// Reset all counters to zero.
    pub fn reset(&self) {
        self.encodes.store(0, Ordering::Relaxed);
        self.encodes_ok.store(0, Ordering::Relaxed);
        self.decodes.store(0, Ordering::Relaxed);
        self.decodes_ok.store(0, Ordering::Relaxed);
        self.errors.store(0, Ordering::Relaxed);
    }

    /// Returns total requests processed.
    pub fn total_requests(&self) -> u64 {
        self.encodes.load(Ordering::Relaxed) + self.decodes.load(Ordering::Relaxed)
    }

    /// Returns total successful operations.
    pub fn total_ok(&self) -> u64 {
        self.encodes_ok.load(Ordering::Relaxed) + self.decodes_ok.load(Ordering::Relaxed)
    }

    /// Returns overall error count.
    pub fn total_errors(&self) -> u64 {
        self.errors.load(Ordering::Relaxed)
    }

    /// Returns overall success rate as a float in [0.0, 1.0].
    pub fn success_rate(&self) -> f64 {
        let total = self.total_requests();
        if total == 0 {
            return 1.0;
        }
        self.total_ok() as f64 / total as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stats_initial_zero() {
        let s = ServiceStats::new();
        assert_eq!(s.total_requests(), 0);
        assert_eq!(s.total_errors(), 0);
        assert!((s.success_rate() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_stats_increment() {
        let s = ServiceStats::new();
        s.inc_encode();
        s.inc_encode_ok();
        s.inc_decode();
        s.inc_decode_ok();
        assert_eq!(s.total_requests(), 2);
        assert_eq!(s.total_ok(), 2);
        assert_eq!(s.total_errors(), 0);
    }

    #[test]
    fn test_stats_reset() {
        let s = ServiceStats::new();
        s.inc_encode();
        s.inc_error();
        s.reset();
        assert_eq!(s.total_requests(), 0);
        assert_eq!(s.total_errors(), 0);
    }
}
