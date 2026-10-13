package main

import (
"fmt"
"log"
"net/http"
"os"
"strconv"
"time"

"github.com/yourusername/go-cache-invalidation-debug/internal"
)

var userService *internal.UserDataService

func main() {
// Initialize the service with a TTL of 5 seconds
cacheTTL, err := time.ParseDuration("5s")
if err != nil {
log.Fatalf("Invalid TTL duration: %v", err)
}

userService = internal.NewUserDataService(cacheTTL)

http.HandleFunc("/user/get/", handleGetUser)
http.HandleFunc("/user/update/", handleUpdateUser)

port := "8080"
if p := os.Getenv("PORT"); p != "" {
port = p
}

log.Printf("Server starting on port %s\n", port)
if err := http.ListenAndServe(":"+port, nil); err != nil {
log.Fatalf("Could not start server: %v\n", err)
}
}

handleGetUser(w http.ResponseWriter, r *http.Request) {
userID := r.URL.PathValue("userID")
if userID == "" {
http.Error(w, "User ID is required", http.StatusBadRequest)
return
}

startTime := time.Now()
userData, err := userService.GetUserData(userID)
if err != nil {
http.Error(w, fmt.Sprintf("Error getting user data: %v", err), http.StatusInternalServerError)
return
}

// Simulate latency check for cache lookups
lookupDuration := time.Since(startTime)
if lookupDuration > 50*time.Millisecond {
log.Printf("WARN: Cache lookup for user %s exceeded threshold: %v\n", userID, lookupDuration)
}

w.Header().Set("Content-Type", "application/json")
json.NewEncoder(w).Encode(userData)
}

handleUpdateUser(w http.ResponseWriter, r *http.Request) {
userID := r.URL.PathValue("userID")
if userID == "" {
http.Error(w, "User ID is required", http.StatusBadRequest)
return
}

var updateData struct {
Name  string `json:"name"`
Email string `json:"email"`
}
if err := json.NewDecoder(r.Body).Decode(&updateData);
err != nil {
http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
return
}

startTime := time.Now()
err := userService.UpdateUserData(userID, updateData.Name, updateData.Email)
if err != nil {
http.Error(w, fmt.Sprintf("Error updating user data: %v", err), http.StatusInternalServerError)
return
}

// Simulate latency check for cache invalidations/updates
updateDuration := time.Since(startTime)
if updateDuration > 100*time.Millisecond {
log.Printf("WARN: Cache update for user %s exceeded threshold: %v\n", userID, updateDuration)
}

w.WriteHeader(http.StatusOK)
}
