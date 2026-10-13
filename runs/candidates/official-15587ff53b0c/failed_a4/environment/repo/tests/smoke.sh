#!/bin/sh
set -eu
./bin/reconcile-pack < fixtures/basic.ledger >/dev/null
