#!/usr/bin/env bash
# Bootstrap script for an Ubuntu 22.04 / 24.04 EC2 instance.
# Run as root (or via sudo) AFTER the instance is reachable via SSH.
#
# Usage:
#   sudo bash ec2-setup.sh <git-repo-url> [branch]
#
# Example:
#   sudo bash ec2-setup.sh https://github.com/yourname/ticket-classifier.git main
#
# What it does:
#   1. Installs Docker Engine + Compose plugin
#   2. Adds the `ubuntu` user to the docker group
#   3. Clones the repo into /opt/ticket-classifier
#   4. Builds the image and runs it via docker compose
#   5. Configures a systemd unit so the container restarts on reboot
#   6. Opens port 8000 in UFW (optional)

set -euo pipefail

REPO_URL="${1:-}"
BRANCH="${2:-main}"
APP_DIR="/opt/ticket-classifier"
SERVICE_NAME="ticket-classifier"

if [[ -z "$REPO_URL" ]]; then
  echo "Usage: sudo bash $0 <git-repo-url> [branch]" >&2
  exit 1
fi

echo ">>> Installing Docker..."
apt-get update -y
apt-get install -y ca-certificates curl gnupg git ufw

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
usermod -aG docker ubuntu || true

echo ">>> Cloning $REPO_URL @ $BRANCH into $APP_DIR..."
# Move out of $APP_DIR if we're inside it, otherwise `rm -rf` would
# delete our own working directory and `git clone` would fail with
# "Unable to read current working directory".
pushd / >/dev/null 2>&1 || cd /
rm -rf "$APP_DIR"
git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
popd >/dev/null 2>&1 || true
# chown is best-effort: skip when the `ubuntu` user doesn't exist (e.g. AMI
# images with a different default user, or running inside a container).
chown -R ubuntu:ubuntu "$APP_DIR" 2>/dev/null || true

echo ">>> Building image and starting container..."
# `cd` defensively — the earlier `rm -rf` may have moved us.
cd "$APP_DIR" 2>/dev/null || cd /
docker compose up -d --build

# Only register the systemd unit when systemd is actually present. Inside
# containers (no PID 1 systemd) this would fail with `policy-rc.d returned 101`.
if [[ -d /run/systemd/system ]]; then
  echo ">>> Writing systemd unit for auto-restart..."
  cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Ticket Classifier container
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose up -d --build
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${SERVICE_NAME}.service
else
  echo ">>> No systemd detected (container?) — skipping unit registration."
fi

echo ">>> Opening firewall port 8000..."
# `ufw` may not be installed inside a container; tolerate that.
command -v ufw >/dev/null 2>&1 && {
  ufw allow OpenSSH || true
  ufw allow 8000/tcp || true
  yes | ufw enable || true
} || echo ">>> ufw not available, skipping firewall config."
ufw allow 8000/tcp || true
yes | ufw enable || true

echo ">>> Done. Container status:"
docker compose -f "$APP_DIR/docker-compose.yml" ps
echo
echo "Test it:  curl http://127.0.0.1:8000/health"
echo "Public:   http://<EC2-PUBLIC-IP>:8000/health"