#!/usr/bin/env bash
# EC2 "user data" — paste this into the Launch Instance -> Advanced details
# -> User data field as-is (base64-encoded by the console, or raw text).
# Runs once, as root, on first boot.
#
# Replace REPO_URL with your git URL. BRANCH defaults to main.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

REPO_URL="https://github.com/YOUR-USERNAME/YOUR-REPO.git"
BRANCH="main"
APP_DIR="/opt/ticket-classifier"

# Pull and run the full setup script.
apt-get update -y
apt-get install -y ca-certificates curl git

curl -fsSL https://raw.githubusercontent.com/yourname/yourrepo/main/deploy/ec2-setup.sh \
  -o /tmp/ec2-setup.sh || true

# If the script isn't hosted yet, fall back to an inline install.
if [[ ! -s /tmp/ec2-setup.sh ]]; then
  echo ">>> Fallback: cloning repo and running ec2-setup.sh from disk..."
  rm -rf "$APP_DIR"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
  bash "$APP_DIR/deploy/ec2-setup.sh" "$REPO_URL" "$BRANCH"
else
  bash /tmp/ec2-setup.sh "$REPO_URL" "$BRANCH"
fi