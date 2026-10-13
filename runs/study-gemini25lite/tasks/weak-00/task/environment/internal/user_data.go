package internal

import (
"encoding/json"
"fmt"
"os"
"sync"
"time"
)

// UserData struct definition (redundant but good for self-containment of this file)
type UserData struct {
ID        string    `json:"id"`
Name      string    `json:"name"`
Email     string    `json:"email"`
Timestamp time.Time `json:"-"` // Not to be marshalled, internal use
}

// UserDataService handles user data operations.
type UserDataService struct {
cache *Cache
db    map[string]UserData // Mock DB
mu    sync.RWMutex
}

// NewUserDataService creates a new UserDataService.
func NewUserDataService(cacheTTL time.Duration) *UserDataService {
// Load initial data from JSON
initialData, err := loadInitialUserData("./user_data.json")
if err != nil {
// In a real app, this might be a fatal error. For this task, we'll log and continue.
fmt.Fprintf(os.Stderr, "Warning: Failed to load initial user data: %v\n", err)
}

db := make(map[string]UserData)
for _, data := range initialData {
db[data.ID] = data
}

return &UserDataService{
cache: NewCache(cacheTTL),
db:    db,
}
}

// GetUserData retrieves user data, first from cache, then from DB if not found.
func (s *UserDataService) GetUserData(userID string) (UserData, error) {
// Try cache first
userData, hit := s.cache.Get(userID)
if hit {
return userData, nil
}

// Not in cache, fetch from DB
ss.mu.RLock()
dbData, ok := s.db[userID]
ss.mu.RUnlock()

if !ok {
return UserData{}, fmt.Errorf("user %s not found in DB", userID)
}

// Update cache with fresh data and return
updatedUserData := dbData // Copy to ensure we don't modify the DB entry directly via cache
ss.cache.Set(userID, updatedUserData)
return updatedUserData, nil
}

// UpdateUserData updates user data in the DB and invalidates the cache.
func (s *UserDataService) UpdateUserData(userID string, name, email string) error {
s.mu.Lock()
defer s.mu.Unlock()

_, exists := s.db[userID]
if !exists {
return fmt.Errorf("user %s not found in DB for update", userID)
}

// Update DB
s.db[userID] = UserData{ID: userID, Name: name, Email: email}

// Invalidate cache entry for this user
ss.cache.Invalidate(userID)

return nil
}

// loadInitialUserData loads user data from a JSON file.
func loadInitialUserData(filePath string) ([]UserData, error) {
file, err := os.Open(filePath)
if err != nil {
return nil, fmt.Errorf("failed to open %s: %w", filePath, err)
}
defer file.Close()

var users []UserData
if err := json.NewDecoder(file).Decode(&users); err != nil {
return nil, fmt.Errorf("failed to decode JSON from %s: %w", filePath, err)
}
return users, nil
}

// Mock DB data for initial population.
var mockDBInitial = []UserData{
{ID: "user1", Name: "Alice", Email: "alice@example.com"},
{ID: "user2", Name: "Bob", Email: "bob@example.com"},
{ID: "user3", Name: "Charlie", Email: "charlie@example.com"},
}

// Write mockDBInitial to user_data.json if it doesn't exist.
func init() {
// This init function is primarily for local development/testing of these files.
// In the Docker build, we will explicitly copy a user_data.json.
_, err := os.Stat("./user_data.json")
if os.IsNotExist(err) {
file, createErr := os.Create("./user_data.json")
if createErr != nil {
fmt.Fprintf(os.Stderr, "Error creating user_data.json: %v\n", createErr)
return
}
defer file.Close()

encoder := json.NewEncoder(file)
encoder.SetIndent("", "  ") // Pretty print JSON
if encodeErr := encoder.Encode(mockDBInitial); encodeErr != nil {
fmt.Fprintf(os.Stderr, "Error encoding initial data to user_data.json: %v\n", encodeErr)
}
}
}

// Simulate DB access delay for FetchUserData
func FetchUserData(userID string) (UserData, error) {
time.Sleep(20 * time.Millisecond)
// This function is defined in cache.go, but for completeness, it's good to have it here too.
// In a real app, this would hit a database.
// For the purpose of this task, it's assumed cache.go's FetchUserData is the one used.
return UserData{}, fmt.Errorf("FetchUserData not implemented here, should be in cache.go")
}
