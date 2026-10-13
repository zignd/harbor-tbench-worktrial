package main

import (
"flag"
"fmt"
"net/http"
"sync"
"time"
)

func main() {
url := flag.String("url", "http://localhost:8080", "URL to attack")
duration := flag.Duration("duration", 10*time.Second, "Duration of attack")
concurrent := flag.Int("concurrent", 100, "Number of concurrent goroutines")
flag.Parse()

start := time.Now()
end := start.Add(*duration)

var wg sync.WaitGroup
results := make(chan int, 1000000)

for i := 0; i < *concurrent; i++ {
wg.Add(1)
go func() {
defer wg.Done()
client := &http.Client{Timeout: 500 * time.Millisecond}
for time.Now().Before(end) {
resp, err := client.Get(*url)
if err == nil {
results <- resp.StatusCode
resp.Body.Close()
} else {
results <- 0
}
}
}()
}

go func() {
wg.Wait()
close(results)
}()

ok := 0
tooMany := 0
other := 0
for res := range results {
switch res {
case http.StatusOK:
ok++
case http.StatusTooManyRequests:
tooMany++
default:
other++
}
}

fmt.Printf("OK: %d, TooManyRequests: %d, Other: %d\n", ok, tooMany, other)
}
