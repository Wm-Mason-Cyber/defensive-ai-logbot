#!/usr/bin/env bash
# start_visitors.sh — STEP 3: add simulated normal employees and visitors.
#
# Does NOT reset anything, so your own Step 2 traffic stays in the log.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting the normal-traffic script (visitors)..."
docker compose up -d visitors

echo
echo "Step 3 — 'regular traffic' is now hitting the website."
echo "  • Watch it arrive:   tail -f logs/access.json     (Ctrl-C to stop watching)"
echo "  • Count log lines:   wc -l logs/access.json"
echo
echo "Remember: this is a SCRIPT (traffic/legit_users.py), not real people."
