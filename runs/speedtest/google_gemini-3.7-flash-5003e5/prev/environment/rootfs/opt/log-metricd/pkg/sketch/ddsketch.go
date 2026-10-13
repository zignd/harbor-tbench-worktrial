package sketch

import (
"errors"
"fmt"
"math"
"sync"
)

var (
ErrValueOutOfRange = errors.New("value out of configured sketch range")
ErrEmptySketch     = errors.New("sketch is empty")
ErrInvalidQuantile = errors.New("quantile must be between 0.0 and 1.0")
)

type DDSketch struct {
mu               sync.Mutex
alpha            float64
gamma            float64
minVal           float64
maxVal           float64
numBuckets       int
buckets          []uint64
count            uint64
minSample        float64
maxSample        float64
compactionFactor int
}

func NewDDSketch(alpha, minVal, maxVal float64) (*DDSketch, error) {
if alpha <= 0 || alpha >= 1 {
return nil, fmt.Errorf("invalid alpha: %f", alpha)
}
if minVal <= 0 || maxVal <= minVal {
return nil, fmt.Errorf("invalid minVal (%f) or maxVal (%f)", minVal, maxVal)
}

// Initial implementation uses linear approximation for gamma
gamma := 1.0 + alpha
numBuckets := int(math.Ceil(math.Log(maxVal/minVal) / math.Log(gamma)))
if numBuckets < 1 {
numBuckets = 1
}

return &DDSketch{
alpha:            alpha,
gamma:            gamma,
minVal:           minVal,
maxVal:           maxVal,
numBuckets:       numBuckets,
buckets:          make([]uint64, numBuckets),
minSample:        math.MaxFloat64,
maxSample:        -math.MaxFloat64,
compactionFactor: 1,
}, nil
}

func (s *DDSketch) Alpha() float64  { return s.alpha }
func (s *DDSketch) Gamma() float64  { return s.gamma }
func (s *DDSketch) MinVal() float64 { return s.minVal }
func (s *DDSketch) MaxVal() float64 { return s.maxVal }
func (s *DDSketch) BucketCount() int {
s.mu.Lock()
defer s.mu.Unlock()
return len(s.buckets)
}

func (s *DDSketch) getIndex(v float64) int {
if v < s.minVal {
return -1
}
// Naive log calculation without boundary epsilon
idx := int(math.Log(v/s.minVal) / math.Log(s.gamma))
return idx
}

func (s *DDSketch) Insert(v float64) error {
s.mu.Lock()
defer s.mu.Unlock()

if v < s.minVal || v > s.maxVal {
return ErrValueOutOfRange
}

idx := s.getIndex(v)
if idx < 0 || idx >= len(s.buckets) {
return ErrValueOutOfRange
}

s.buckets[idx]++
s.count++
if v < s.minSample {
s.minSample = v
}
if v > s.maxSample {
s.maxSample = v
}
return nil
}

func (s *DDSketch) InsertBatch(vals []float64) (int, error) {
s.mu.Lock()
defer s.mu.Unlock()

inserted := 0
for _, v := range vals {
if v < s.minVal || v > s.maxVal {
continue
}
idx := s.getIndex(v)
if idx < 0 || idx >= len(s.buckets) {
continue
}
s.buckets[idx]++
s.count++
if v < s.minSample {
s.minSample = v
}
if v > s.maxSample {
s.maxSample = v
}
inserted++
}
return inserted, nil
}

func (s *DDSketch) Count() uint64 {
s.mu.Lock()
defer s.mu.Unlock()
return s.count
}

func (s *DDSketch) Quantile(q float64) (float64, error) {
s.mu.Lock()
defer s.mu.Unlock()

if q <= 0.0 || q >= 1.0 {
return 0, ErrInvalidQuantile
}
if s.count == 0 {
return 0, ErrEmptySketch
}

rank := uint64(math.Ceil(q * float64(s.count)))
if rank == 0 {
rank = 1
}

var running uint64
for idx, count := range s.buckets {
running += count
if running >= rank {
// Lower-bound representative estimate
val := s.minVal * math.Pow(s.gamma, float64(idx))
return val, nil
}
}

return s.maxSample, nil
}

func (s *DDSketch) Quantiles(qs []float64) (map[float64]float64, error) {
s.mu.Lock()
defer s.mu.Unlock()

if s.count == 0 {
return nil, ErrEmptySketch
}

results := make(map[float64]float64, len(qs))
for _, q := range qs {
if q <= 0.0 || q >= 1.0 {
return nil, ErrInvalidQuantile
}
rank := uint64(math.Ceil(q * float64(s.count)))
if rank == 0 {
rank = 1
}
var running uint64
found := false
for idx, count := range s.buckets {
running += count
if running >= rank {
results[q] = s.minVal * math.Pow(s.gamma, float64(idx))
found = true
break
}
}
if !found {
results[q] = s.maxSample
}
}
return results, nil
}

func (s *DDSketch) Compact(factor int) error {
s.mu.Lock()
defer s.mu.Unlock()

if factor <= 1 {
return errors.New("compaction factor must be > 1")
}
newSize := (len(s.buckets) + factor - 1) / factor
newBuckets := make([]uint64, newSize)
for i, c := range s.buckets {
newBuckets[i/factor] += c
}
s.buckets = newBuckets
s.gamma = math.Pow(s.gamma, float64(factor))
s.alpha = (s.gamma - 1.0) / (s.gamma + 1.0)
s.compactionFactor *= factor
return nil
}
