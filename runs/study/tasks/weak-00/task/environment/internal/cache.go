package internal

import (
"fmt"
"sync"
"time"
)

// UserData represents user data retrieved from the DB.
type UserData struct {
ID        string
Name      string
Email     string
Timestamp time.Time // When this data was fetched/updated
}

// Cache is an in-memory cache for user data.
type Cache struct {
data map[string]UserData
// We need a way to track expiry. A simple map with expiry times could work, or a sorted list/heap.
// Let's use a map for simplicity for now, mapping UserID to its expiry time.
expiryTimes map[string]time.Time
mu        sync.RWMutex
// TTL is the Time To Live for cache entries.
TTL       time.Duration
}

// NewCache creates a new Cache with the given TTL.
func NewCache(ttl time.Duration) *Cache {
c := &Cache{
data:      make(map[string]UserData),
expiryTimes: make(map[string]time.Time),
TTL:       ttl,
}
// Start a background goroutine to clean up expired entries.
go c.cleanupLoop()
return c
}

// Get retrieves user data from the cache. Returns the data and a boolean indicating if it was a cache hit.
func (c *Cache) Get(userID string) (UserData, bool) {
c.mu.RLock()
defer c.mu.RUnlock()

data, ok := c.data[userID]
if !ok {
return UserData{}, false
}

// Check if the entry has expired (this check should ideally be done by cleanup, but double-checking here can be defensive).
expiry, expiryOK := c.expiryTimes[userID]
if !expiryOK || time.Now().After(expiry) {
// This might happen if cleanup hasn't run yet, or if there's a race.
// For now, consider it expired and remove it.
// Note: This is a potential area for bugs if not handled carefully with locks.
delete(c.data, userID)
delete(c.expiryTimes, userID)
return UserData{}, false
}

return data, true
}

// Set adds or updates user data in the cache.
func (c *Cache) Set(userID string, data UserData) {
c.mu.Lock()
defer c.mu.Unlock()

newData := data // Make a copy to avoid external modification
newData.Timestamp = time.Now()

c.data[userID] = newData
c.expiryTimes[userID] = time.Now().Add(c.TTL)
}

// Invalidate removes user data from the cache.
func (c *Cache) Invalidate(userID string) {
c.mu.Lock()
defer c.mu.Unlock()

delete(c.data, userID)
delete(c.expiryTimes, userID)
}

// cleanupLoop runs in the background to remove expired cache entries.
func (c *Cache) cleanupLoop() {
// We need a ticker to periodically check for expired items.
ticker := time.NewTicker(c.TTL / 2) // Check twice per TTL
defer ticker.Stop()

for range ticker.C {
c.mu.Lock()
now := time.Now()
for userID, expiry := range c.expiryTimes {
if now.After(expiry) {
delete(c.data, userID)
delete(c.expiryTimes, userID)
}
}
c.mu.Unlock()
}
}

// For testing purposes: simulate DB access.
// In a real scenario, this would hit a database.
var mockDB = map[string]UserData{
"user1": {ID: "user1", Name: "Alice", Email: "alice@example.com"},
"user2": {ID: "user2", Name: "Bob", Email: "bob@example.com"},
}

// FetchUserData simulates fetching user data from a database.
func FetchUserData(userID string) (UserData, error) {
// Simulate network latency or DB query time
time.Sleep(20 * time.Millisecond)

data, ok := mockDB[userID]
if !ok {
return UserData{}, fmt.Errorf("user %s not found", userID)
}
return data, nil
}
