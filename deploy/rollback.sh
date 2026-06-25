#!/usr/bin/env bash
# Roll back to the previous image tag after a bad deploy.
# Run on the EC2 host: sudo bash deploy/rollback.sh

set -euo pipefail
APP_DIR="/opt/ticket-classifier"
cd "$APP_DIR"

echo ">>> Current images:"
docker images ticket-classifier --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}\t{{.ID}}"

PREVIOUS=$(docker images ticket-classifier --format "{{.Repository}}:{{.Tag}}\t{{.ID}}" \
  | grep -v ":latest" | head -n 1 | awk -F'\t' '{print $1}')

if [[ -z "$PREVIOUS" ]]; then
  echo "No previous image tag found. Aborting." >&2
  exit 1
fi

echo ">>> Rolling back to: $PREVIOUS"
docker compose down
docker tag "$PREVIOUS" ticket-classifier:latest
docker compose up -d

echo ">>> Rollback complete."
docker compose ps