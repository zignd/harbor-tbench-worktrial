package config

import (
    "bufio"
    "fmt"
    "os"
    "strconv"
    "strings"
)

// Config contains the static service settings. The small deployment config is
// intentionally parsed without a third-party YAML dependency.
type Config struct {
    Listen               string
    GlobalBucketBudget   int
    DefaultAlpha         float64
    LogDirectory         string
    ReadTimeoutSeconds   int
    WriteTimeoutSeconds  int
    MaxIngestBatch       int
}

func Default() *Config {
    return &Config{
        Listen:              "0.0.0.0:9090",
        GlobalBucketBudget:  2048,
        DefaultAlpha:        0.01,
        LogDirectory:        "/var/log/log-metricd",
        ReadTimeoutSeconds:  15,
        WriteTimeoutSeconds: 15,
        MaxIngestBatch:      50000,
    }
}

func Load(path string) (*Config, error) {
    cfg := Default()
    file, err := os.Open(path)
    if err != nil {
        return nil, fmt.Errorf("open config: %w", err)
    }
    defer file.Close()

    scanner := bufio.NewScanner(file)
    line := 0
    for scanner.Scan() {
        line++
        text := strings.TrimSpace(scanner.Text())
        if text == "" || strings.HasPrefix(text, "#") {
            continue
        }
        key, value, found := strings.Cut(text, ":")
        if !found {
            return nil, fmt.Errorf("config line %d: expected key: value", line)
        }
        key = strings.TrimSpace(key)
        value = strings.TrimSpace(value)
        value = strings.Trim(value, "\"'")
        switch key {
        case "listen":
            cfg.Listen = value
        case "global_bucket_budget":
            n, err := strconv.Atoi(value)
            if err != nil {
                return nil, fmt.Errorf("config line %d: %w", line, err)
            }
            cfg.GlobalBucketBudget = n
        case "default_alpha":
            f, err := strconv.ParseFloat(value, 64)
            if err != nil {
                return nil, fmt.Errorf("config line %d: %w", line, err)
            }
            cfg.DefaultAlpha = f
        case "log_directory":
            cfg.LogDirectory = value
        case "read_timeout_seconds":
            n, err := strconv.Atoi(value)
            if err != nil {
                return nil, fmt.Errorf("config line %d: %w", line, err)
            }
            cfg.ReadTimeoutSeconds = n
        case "write_timeout_seconds":
            n, err := strconv.Atoi(value)
            if err != nil {
                return nil, fmt.Errorf("config line %d: %w", line, err)
            }
            cfg.WriteTimeoutSeconds = n
        case "max_ingest_batch":
            n, err := strconv.Atoi(value)
            if err != nil {
                return nil, fmt.Errorf("config line %d: %w", line, err)
            }
            cfg.MaxIngestBatch = n
        default:
            return nil, fmt.Errorf("config line %d: unknown key %q", line, key)
        }
    }
    if err := scanner.Err(); err != nil {
        return nil, fmt.Errorf("read config: %w", err)
    }
    if err := cfg.validate(); err != nil {
        return nil, err
    }
    return cfg, nil
}

func (c *Config) validate() error {
    if c.Listen == "" {
        return fmt.Errorf("listen address is required")
    }
    if c.GlobalBucketBudget <= 0 {
        return fmt.Errorf("global_bucket_budget must be positive")
    }
    if c.DefaultAlpha <= 0 || c.DefaultAlpha >= 1 {
        return fmt.Errorf("default_alpha must be in (0, 1)")
    }
    if c.ReadTimeoutSeconds <= 0 || c.WriteTimeoutSeconds <= 0 {
        return fmt.Errorf("HTTP timeouts must be positive")
    }
    if c.MaxIngestBatch <= 0 {
        return fmt.Errorf("max_ingest_batch must be positive")
    }
    return nil
}
