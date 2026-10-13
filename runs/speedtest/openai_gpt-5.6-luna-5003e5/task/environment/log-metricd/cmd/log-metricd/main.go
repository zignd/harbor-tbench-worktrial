package main

import (
	"log"
	"log-metricd/pkg/api"
	"log-metricd/pkg/storage"
	"net/http"
)

func main() {
	s := &api.Server{Store: storage.New(), Budget: 2048}
	log.Fatal(http.ListenAndServe(":9090", s.Handler()))
}
