#!/bin/bash
set -e

# Ensure data directory exists
mkdir -p /app/data

# Pre-populate the database with 48 hours of historical records for 20 users
# This runs a small Node.js script to seed the DB before the service starts
node /app/seed.js

echo "[start] launching snippet-eval-service on port 4000"
exec node /app/service/server.js
