package api

import (
	"encoding/json"
	"net/http"
	"strings"

	"log-metricd/pkg/planner"
	"log-metricd/pkg/storage"
)

type Server struct {
	store *storage.Store
	mux   *http.ServeMux
}

func NewServer(store *storage.Store) *Server {
	s := &Server{
		store: store,
		mux:   http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) routes() {
	s.mux.HandleFunc("/healthz", s.handleHealthz)
	s.mux.HandleFunc("/v1/streams/register", s.handleRegisterStream)
	s.mux.HandleFunc("/v1/ingest", s.handleIngest)
	s.mux.HandleFunc("/v1/query", s.handleQuery)
	s.mux.HandleFunc("/v1/stats", s.handleStats)
	s.mux.HandleFunc("/v1/streams/", s.handleStreamDetail)
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func (s *Server) handleHealthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

type RegisterRequest struct {
	StreamID string  `json:"stream_id"`
	XMin     float64 `json:"x_min"`
	XMax     float64 `json:"x_max"`
	Alpha    float64 `json:"alpha"`
	MaxAlpha float64 `json:"max_alpha"`
	Priority int     `json:"priority"`
}

func (s *Server) handleRegisterStream(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}

	cfg := planner.StreamBudgetConfig{
		StreamID: req.StreamID,
		XMin:     req.XMin,
		XMax:     req.XMax,
		Alpha:    req.Alpha,
		MaxAlpha: req.MaxAlpha,
		Priority: req.Priority,
	}

	allocated, err := s.store.RegisterStream(cfg)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, allocated)
}

type IngestRequest struct {
	StreamID string    `json:"stream_id"`
	Values   []float64 `json:"values"`
}

type IngestResponse struct {
	StreamID string `json:"stream_id"`
	Ingested int    `json:"ingested"`
	Status   string `json:"status"`
}

func (s *Server) handleIngest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req IngestRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if req.StreamID == "" || len(req.Values) == 0 {
		writeError(w, http.StatusBadRequest, "missing stream_id or empty values")
		return
	}

	ingested, err := s.store.Ingest(req.StreamID, req.Values)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, IngestResponse{
		StreamID: req.StreamID,
		Ingested: ingested,
		Status:   "ok",
	})
}

type QueryRequest struct {
	StreamID  string    `json:"stream_id"`
	Quantiles []float64 `json:"quantiles"`
}

type QueryResponse struct {
	StreamID string             `json:"stream_id"`
	Results  map[string]float64 `json:"results"`
}

func (s *Server) handleQuery(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "malformed request body")
		return
	}
	if req.StreamID == "" || len(req.Quantiles) == 0 {
		writeError(w, http.StatusBadRequest, "missing stream_id or quantiles")
		return
	}

	results, err := s.store.Query(req.StreamID, req.Quantiles)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, QueryResponse{
		StreamID: req.StreamID,
		Results:  results,
	})
}

func (s *Server) handleStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	writeJSON(w, http.StatusOK, s.store.GlobalStats())
}

func (s *Server) handleStreamDetail(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	streamID := strings.TrimPrefix(r.URL.Path, "/v1/streams/")
	if streamID == "" {
		writeError(w, http.StatusBadRequest, "missing stream id")
		return
	}

	stats, err := s.store.GetStreamStats(streamID)
	if err != nil {
		writeError(w, http.StatusNotFound, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, stats)
}
