package limiter

type RateLimiter interface {
// Allow returns true if the request is permitted, false otherwise.
Allow() bool
}
