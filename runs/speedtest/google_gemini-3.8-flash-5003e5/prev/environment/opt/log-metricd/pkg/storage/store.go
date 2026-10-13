package storage

import (
	"errors"
	"fmt"
	"sync"
	"time"

	"log-metricd/pkg/planner"
	"log-metricd/pkg/sketch"
)

var (
	ErrStreamNotFound = errors.New("stream not found in store")
)

type StreamState struct {
	ID             string
	Config         planner.StreamBudgetConfig
	Sketch         *sketch.DDSketch
	TotalSamples   int64
	DroppedSamples int64
	CreatedAt      time.Time
	mu             sync.RWMutex
}

type Store struct {
	mu                sync.Mutex
	planner           *planner.Planner
	streams           map[string]*StreamState
	globalIngestCount int64
	globalQueryCount  int64
}

func NewStore(p *planner.Planner) *Store {
	return &Store{
		planner: p,
		streams: make(map[string]*StreamState),
	}
}

func (s *Store) RegisterStream(req planner.StreamBudgetConfig) (*planner.StreamBudgetConfig, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	cfg, err := s.planner.RegisterStream(req)
	if err != nil {
		return nil, err
	}

	sk, err := sketch.NewDDSketch(cfg.EffectiveAlpha)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize sketch: %w", err)
	}

	state := &StreamState{
		ID:        cfg.StreamID,
		Config:    *cfg,
		Sketch:    sk,
		CreatedAt: time.Now(),
	}
	s.streams[cfg.StreamID] = state
	return cfg, nil
}

func (s *Store) Ingest(streamID string, values []float64) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state, ok := s.streams[streamID]
	if !ok {
		return 0, ErrStreamNotFound
	}

	ingested := 0
	for _, v := range values {
		if err := s.planner.ValidateSample(streamID, v); err != nil {
			state.DroppedSamples++
			continue
		}
		if err := state.Sketch.Add(v); err != nil {
			state.DroppedSamples++
			continue
		}
		ingested++
		state.TotalSamples++
	}
	s.globalIngestCount += int64(ingested)
	return ingested, nil
}

func (s *Store) Query(streamID string, quantiles []float64) (map[string]float64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state, ok := s.streams[streamID]
	if !ok {
		return nil, ErrStreamNotFound
	}

	s.globalQueryCount++
	results := make(map[string]float64, len(quantiles))
	for _, q := range quantiles {
		val, err := state.Sketch.Quantile(q)
		if err != nil {
			return nil, err
		}
		results[fmt.Sprintf("%g", q)] = val
	}
	return results, nil
}

func (s *Store) GetStreamStats(streamID string) (map[string]interface{}, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state, ok := s.streams[streamID]
	if !ok {
		return nil, ErrStreamNotFound
	}

	stats := map[string]interface{}{
		"stream_id":        state.ID,
		"total_samples":    state.TotalSamples,
		"dropped_samples":  state.DroppedSamples,
		"bucket_count":     state.Sketch.BucketCount(),
		"min":              state.Sketch.Min(),
		"max":              state.Sketch.Max(),
		"sum":              state.Sketch.Sum(),
		"allocated_budget": state.Config.AllocatedBuckets,
		"effective_alpha":  state.Config.EffectiveAlpha,
	}
	return stats, nil
}

func (s *Store) GlobalStats() map[string]interface{} {
	s.mu.Lock()
	defer s.mu.Unlock()

	return map[string]interface{}{
		"active_streams": len(s.streams),
		"total_ingests":  s.globalIngestCount,
		"total_queries":  s.globalQueryCount,
		"budget_used":    s.planner.AllocatedTotal(),
		"budget_cap":     s.planner.TotalCapacity(),
	}
}
