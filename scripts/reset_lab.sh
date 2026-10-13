#!/usr/bin/env bash
# reset_lab.sh — clear runtime artifacts so the next run starts clean.
# Removes generated logs, incident files, and firewall rules (restores template).
set -euo pipefail
cd "$(dirname "$0")/.."
QUIET="${1:-}"

rm -f logs/*.json logs/*.log
rm -f alerts/incident_*.json
cp firewall/blocklist.conf.template firewall/blocklist.conf

[ "$QUIET" = "--quiet" ] || echo "Runtime state cleared (logs, alerts, firewall rules reset to empty)."
