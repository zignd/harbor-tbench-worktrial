#!/bin/bash
set -e
for f in /opt/quant-reconcile/staging/*; do /opt/quant-reconcile/bin/ingest_batch.sh "$f" & done
wait
