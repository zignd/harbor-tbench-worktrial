package main

import (
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"

	"gopkg.in/yaml.v3"

	"log-metricd/pkg/api"
	"log-metricd/pkg/planner"
	"log-metricd/pkg/storage"
)

type Config struct {
	ListenAddr   string  `yaml:"listen_addr"`
	TotalBudget  int     `yaml:"total_budget"`
	DefaultAlpha float64 `yaml:"default_alpha"`
	LogFile      string  `yaml:"log_file"`
}

func loadConfig(path string) (*Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open config: %w", err)
	}
	defer f.Close()

	var cfg Config
	if err := yaml.NewDecoder(f).Decode(&cfg); err != nil {
		return nil, fmt.Errorf("failed to decode config: %w", err)
	}

	if cfg.ListenAddr == "" {
		cfg.ListenAddr = "0.0.0.0:9090"
	}
	if cfg.TotalBudget <= 0 {
		cfg.TotalBudget = 2048
	}
	if cfg.DefaultAlpha <= 0 || cfg.DefaultAlpha >= 1 {
		cfg.DefaultAlpha = 0.01
	}
	return &cfg, nil
}

func setupLogging(logPath string) (*os.File, error) {
	if logPath == "" {
		log.SetOutput(os.Stdout)
		return nil, nil
	}

	f, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return nil, fmt.Errorf("cannot open log file %s: %w", logPath, err)
	}
	mw := io.MultiWriter(os.Stdout, f)
	log.SetOutput(mw)
	return f, nil
}

func main() {
	configPath := flag.String("config", "/etc/log-metricd/config.yaml", "Path to configuration file")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("Configuration error: %v", err)
	}

	logFile, err := setupLogging(cfg.LogFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to initialize logging: %v\n", err)
		os.Exit(1)
	}
	if logFile != nil {
		defer logFile.Close()
	}

	log.Printf("Starting log-metricd daemon on %s (budget: %d, default alpha: %f)",
		cfg.ListenAddr, cfg.TotalBudget, cfg.DefaultAlpha)

	budgetPlanner := planner.NewPlanner(cfg.TotalBudget)
	store := storage.NewStore(budgetPlanner)
	server := api.NewServer(store)

	log.Printf("Service initialized successfully, listening on %s", cfg.ListenAddr)
	if err := http.ListenAndServe(cfg.ListenAddr, server); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
