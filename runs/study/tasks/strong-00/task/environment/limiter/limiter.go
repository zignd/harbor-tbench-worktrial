package limiter

import (
"sync"
"time"
)

type LeakyBucket struct {
mu       sync.Mutex
rate     float64
capacity float64
count    float64
last     time.Time
}

func NewLeakyBucket(rate float64, capacity float64) *LeakyBucket {
return &LeakyBucket{
rate:     rate,
capacity: capacity,
last:     time.Now(),
}
}

func (b *LeakyBucket) Allow() bool {
// TODO: Implement a high-performance, thread-safe leaky bucket.
// The current implementation is a slow placeholder.
b.mu.Lock()
defer b.mu.Unlock()

now := time.Now()
elapsed := now.Sub(b.last).Seconds()
b.count -= elapsed * b.rate
if b.count < 0 {
b.count = 0
}
b.last = now

if b.count < b.capacity {
b.count++
return true
}
return false
}
