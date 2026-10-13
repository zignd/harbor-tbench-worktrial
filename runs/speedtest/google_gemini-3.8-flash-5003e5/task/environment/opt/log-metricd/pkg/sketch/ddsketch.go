package sketch

import (
	"errors"
	"fmt"
	"math"
	"sort"
)

var (
	ErrInvalidAlpha    = errors.New("alpha must be between 0 and 1")
	ErrInvalidQuantile = errors.New("quantile must be between 0 and 1")
	ErrEmptySketch     = errors.New("cannot query quantile on empty sketch")
	ErrInvalidValue    = errors.New("sketch only accepts positive values > 0")
)

type DDSketch struct {
	alpha   float64
	gamma   float64
	count   int64
	sum     float64
	minVal  float64
	maxVal  float64
	buckets map[int]int64
	minKey  int
	maxKey  int
}

func NewDDSketch(alpha float64) (*DDSketch, error) {
	if alpha <= 0 || alpha >= 1 {
		return nil, ErrInvalidAlpha
	}

	gamma := 1.0 + alpha

	return &DDSketch{
		alpha:   alpha,
		gamma:   gamma,
		buckets: make(map[int]int64),
		minVal:  math.MaxFloat64,
		maxVal:  -math.MaxFloat64,
		minKey:  math.MaxInt32,
		maxKey:  math.MinInt32,
	}, nil
}

func (s *DDSketch) Alpha() float64 {
	return s.alpha
}

func (s *DDSketch) Gamma() float64 {
	return s.gamma
}

func (s *DDSketch) Count() int64 {
	return s.count
}

func (s *DDSketch) Sum() float64 {
	return s.sum
}

func (s *DDSketch) Min() float64 {
	if s.count == 0 {
		return 0
	}
	return s.minVal
}

func (s *DDSketch) Max() float64 {
	if s.count == 0 {
		return 0
	}
	return s.maxVal
}

func (s *DDSketch) BucketCount() int {
	return len(s.buckets)
}

func (s *DDSketch) valToIndex(val float64) int {
	return int(math.Floor(math.Log(val) / math.Log(s.gamma)))
}

func (s *DDSketch) indexToVal(key int) float64 {
	return math.Pow(s.gamma, float64(key))
}

func (s *DDSketch) Add(val float64) error {
	if val <= 0 || math.IsNaN(val) || math.IsInf(val, 0) {
		return ErrInvalidValue
	}

	key := s.valToIndex(val)
	s.buckets[key]++
	s.count++
	s.sum += val

	if val < s.minVal {
		s.minVal = val
	}
	if val > s.maxVal {
		s.maxVal = val
	}
	if key < s.minKey {
		s.minKey = key
	}
	if key > s.maxKey {
		s.maxKey = key
	}
	return nil
}

func (s *DDSketch) AddMany(vals []float64) (int, error) {
	ingested := 0
	for _, v := range vals {
		if err := s.Add(v); err != nil {
			return ingested, err
		}
		ingested++
	}
	return ingested, nil
}

func (s *DDSketch) Quantile(q float64) (float64, error) {
	if q <= 0 || q >= 1 {
		if q == 0 && s.count > 0 {
			return s.minVal, nil
		}
		if q == 1 && s.count > 0 {
			return s.maxVal, nil
		}
		return 0, ErrInvalidQuantile
	}
	if s.count == 0 {
		return 0, ErrEmptySketch
	}

	rank := q * float64(s.count)

	keys := make([]int, 0, len(s.buckets))
	for k := range s.buckets {
		keys = append(keys, k)
	}
	sort.Ints(keys)

	var runningCount int64
	for _, k := range keys {
		runningCount += s.buckets[k]
		if float64(runningCount) >= rank {
			est := s.indexToVal(k)
			if est < s.minVal {
				est = s.minVal
			}
			if est > s.maxVal {
				est = s.maxVal
			}
			return est, nil
		}
	}

	return s.maxVal, nil
}

func (s *DDSketch) Merge(other *DDSketch) error {
	if other == nil || other.count == 0 {
		return nil
	}
	if math.Abs(s.gamma-other.gamma) > 1e-9 {
		return fmt.Errorf("cannot merge sketches with distinct gamma values (%f vs %f)", s.gamma, other.gamma)
	}

	for k, c := range other.buckets {
		s.buckets[k] += c
		if k < s.minKey {
			s.minKey = k
		}
		if k > s.maxKey {
			s.maxKey = k
		}
	}
	s.count += other.count
	s.sum += other.sum
	if other.minVal < s.minVal {
		s.minVal = other.minVal
	}
	if other.maxVal > s.maxVal {
		s.maxVal = other.maxVal
	}
	return nil
}

func (s *DDSketch) Copy() *DDSketch {
	cp := &DDSketch{
		alpha:   s.alpha,
		gamma:   s.gamma,
		count:   s.count,
		sum:     s.sum,
		minVal:  s.minVal,
		maxVal:  s.maxVal,
		minKey:  s.minKey,
		maxKey:  s.maxKey,
		buckets: make(map[int]int64, len(s.buckets)),
	}
	for k, v := range s.buckets {
		cp.buckets[k] = v
	}
	return cp
}
