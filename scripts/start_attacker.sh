#!/usr/bin/env bash
# start_attacker.sh — STEP 4: start the simulated password-guessing attacker.
#
# Does NOT reset anything. The attacker is a script (traffic/attacker.py) that
# keeps running until you stop the lab with ./scripts/stop_lab.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting the attacker script (attacker)..."
docker compose up -d attacker

echo
echo "Step 4 — 'bad traffic' is now hitting /admin/ in bursts of failed logins."
echo "  • Only the failed logins:  grep '\"status\":401' logs/access.json | tail"
echo "  • What the attacker says:  docker logs lab-attacker"
echo
echo "The attacker keeps going until you run:  ./scripts/stop_lab.sh"
