#!/bin/sh
set -eu
mkdir -p /var/run/relay /var/log/relay
python3 /opt/relay/sink.py >/var/log/relay/sink.log 2>&1 & echo $! >/var/run/relay/sink.pid
sleep .1
python3 /opt/relay/relay_fragile.py >/var/log/relay/relay.log 2>&1 & echo $! >/var/run/relay/relay.pid
