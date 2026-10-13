package api

import (
	"encoding/json"
	"log-metricd/pkg/planner"
	"log-metricd/pkg/storage"
	"net/http"
)

type Server struct {
	Store  *storage.Store
	Budget int
	Alloc  []planner.Allocation
}

func (s *Server) Handler() http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("/healthz", s.health)
	m.HandleFunc("/v1/ingest", s.ingest)
	m.HandleFunc("/v1/query", s.query)
	m.HandleFunc("/v1/streams/register", s.register)
	return m
}
func dec(r *http.Request, v any) error { return json.NewDecoder(r.Body).Decode(v) }
func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok"}`))
}

type event struct {
	Stream   string  `json:"stream"`
	StreamID string  `json:"stream_id"`
	Value    float64 `json:"value"`
	Latency  float64 `json:"latency"`
}

func (s *Server) ingest(w http.ResponseWriter, r *http.Request) {
	var raw json.RawMessage
	if dec(r, &raw) != nil {
		http.Error(w, "bad json", 400)
		return
	}
	var e event
	if json.Unmarshal(raw, &e) == nil && (e.Stream != "" || e.StreamID != "") {
		n := e.Stream
		if n == "" {
			n = e.StreamID
		}
		v := e.Value
		if v == 0 {
			v = e.Latency
		}
		s.Store.Add(n, v)
	} else {
		var x struct {
			Events []event `json:"events"`
		}
		if json.Unmarshal(raw, &x) != nil {
			http.Error(w, "bad json", 400)
			return
		}
		for _, e := range x.Events {
			n := e.Stream
			if n == "" {
				n = e.StreamID
			}
			v := e.Value
			if v == 0 {
				v = e.Latency
			}
			s.Store.Add(n, v)
		}
	}
	json.NewEncoder(w).Encode(map[string]any{"accepted": true})
}
func (s *Server) query(w http.ResponseWriter, r *http.Request) {
	var x struct {
		Stream   string  `json:"stream"`
		StreamID string  `json:"stream_id"`
		Q        float64 `json:"q"`
		Quantile float64 `json:"quantile"`
	}
	if dec(r, &x) != nil {
		http.Error(w, "bad json", 400)
		return
	}
	n := x.Stream
	if n == "" {
		n = x.StreamID
	}
	q := x.Q
	if q == 0 {
		q = x.Quantile
	}
	v := s.Store.Query(n, q)
	json.NewEncoder(w).Encode(map[string]any{"quantile": q, "value": v, "estimate": v})
}
func (s *Server) register(w http.ResponseWriter, r *http.Request) {
	var x struct {
		Name     string  `json:"name"`
		Stream   string  `json:"stream"`
		StreamID string  `json:"stream_id"`
		XMin     float64 `json:"x_min"`
		XMax     float64 `json:"x_max"`
		Alpha    float64 `json:"alpha"`
	}
	if dec(r, &x) != nil {
		http.Error(w, "bad json", 400)
		return
	}
	n := x.Name
	if n == "" {
		n = x.Stream
	}
	if n == "" {
		n = x.StreamID
	}
	s.Store.Ensure(n)
	s.Alloc = append(s.Alloc, planner.Allocation{Name: n, Buckets: 1, XMin: x.XMin, XMax: x.XMax})
	json.NewEncoder(w).Encode(map[string]any{"accepted": true, "name": n, "buckets": 1, "allocated_buckets": 1, "total_buckets": len(s.Alloc)})
}
