#!/usr/bin/env bash
# run_lab.sh — start the lab environment (web + visitors + attacker).
#
# This brings up the three containers. It does NOT start the SOC broker — you
# run that yourself in a second terminal so you can watch it think:
#     python3 broker/soc_broker.py
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Resetting previous runtime state (logs, alerts, firewall rules)..."
./scripts/reset_lab.sh --quiet

echo "Starting lab containers (web, visitors, attacker)..."
docker compose up -d

echo
echo "Lab is running."
echo "  • Target website:   http://localhost:8080"
echo "  • Protected console: http://localhost:8080/admin/   (try to log in — you don't have the password)"
echo "  • Live access log:   logs/access.json"
echo
echo "Now, in THIS terminal, start the defensive AI broker:"
echo "    python3 broker/soc_broker.py"
echo
echo "Watch it detect the attack and block the attacker's IP."
echo
echo "Stuck or not sure a step worked?  python3 scripts/check_progress.py"
echo "Stop everything when done with:   ./scripts/stop_lab.sh"
