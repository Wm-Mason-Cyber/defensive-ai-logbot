#!/usr/bin/env bash
# stop_lab.sh — stop and remove the lab containers. Leaves logs/alerts for review.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down -t 2
echo "Lab stopped. Your logs/ and alerts/ from this run are kept for review."
echo "Run ./scripts/reset_lab.sh to clear them before the next run."
