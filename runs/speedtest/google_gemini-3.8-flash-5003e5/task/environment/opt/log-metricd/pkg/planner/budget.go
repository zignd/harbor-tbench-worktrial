package planner

import (
	"errors"
	"fmt"
	"math"
	"sync"
)

var (
	ErrStreamAlreadyExists = errors.New("stream already registered")
	ErrStreamNotFound      = errors.New("stream not found")
	ErrBudgetExceeded      = errors.New("global bucket budget capacity exceeded")
	ErrInvalidConfig       = errors.New("invalid stream configuration")
	ErrValueOutOfRange     = errors.New("value out of registered range")
)

type StreamBudgetConfig struct {
	StreamID         string  `json:"stream_id"`
	XMin             float64 `json:"x_min"`
	XMax             float64 `json:"x_max"`
	Alpha            float64 `json:"alpha"`
	MaxAlpha         float64 `json:"max_alpha"`
	Priority         int     `json:"priority"`
	AllocatedBuckets int     `json:"allocated_buckets"`
	EffectiveAlpha   float64 `json:"effective_alpha"`
	EffectiveXMax    float64 `json:"effective_x_max"`
	CompactionFactor int     `json:"compaction_factor"`
}

type Planner struct {
	mu            sync.RWMutex
	totalCapacity int
	allocated     int
	streams       map[string]*StreamBudgetConfig
}

func NewPlanner(totalCapacity int) *Planner {
	if totalCapacity <= 0 {
		totalCapacity = 2048
	}
	return &Planner{
		totalCapacity: totalCapacity,
		streams:       make(map[string]*StreamBudgetConfig),
	}
}

func (p *Planner) TotalCapacity() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.totalCapacity
}

func (p *Planner) AllocatedTotal() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.allocated
}

func (p *Planner) GetStream(streamID string) (*StreamBudgetConfig, bool) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	cfg, ok := p.streams[streamID]
	if !ok {
		return nil, false
	}
	cp := *cfg
	return &cp, true
}

func (p *Planner) ListStreams() []*StreamBudgetConfig {
	p.mu.RLock()
	defer p.mu.RUnlock()
	list := make([]*StreamBudgetConfig, 0, len(p.streams))
	for _, s := range p.streams {
		cp := *s
		list = append(list, &cp)
	}
	return list
}

func calcBaseGamma(alpha float64) float64 {
	return (1.0 + alpha) / (1.0 - alpha)
}

func calcBucketsNeeded(xMin, xMax, alpha float64) int {
	gamma := calcBaseGamma(alpha)
	if gamma <= 1.0 {
		gamma = 1.0001
	}
	kMin := math.Floor(math.Log(xMin) / math.Log(gamma))
	kMax := math.Ceil(math.Log(xMax) / math.Log(gamma))
	needed := int(kMax - kMin + 1)
	if needed < 1 {
		needed = 1
	}
	return needed
}

func (p *Planner) RegisterStream(req StreamBudgetConfig) (*StreamBudgetConfig, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if req.StreamID == "" || req.XMin <= 0 || req.XMax <= req.XMin || req.Alpha <= 0 || req.Alpha >= 1 {
		return nil, ErrInvalidConfig
	}
	if req.MaxAlpha < req.Alpha {
		req.MaxAlpha = req.Alpha
	}
	if req.Priority <= 0 {
		req.Priority = 1
	}

	if _, exists := p.streams[req.StreamID]; exists {
		return nil, ErrStreamAlreadyExists
	}

	needed := calcBucketsNeeded(req.XMin, req.XMax, req.Alpha)

	cfg := &StreamBudgetConfig{
		StreamID:         req.StreamID,
		XMin:             req.XMin,
		XMax:             req.XMax,
		Alpha:            req.Alpha,
		MaxAlpha:         req.MaxAlpha,
		Priority:         req.Priority,
		AllocatedBuckets: needed,
		EffectiveAlpha:   req.Alpha,
		EffectiveXMax:    req.XMax,
		CompactionFactor: 1,
	}

	newTotal := p.allocated + needed
	if newTotal > p.totalCapacity {
		scale := float64(p.totalCapacity-p.allocated) / float64(needed)
		if scale <= 0 {
			return nil, ErrBudgetExceeded
		}
		cfg.AllocatedBuckets = int(float64(needed) * scale)
		if cfg.AllocatedBuckets < 1 {
			cfg.AllocatedBuckets = 1
		}
		gamma := calcBaseGamma(req.Alpha)
		cfg.EffectiveXMax = req.XMin * math.Pow(gamma, float64(cfg.AllocatedBuckets))
		p.allocated += cfg.AllocatedBuckets
	} else {
		p.allocated = newTotal
	}

	p.streams[req.StreamID] = cfg
	cp := *cfg
	return &cp, nil
}

func (p *Planner) ValidateSample(streamID string, val float64) error {
	p.mu.RLock()
	cfg, ok := p.streams[streamID]
	p.mu.RUnlock()

	if !ok {
		return ErrStreamNotFound
	}
	if val < cfg.XMin || val > cfg.EffectiveXMax {
		return fmt.Errorf("%w: val %f not in [%f, %f]", ErrValueOutOfRange, val, cfg.XMin, cfg.EffectiveXMax)
	}
	return nil
}
