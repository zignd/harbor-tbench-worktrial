//! Statistical result types and display utilities.

use std::fmt;

/// A single row written to the results database.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResultRow {
    pub batch_id: i64,
    pub sample_count: i64,
    pub fixed_mean: i64,
    pub fixed_variance: i64,
    pub checksum: i64,
}

impl ResultRow {
    /// Create a zeroed row for a given batch.
    pub fn zero(batch_id: i64) -> Self {
        ResultRow {
            batch_id,
            sample_count: 0,
            fixed_mean: 0,
            fixed_variance: 0,
            checksum: 0,
        }
    }

    /// Return the fixed_mean as a floating-point value for display.
    pub fn mean_f64(&self) -> f64 {
        self.fixed_mean as f64 / 65536.0
    }

    /// Return the fixed_variance as a floating-point value for display.
    pub fn variance_f64(&self) -> f64 {
        self.fixed_variance as f64 / 65536.0
    }

    /// Return the standard deviation as a floating-point value for display.
    pub fn stddev_f64(&self) -> f64 {
        self.variance_f64().sqrt()
    }
}

impl fmt::Display for ResultRow {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "batch={} n={} mean={:.6} var={:.6} crc={:#010x}",
            self.batch_id,
            self.sample_count,
            self.mean_f64(),
            self.variance_f64(),
            self.checksum as u64,
        )
    }
}

/// Running summary statistics (floating-point, for diagnostics only).
#[derive(Debug, Clone, Default)]
pub struct SummaryStats {
    pub count: u64,
    pub sum: f64,
    pub sum_sq: f64,
    pub min: f64,
    pub max: f64,
}

impl SummaryStats {
    pub fn new() -> Self {
        SummaryStats {
            count: 0,
            sum: 0.0,
            sum_sq: 0.0,
            min: f64::INFINITY,
            max: f64::NEG_INFINITY,
        }
    }

    pub fn update(&mut self, x: f64) {
        self.count += 1;
        self.sum += x;
        self.sum_sq += x * x;
        if x < self.min { self.min = x; }
        if x > self.max { self.max = x; }
    }

    pub fn mean(&self) -> f64 {
        if self.count == 0 { return 0.0; }
        self.sum / self.count as f64
    }

    pub fn variance(&self) -> f64 {
        if self.count == 0 { return 0.0; }
        let n = self.count as f64;
        self.sum_sq / n - (self.sum / n).powi(2)
    }

    pub fn stddev(&self) -> f64 {
        self.variance().sqrt()
    }

    pub fn range(&self) -> f64 {
        if self.count == 0 { return 0.0; }
        self.max - self.min
    }
}

impl fmt::Display for SummaryStats {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "n={} mean={:.4} var={:.4} range=[{:.0}, {:.0}]",
            self.count, self.mean(), self.variance(), self.min, self.max
        )
    }
}

/// Q16.16 fixed-point helpers.
pub mod fixedpoint {
    /// The number of fractional bits.
    pub const FRAC_BITS: i64 = 16;
    /// The scale factor: 2^16 = 65536.
    pub const SCALE: i64 = 1i64 << FRAC_BITS;

    /// Convert an integer to Q16.16.
    pub fn from_int(x: i64) -> i64 {
        x * SCALE
    }

    /// Convert Q16.16 to f64.
    pub fn to_f64(q: i64) -> f64 {
        q as f64 / SCALE as f64
    }

    /// Convert f64 to Q16.16 (truncated).
    pub fn from_f64_trunc(x: f64) -> i64 {
        (x * SCALE as f64) as i64
    }

    /// Convert f64 to Q16.16 (round-half-up).
    pub fn from_f64_round(x: f64) -> i64 {
        (x * SCALE as f64 + 0.5).floor() as i64
    }

    /// Multiply two Q16.16 values, returning Q16.16.
    pub fn mul(a: i64, b: i64) -> i64 {
        ((a as i128 * b as i128) >> FRAC_BITS) as i64
    }

    /// Integer part of a Q16.16 value.
    pub fn integer_part(q: i64) -> i64 {
        q >> FRAC_BITS
    }

    /// Fractional part of a Q16.16 value (as a Q16.16 value in [0, 1)).
    pub fn frac_part(q: i64) -> i64 {
        q & (SCALE - 1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::fixedpoint::*;

    #[test]
    fn result_row_display() {
        let row = ResultRow {
            batch_id: 7,
            sample_count: 1000,
            fixed_mean: 65536,   // 1.0 in Q16.16
            fixed_variance: 131072, // 2.0 in Q16.16
            checksum: 0xCAFEBABE_u32 as i64,
        };
        let s = format!("{}", row);
        assert!(s.contains("batch=7"));
        assert!(s.contains("n=1000"));
    }

    #[test]
    fn summary_stats_basic() {
        let mut s = SummaryStats::new();
        for i in 1..=4 {
            s.update(i as f64);
        }
        assert_eq!(s.count, 4);
        assert!((s.mean() - 2.5).abs() < 1e-9);
        // population variance of [1,2,3,4] = 1.25
        assert!((s.variance() - 1.25).abs() < 1e-9);
    }

    #[test]
    fn fixedpoint_conversions() {
        assert_eq!(from_int(1), 65536);
        assert_eq!(from_int(0), 0);
        assert!((to_f64(65536) - 1.0).abs() < 1e-9);
        assert_eq!(from_f64_trunc(1.5), 98304);
        assert_eq!(from_f64_round(1.5), 98305);
    }

    #[test]
    fn fixedpoint_mul() {
        // 2.0 * 3.0 = 6.0 in Q16.16
        let a = from_int(2);
        let b = from_int(3);
        assert_eq!(mul(a, b), from_int(6));
    }
}
