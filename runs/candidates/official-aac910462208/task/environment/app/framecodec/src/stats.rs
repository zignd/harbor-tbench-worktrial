use std::sync::atomic::{AtomicU64, Ordering};
use serde_json::json;

/// Tracks operational statistics for the codec service.
/// All fields use atomic counters for thread-safe access without locks.
pub struct ServiceStats {
    decode_attempts: AtomicU64,
    decode_successes: AtomicU64,
    decode_failures: AtomicU64,
    encode_attempts: AtomicU64,
    encode_successes: AtomicU64,
    encode_failures: AtomicU64,
    bytes_decoded: AtomicU64,
    bytes_encoded: AtomicU64,
}

impl ServiceStats {
    pub fn new() -> Self {
        ServiceStats {
            decode_attempts: AtomicU64::new(0),
            decode_successes: AtomicU64::new(0),
            decode_failures: AtomicU64::new(0),
            encode_attempts: AtomicU64::new(0),
            encode_successes: AtomicU64::new(0),
            encode_failures: AtomicU64::new(0),
            bytes_decoded: AtomicU64::new(0),
            bytes_encoded: AtomicU64::new(0),
        }
    }

    pub fn record_decode_attempt(&self) {
        self.decode_attempts.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_decode_success(&self) {
        self.decode_successes.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_decode_failure(&self) {
        self.decode_failures.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_encode_attempt(&self) {
        self.encode_attempts.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_encode_success(&self) {
        self.encode_successes.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_encode_failure(&self) {
        self.encode_failures.fetch_add(1, Ordering::Relaxed);
    }

    pub fn add_bytes_decoded(&self, n: u64) {
        self.bytes_decoded.fetch_add(n, Ordering::Relaxed);
    }

    pub fn add_bytes_encoded(&self, n: u64) {
        self.bytes_encoded.fetch_add(n, Ordering::Relaxed);
    }

    pub fn decode_attempts(&self) -> u64 {
        self.decode_attempts.load(Ordering::Relaxed)
    }

    pub fn decode_successes(&self) -> u64 {
        self.decode_successes.load(Ordering::Relaxed)
    }

    pub fn decode_failures(&self) -> u64 {
        self.decode_failures.load(Ordering::Relaxed)
    }

    pub fn encode_attempts(&self) -> u64 {
        self.encode_attempts.load(Ordering::Relaxed)
    }

    pub fn encode_successes(&self) -> u64 {
        self.encode_successes.load(Ordering::Relaxed)
    }

    pub fn encode_failures(&self) -> u64 {
        self.encode_failures.load(Ordering::Relaxed)
    }

    pub fn bytes_decoded(&self) -> u64 {
        self.bytes_decoded.load(Ordering::Relaxed)
    }

    pub fn bytes_encoded(&self) -> u64 {
        self.bytes_encoded.load(Ordering::Relaxed)
    }

    pub fn success_rate_decode(&self) -> f64 {
        let attempts = self.decode_attempts();
        if attempts == 0 {
            return 1.0;
        }
        self.decode_successes() as f64 / attempts as f64
    }

    pub fn success_rate_encode(&self) -> f64 {
        let attempts = self.encode_attempts();
        if attempts == 0 {
            return 1.0;
        }
        self.encode_successes() as f64 / attempts as f64
    }

    pub fn as_json(&self) -> serde_json::Value {
        json!({
            "decode": {
                "attempts": self.decode_attempts(),
                "successes": self.decode_successes(),
                "failures": self.decode_failures(),
                "bytes": self.bytes_decoded(),
                "success_rate": self.success_rate_decode(),
            },
            "encode": {
                "attempts": self.encode_attempts(),
                "successes": self.encode_successes(),
                "failures": self.encode_failures(),
                "bytes": self.bytes_encoded(),
                "success_rate": self.success_rate_encode(),
            }
        })
    }

    pub fn reset(&self) {
        self.decode_attempts.store(0, Ordering::Relaxed);
        self.decode_successes.store(0, Ordering::Relaxed);
        self.decode_failures.store(0, Ordering::Relaxed);
        self.encode_attempts.store(0, Ordering::Relaxed);
        self.encode_successes.store(0, Ordering::Relaxed);
        self.encode_failures.store(0, Ordering::Relaxed);
        self.bytes_decoded.store(0, Ordering::Relaxed);
        self.bytes_encoded.store(0, Ordering::Relaxed);
    }
}

impl Default for ServiceStats {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stats_initial_state() {
        let stats = ServiceStats::new();
        assert_eq!(stats.decode_attempts(), 0);
        assert_eq!(stats.encode_attempts(), 0);
    }

    #[test]
    fn test_stats_record_decode() {
        let stats = ServiceStats::new();
        stats.record_decode_attempt();
        stats.record_decode_success();
        assert_eq!(stats.decode_attempts(), 1);
        assert_eq!(stats.decode_successes(), 1);
    }

    #[test]
    fn test_stats_success_rate() {
        let stats = ServiceStats::new();
        stats.record_decode_attempt();
        stats.record_decode_success();
        stats.record_decode_attempt();
        stats.record_decode_failure();
        assert!((stats.success_rate_decode() - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_stats_reset() {
        let stats = ServiceStats::new();
        stats.record_decode_attempt();
        stats.record_encode_attempt();
        stats.reset();
        assert_eq!(stats.decode_attempts(), 0);
        assert_eq!(stats.encode_attempts(), 0);
    }

    #[test]
    fn test_as_json() {
        let stats = ServiceStats::new();
        stats.record_encode_attempt();
        stats.record_encode_success();
        let j = stats.as_json();
        assert_eq!(j["encode"]["attempts"], 1);
        assert_eq!(j["encode"]["successes"], 1);
    }
}
