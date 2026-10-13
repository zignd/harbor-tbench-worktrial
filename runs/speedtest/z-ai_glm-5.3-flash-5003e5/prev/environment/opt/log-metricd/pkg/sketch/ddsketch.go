// Package sketch implements the bounded relative-error logarithmic histogram
// used by the metric service.
package sketch

import (
    "fmt"
    "math"
)

// Config describes one stream's range and the allocation produced by the
// planner. BucketRatio is the ratio between adjacent retained bucket bounds.
type Config struct {
    MinValue    float64
    MaxValue    float64
    Alpha       float64
    BucketRatio float64
    Multiplier  int
}

// Sketch stores counts in logarithmic buckets. A separate store lock normally
// serializes calls to these methods.
type Sketch struct {
    cfg       Config
    lowers    []float64
    uppers    []float64
    reps      []float64
    counts    []uint64
    count     uint64
    underflow uint64
    overflow  uint64
}

// GammaForError returns the base needed by an interval whose endpoints are
// within alpha of its representative.
func GammaForError(alpha float64) (float64, error) {
    if !(alpha > 0) || !(alpha < 1) || math.IsNaN(alpha) {
        return 0, fmt.Errorf("alpha must be in (0, 1)")
    }
    safe := alpha * (1 - math.Pow(2, -40))
    return (1 + safe) / (1 - safe), nil
}

func New(cfg Config) (*Sketch, error) {
    if math.IsNaN(cfg.MinValue) || math.IsInf(cfg.MinValue, 0) || cfg.MinValue <= 0 {
        return nil, fmt.Errorf("minimum value must be finite and positive")
    }
    if math.IsNaN(cfg.MaxValue) || math.IsInf(cfg.MaxValue, 0) || cfg.MaxValue <= cfg.MinValue {
        return nil, fmt.Errorf("maximum value must be finite and greater than the minimum")
    }
    if cfg.BucketRatio <= 1 || math.IsNaN(cfg.BucketRatio) || math.IsInf(cfg.BucketRatio, 1) {
        return nil, fmt.Errorf("bucket ratio must be greater than one")
    }
    if cfg.Multiplier <= 0 {
        return nil, fmt.Errorf("bucket multiplier must be positive")
    }
    if cfg.Alpha <= 0 || cfg.Alpha >= 1 {
        return nil, fmt.Errorf("alpha must be in (0, 1)")
    }
    if cfg.Multiplier > 4 {
        return nil, fmt.Errorf("bucket multiplier is limited to four")
    }

    s := &Sketch{cfg: cfg}
    n := 2048
    if cfg.MaxValue/cfg.MinValue < cfg.BucketRatio {
        n = 1
    } else {
        n = int(math.Ceil(math.Log(cfg.MaxValue/cfg.MinValue) / math.Log(cfg.BucketRatio)))
        if n < 1 {
            n = 1
        }
    }
    s.lowers = make([]float64, n)
    s.uppers = make([]float64, n)
    s.reps = make([]float64, n)
    s.counts = make([]uint64, n)

    lower := cfg.MinValue
    for i := 0; i < n; i++ {
        s.lowers[i] = lower
        upper := lower * cfg.BucketRatio
        if i == n-1 || upper > cfg.MaxValue {
            upper = cfg.MaxValue
        }
        s.uppers[i] = upper
        s.reps[i] = lower
        if upper <= lower {
            return nil, fmt.Errorf("empty bucket at index %d", i)
        }
        lower = upper
    }
    return s, nil
}

func (s *Sketch) bucket(v float64) int {
    if v < s.cfg.MinValue {
        return -1
    }
    if v >= s.cfg.MaxValue {
        return len(s.counts) - 1
    }
    low, high := 0, len(s.counts)-1
    for low < high {
        mid := int(uint(low+high) >> 1)
        if v < s.uppers[mid] {
            high = mid
        } else {
            low = mid + 1
        }
    }
    return low
}

func (s *Sketch) Ingest(v float64) error {
    if math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
        return fmt.Errorf("latency must be finite and positive")
    }
    switch {
    case v < s.cfg.MinValue:
        s.underflow++
    case v > s.cfg.MaxValue:
        s.overflow++
    default:
        index := s.bucket(v)
        if index < 0 || index >= len(s.counts) {
            return fmt.Errorf("latency %v outside allocated buckets", v)
        }
        s.counts[index]++
        s.count++
    }
    return nil
}

func (s *Sketch) Count() uint64 { return s.count }

func (s *Sketch) Underflow() uint64 { return s.underflow }

func (s *Sketch) Overflow() uint64 { return s.overflow }

func (s *Sketch) Quantile(q float64) (float64, error) {
    if !(q > 0) || !(q < 1) || math.IsNaN(q) {
        return 0, fmt.Errorf("quantile must be strictly between zero and one")
    }
    if s.count == 0 {
        return 0, nil
    }
    rank := int(math.Ceil(q * float64(s.count)))
    if rank < 1 {
        rank = 1
    }
    if rank > int(s.count) {
        rank = int(s.count)
    }
    seen := uint64(0)
    for i, n := range s.counts {
        seen += n
        if seen >= uint64(rank) {
            return s.reps[i], nil
        }
    }
    return s.reps[len(s.reps)-1], nil
}

func (s *Sketch) ImplementedError() float64 {
    ratio := s.cfg.BucketRatio
    if ratio <= 1 {
        return 0
    }
    return (ratio - 1) / (ratio + 1)
}
