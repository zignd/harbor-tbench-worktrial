package planner

import (
"errors"
"fmt"
"math"
"sort"
"sync"
)

var (
ErrBudgetExceeded     = errors.New("cannot accommodate stream within global bucket budget")
ErrStreamAlreadyExist = errors.New("stream ID already registered")
)

type StreamSpec struct {
StreamID         string  `json:"stream_id"`
MinValue         float64 `json:"min_value"`
MaxValue         float64 `json:"max_value"`
MaxRelativeError float64 `json:"max_relative_error"`
Priority         int     `json:"priority"`
}

type StreamAllocation struct {
StreamID         string  `json:"stream_id"`
AllocatedBuckets int     `json:"allocated_buckets"`
EffectiveGamma   float64 `json:"effective_gamma"`
EffectiveAlpha   float64 `json:"effective_alpha"`
CompactionFactor int     `json:"compaction_factor"`
MinValue         float64 `json:"min_value"`
MaxValue         float64 `json:"max_value"`
}

type BudgetPlanner struct {
mu          sync.Mutex
totalBudget int
allocations map[string]*StreamAllocation
specs       map[string]StreamSpec
}

func NewBudgetPlanner(totalBudget int) *BudgetPlanner {
if totalBudget <= 0 {
totalBudget = 2048
}
return &BudgetPlanner{
totalBudget: totalBudget,
allocations: make(map[string]*StreamAllocation),
specs:       make(map[string]StreamSpec),
}
}

func (p *BudgetPlanner) TotalBudget() int {
return p.totalBudget
}

func (p *BudgetPlanner) GetAllocation(streamID string) (*StreamAllocation, bool) {
p.mu.Lock()
defer p.mu.Unlock()
alloc, exists := p.allocations[streamID]
return alloc, exists
}

func (p *BudgetPlanner) GetAllAllocations() map[string]*StreamAllocation {
p.mu.Lock()
defer p.mu.Unlock()
res := make(map[string]*StreamAllocation, len(p.allocations))
for k, v := range p.allocations {
cp := *v
res[k] = &cp
}
return res
}

func (p *BudgetPlanner) RegisterStream(spec StreamSpec) (*StreamAllocation, error) {
p.mu.Lock()
defer p.mu.Unlock()

if _, exists := p.specs[spec.StreamID]; exists {
return nil, ErrStreamAlreadyExist
}

if spec.MinValue <= 0 || spec.MaxValue <= spec.MinValue {
return nil, fmt.Errorf("invalid range [%f, %f]", spec.MinValue, spec.MaxValue)
}
if spec.MaxRelativeError <= 0 || spec.MaxRelativeError >= 1 {
spec.MaxRelativeError = 0.01
}

p.specs[spec.StreamID] = spec

plan, err := p.recomputePlan()
if err != nil {
delete(p.specs, spec.StreamID)
return nil, err
}

p.allocations = plan
return p.allocations[spec.StreamID], nil
}

func (p *BudgetPlanner) recomputePlan() (map[string]*StreamAllocation, error) {
n := len(p.specs)
if n == 0 {
return make(map[string]*StreamAllocation), nil
}

type streamReq struct {
spec         StreamSpec
idealBuckets int
baseGamma    float64
}

var reqs []streamReq
totalIdeal := 0
for _, spec := range p.specs {
gamma := 1.0 + spec.MaxRelativeError
ideal := int(math.Ceil(math.Log(spec.MaxValue/spec.MinValue) / math.Log(gamma)))
if ideal < 1 {
ideal = 1
}
reqs = append(reqs, streamReq{
spec:         spec,
idealBuckets: ideal,
baseGamma:    gamma,
})
totalIdeal += ideal
}

sort.Slice(reqs, func(i, j int) bool {
return reqs[i].spec.Priority > reqs[j].spec.Priority
})

allocs := make(map[string]*StreamAllocation)

if totalIdeal <= p.totalBudget {
for _, req := range reqs {
allocs[req.spec.StreamID] = &StreamAllocation{
StreamID:         req.spec.StreamID,
AllocatedBuckets: req.idealBuckets,
EffectiveGamma:   req.baseGamma,
EffectiveAlpha:   req.spec.MaxRelativeError,
CompactionFactor: 1,
MinValue:         req.spec.MinValue,
MaxValue:         req.spec.MaxValue,
}
}
return allocs, nil
}

quota := p.totalBudget / n
if quota < 4 {
return nil, ErrBudgetExceeded
}

for _, req := range reqs {
allocs[req.spec.StreamID] = &StreamAllocation{
StreamID:         req.spec.StreamID,
AllocatedBuckets: quota,
EffectiveGamma:   req.baseGamma,
EffectiveAlpha:   req.spec.MaxRelativeError,
CompactionFactor: 1,
MinValue:         req.spec.MinValue,
MaxValue:         req.spec.MaxValue,
}
}

return allocs, nil
}
