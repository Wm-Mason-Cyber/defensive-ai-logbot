#!/usr/bin/env bash
# run_lab.sh — shortcut: start EVERYTHING at once (web + visitors + attacker).
#
# Students normally go one step at a time instead:
#     ./scripts/start_website.sh    (Step 1)
#     ./scripts/start_visitors.sh   (Step 3)
#     ./scripts/start_attacker.sh   (Step 4)
# This script is for re-runs, demos, and catching up quickly. It does NOT start
# the SOC broker — you run that yourself so you can watch it think:
#     python3 broker/soc_broker.py
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Resetting previous runtime state (logs, alerts, batches, firewall rules)..."
./scripts/reset_lab.sh --quiet

echo "Starting lab containers (web, visitors, attacker)..."
docker compose up -d

echo
echo "Lab is running (all three containers)."
echo "  • Target website:    http://localhost:8080"
echo "  • Protected console: http://localhost:8080/admin/"
echo "  • Live access log:   logs/access.json"
echo
echo "To run the Defensive AI:  python3 broker/soc_broker.py"
echo
echo "Stuck or not sure a step worked?  python3 scripts/check_progress.py"
echo "Stop everything when done with:   ./scripts/stop_lab.sh"
