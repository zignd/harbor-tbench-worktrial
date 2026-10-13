package storage

import (
	"log-metricd/pkg/sketch"
	"sync"
)

type Stream struct {
	Mu     sync.RWMutex
	Sketch sketch.Sketch
}
type Store struct {
	Mu      sync.RWMutex
	Streams map[string]*Stream
}

func New() *Store                     { return &Store{Streams: map[string]*Stream{}} }
func (s *Store) Get(n string) *Stream { s.Mu.RLock(); x := s.Streams[n]; s.Mu.RUnlock(); return x }
func (s *Store) Ensure(n string) *Stream {
	s.Mu.Lock()
	x := s.Streams[n]
	if x == nil {
		x = &Stream{}
		s.Streams[n] = x
	}
	s.Mu.Unlock()
	return x
}
func (s *Store) Add(n string, v float64) {
	x := s.Ensure(n)
	x.Mu.Lock()
	x.Sketch.Add(v)
	x.Mu.Unlock()
}
func (s *Store) Query(n string, q float64) float64 {
	x := s.Get(n)
	if x == nil {
		return 0
	}
	x.Mu.RLock()
	defer x.Mu.RUnlock()
	return x.Sketch.Quantile(q)
}
