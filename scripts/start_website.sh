#!/usr/bin/env bash
# start_website.sh — STEP 1: start ONLY the Acme Corp website (no other traffic).
#
# With nothing else running, every line in the log is yours. That makes Step 2
# (finding your own requests in the log) easy.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Resetting previous runtime state (logs, alerts, batches, firewall rules)..."
./scripts/reset_lab.sh --quiet

echo "Starting the website container (web)..."
docker compose up -d --wait web

echo
echo "Step 1 — the website is running. Nobody else is visiting it yet."
echo "  • Browse it:          http://localhost:8080"
echo "  • Staff-only console: http://localhost:8080/admin/"
echo
echo "When you've explored, go on to Step 2 in the Student Guide (find your traffic in the log)."
echo "Not sure a step worked?  python3 scripts/check_progress.py"
