package api

import (
"encoding/json"
"net/http"
"strconv"
"time"

"log-metricd/pkg/planner"
"log-metricd/pkg/storage"
)

type Server struct {
store     *storage.MetricStore
startTime time.Time
}

func NewServer(store *storage.MetricStore) *Server {
return &Server{
store:     store,
startTime: time.Now(),
}
}

type HealthResponse struct {
Status        string `json:"status"`
Streams       int    `json:"streams"`
UptimeSeconds int64  `json:"uptime_seconds"`
}

func (s *Server) HandleHealthz(w http.ResponseWriter, r *http.Request) {
if r.Method != http.MethodGet {
http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
return
}
uptime := int64(time.Since(s.startTime).Seconds())
resp := HealthResponse{
Status:        "ok",
Streams:       s.store.StreamCount(),
UptimeSeconds: uptime,
}
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusOK)
_ = json.NewEncoder(w).Encode(resp)
}

type RegisterRequest struct {
StreamID         string  `json:"stream_id"`
MinValue         float64 `json:"min_value"`
MaxValue         float64 `json:"max_value"`
MaxRelativeError float64 `json:"max_relative_error"`
Priority         int     `json:"priority"`
}

type RegisterResponse struct {
Status           string                    `json:"status"`
StreamID         string                    `json:"stream_id"`
AllocatedBuckets int                       `json:"allocated_buckets"`
EffectiveAlpha   float64                   `json:"effective_alpha"`
EffectiveGamma   float64                   `json:"effective_gamma"`
CompactionFactor int                       `json:"compaction_factor"`
StreamAllocation *planner.StreamAllocation `json:"stream_allocation,omitempty"`
}

func (s *Server) HandleRegister(w http.ResponseWriter, r *http.Request) {
if r.Method != http.MethodPost {
http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
return
}

var req RegisterRequest
if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
http.Error(w, `{"error":"invalid json body"}`, http.StatusBadRequest)
return
}

if req.StreamID == "" {
http.Error(w, `{"error":"stream_id is required"}`, http.StatusBadRequest)
return
}
if req.MinValue <= 0 {
req.MinValue = 1.0
}
if req.MaxValue <= req.MinValue {
req.MaxValue = 10000.0
}
if req.MaxRelativeError <= 0 || req.MaxRelativeError >= 1 {
req.MaxRelativeError = 0.01
}

spec := planner.StreamSpec{
StreamID:         req.StreamID,
MinValue:         req.MinValue,
MaxValue:         req.MaxValue,
MaxRelativeError: req.MaxRelativeError,
Priority:         req.Priority,
}

alloc, err := s.store.RegisterStream(spec)
if err != nil {
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusBadRequest)
_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
return
}

resp := RegisterResponse{
Status:           "registered",
StreamID:         alloc.StreamID,
AllocatedBuckets: alloc.AllocatedBuckets,
EffectiveAlpha:   alloc.EffectiveAlpha,
EffectiveGamma:   alloc.EffectiveGamma,
CompactionFactor: alloc.CompactionFactor,
StreamAllocation: alloc,
}
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusOK)
_ = json.NewEncoder(w).Encode(resp)
}

type IngestRequest struct {
StreamID string    `json:"stream_id"`
Values   []float64 `json:"values"`
}

type IngestResponse struct {
Status string `json:"status"`
Count  int    `json:"count"`
}

func (s *Server) HandleIngest(w http.ResponseWriter, r *http.Request) {
if r.Method != http.MethodPost {
http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
return
}

var req IngestRequest
if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
http.Error(w, `{"error":"invalid json body"}`, http.StatusBadRequest)
return
}

if req.StreamID == "" {
http.Error(w, `{"error":"stream_id is required"}`, http.StatusBadRequest)
return
}

count, err := s.store.Ingest(req.StreamID, req.Values)
if err != nil {
w.Header().Set("Content-Type", "application/json")
if err == storage.ErrStreamNotFound {
w.WriteHeader(http.StatusNotFound)
} else {
w.WriteHeader(http.StatusBadRequest)
}
_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
return
}

resp := IngestResponse{
Status: "ingested",
Count:  count,
}
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusOK)
_ = json.NewEncoder(w).Encode(resp)
}

type QueryRequest struct {
StreamID  string    `json:"stream_id"`
Quantiles []float64 `json:"quantiles"`
}

type QueryResponse struct {
StreamID string             `json:"stream_id"`
Count    uint64             `json:"count"`
Results  map[string]float64 `json:"results"`
}

func (s *Server) HandleQuery(w http.ResponseWriter, r *http.Request) {
if r.Method != http.MethodPost {
http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
return
}

var req QueryRequest
if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
http.Error(w, `{"error":"invalid json body"}`, http.StatusBadRequest)
return
}

if req.StreamID == "" {
http.Error(w, `{"error":"stream_id is required"}`, http.StatusBadRequest)
return
}
if len(req.Quantiles) == 0 {
req.Quantiles = []float64{0.5, 0.9, 0.99}
}

rawRes, count, err := s.store.Query(req.StreamID, req.Quantiles)
if err != nil {
w.Header().Set("Content-Type", "application/json")
if err == storage.ErrStreamNotFound {
w.WriteHeader(http.StatusNotFound)
} else {
w.WriteHeader(http.StatusBadRequest)
}
_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
return
}

formatted := make(map[string]float64, len(rawRes))
for q, val := range rawRes {
formatted[strconv.FormatFloat(q, 'f', -1, 64)] = val
}

resp := QueryResponse{
StreamID: req.StreamID,
Count:    count,
Results:  formatted,
}
w.Header().Set("Content-Type", "application/json")
w.WriteHeader(http.StatusOK)
_ = json.NewEncoder(w).Encode(resp)
}

func (s *Server) RegisterRoutes(mux *http.ServeMux) {
mux.HandleFunc("/healthz", s.HandleHealthz)
mux.HandleFunc("/v1/streams/register", s.HandleRegister)
mux.HandleFunc("/v1/ingest", s.HandleIngest)
mux.HandleFunc("/v1/query", s.HandleQuery)
}
