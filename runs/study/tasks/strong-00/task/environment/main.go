package main

import (
"fmt"
"net/http"
"os"
"strconv"
"gophershield/limiter"
)

func main() {
rate, _ := strconv.ParseFloat(os.Getenv("RATE"), 64)
capacity, _ := strconv.ParseFloat(os.Getenv("CAPACITY"), 64)

l := limiter.NewLeakyBucket(rate, capacity)

http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
if l.Allow() {
w.WriteHeader(http.StatusOK)
} else {
w.WriteHeader(http.StatusTooManyRequests)
}
})

fmt.Printf("Starting server on :8080 with rate %v and capacity %v\n", rate, capacity)
http.ListenAndServe(":8080", nil)
}
