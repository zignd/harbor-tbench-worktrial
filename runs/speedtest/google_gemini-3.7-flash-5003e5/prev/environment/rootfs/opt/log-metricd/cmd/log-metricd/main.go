package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"log-metricd/pkg/api"
	"log-metricd/pkg/planner"
	"log-metricd/pkg/storage"
)

type Config struct {
	ListenAddr   string
	BucketBudget int
	DefaultAlpha float64
	LogFile      string
}

func parseSimpleConfig(path string) (*Config, error) {
	cfg := &Config{
		ListenAddr:   ":9090",
		BucketBudget: 2048,
		DefaultAlpha: 0.01,
		LogFile:      "/var/log/log-metricd/service.log",
	}

	f, err := os.Open(path)
	if err != nil {
		return cfg, nil
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val := strings.TrimSpace(parts[1])
		val = strings.Trim(val, string([]byte{39, 34, 32}))

		switch key {
		case "listen_addr":
			cfg.ListenAddr = val
		case "bucket_budget":
			var b int
			if _, err := fmt.Sscanf(val, "%d", &b); err == nil && b > 0 {
				cfg.BucketBudget = b
			}
		case "default_alpha":
			var a float64
			if _, err := fmt.Sscanf(val, "%f", &a); err == nil && a > 0 {
				cfg.DefaultAlpha = a
			}
		case "log_file":
			cfg.LogFile = val
		}
	}
	return cfg, nil
}

func main() {
	configPath := flag.String("config", "/etc/log-metricd/config.yaml", "path to config file")
	flag.Parse()

	cfg, err := parseSimpleConfig(*configPath)
	if err != nil {
		log.Fatalf("failed to parse config: %v", err)
	}

	if cfg.LogFile != "" {
		logF, err := os.OpenFile(cfg.LogFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			log.Fatalf("unable to open log file %s: %v", cfg.LogFile, err)
		}
		defer logF.Close()
		multi := io.MultiWriter(os.Stdout, logF)
		log.SetOutput(multi)
	}

	log.Printf("[INFO] Initializing log-metricd daemon on %s (budget=%d, alpha=%f)",
		cfg.ListenAddr, cfg.BucketBudget, cfg.DefaultAlpha)

	p := planner.NewBudgetPlanner(cfg.BucketBudget)
	store := storage.NewMetricStore(p)
	srv := api.NewServer(store)

	mux := http.NewServeMux()
	srv.RegisterRoutes(mux)

	httpServer := &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("[INFO] Server listening on %s", cfg.ListenAddr)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	<-stopChan
	log.Println("[INFO] Shutting down log-metricd...")
	_ = httpServer.Close()
	log.Println("[INFO] Server stopped.")
}
