# Deploying to an AWS EC2 instance

This guide walks you through launching a fresh Ubuntu EC2 instance and
running the `ticket-classifier` container on it. Everything you need
(security group rules, IAM policy, user data, post-launch steps) is here.

## 0. Prerequisites

- An AWS account with permission to create VPC resources, key pairs, and EC2
  instances.
- Your project code in a Git repo (GitHub, GitLab, CodeCommit, Bitbucket…).
- The repo must contain `Dockerfile`, `docker-compose.yml`, `requirements.txt`,
  `main.py`, and `classifier.py` — all of which are already in this project.

## 1. Create (or pick) a key pair

EC2 console → **Network & Security → Key Pairs → Create key pair**.

- Name: `ticket-classifier-key`
- Type: **RSA**
- Format: **`.pem`** (for OpenSSH on macOS/Linux/Windows)
- Save `ticket-classifier-key.pem` somewhere safe. You'll need it to SSH.

## 2. Create a security group

EC2 console → **Network & Security → Security Groups → Create security group**.

| Inbound rule | Protocol | Port | Source          | Why                              |
|--------------|----------|------|-----------------|----------------------------------|
| SSH          | TCP      | 22   | Your IP / `0.0.0.0/0` | SSH into the box            |
| Custom TCP   | TCP      | 8000 | `0.0.0.0/0`     | Hit the public API on port 8000  |

Egress: leave as default (all traffic out).

## 3. Launch the EC2 instance

EC2 console → **Instances → Launch instances**.

- **Name**: `ticket-classifier`
- **AMI**: **Ubuntu Server 22.04 LTS** (or 24.04) — x86_64
- **Instance type**: `t3.micro` (free tier) for dev, `t3.small` for low traffic
- **Key pair**: select the one from step 1
- **Network settings → Select existing security group**: pick the one from step 2
- **Storage**: 8 GB gp3 is plenty
- **Advanced details → IAM instance profile**: `AmazonEC2ReadOnlyAccess` is fine
  (or your own scoped role) — *not required* unless you later use SSM/S3/etc.
- **Advanced details → User data**: paste the contents of
  `deploy/user-data.sh` (edit `REPO_URL` first!) — or skip this and run the
  setup script manually after launch (next step).

Click **Launch instance**.

## 4. Option A — auto-deploy via user data (easiest)

Before pasting `user-data.sh` into the launch wizard:

1. Edit `deploy/user-data.sh` and replace `REPO_URL` with your real git URL.
2. Make sure `deploy/ec2-setup.sh` exists in the repo at that URL.
3. Paste the whole file into **Advanced details → User data**.

The instance will install Docker, clone your repo, build, and start the
container on first boot. Wait ~3–5 minutes, then jump to step 6.

## 4. Option B — manual deploy via SSH

1. Get the instance's **Public IPv4 address** from the EC2 console.
2. SSH in:

   ```bash
   chmod 400 ticket-classifier-key.pem
   ssh -i ticket-classifier-key.pem ubuntu@<PUBLIC-IP>
   ```

3. Pull this repo (or just `scp` the files in) and run the bootstrap:

   ```bash
   git clone https://github.com/YOUR-USER/YOUR-REPO.git
   cd YOUR-REPO
   sudo bash deploy/ec2-setup.sh https://github.com/YOUR-USER/YOUR-REPO.git main
   ```

   This script:
   - Installs Docker Engine + Compose plugin
   - Clones the repo into `/opt/ticket-classifier`
   - Runs `docker compose up -d --build`
   - Registers a systemd unit so the container restarts on reboot

## 5. (Optional) Allocate and attach an Elastic IP

If you stop/start the instance, its public IP changes. To pin a permanent IP:

EC2 → **Network & Security → Elastic IPs → Allocate**, then **Associate** with
the instance.

## 6. Verify it works

From the EC2 host:

```bash
curl http://127.0.0.1:8000/health
# -> {"status":"ok","service":"ticket-classifier"}

curl -X POST http://127.0.0.1:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-3","message":"Someone called asking my OTP"}'
```

From your laptop:

```bash
curl http://<PUBLIC-IP>:8000/health
```

Swagger UI is at: `http://<PUBLIC-IP>:8000/docs`

## 7. Day-2 operations

| Task              | Command (run on the EC2 host)                                   |
|-------------------|-----------------------------------------------------------------|
| View logs         | `docker compose -f /opt/ticket-classifier/docker-compose.yml logs -f` |
| Restart           | `sudo systemctl restart ticket-classifier`                      |
| Rebuild + reload  | `cd /opt/ticket-classifier && git pull && sudo systemctl reload ticket-classifier` |
| Stop              | `cd /opt/ticket-classifier && docker compose down`              |
| Roll back         | `sudo bash /opt/ticket-classifier/deploy/rollback.sh`           |

## 8. Putting HTTPS in front (optional but recommended)

Don't expose port 8000 directly to the internet for real traffic. Two simple
options:

- **Domain + Caddy reverse proxy** — point a domain at the Elastic IP, install
  Caddy (`sudo apt install -y caddy`), put this in `/etc/caddy/Caddyfile`:

  ```
  api.example.com {
      reverse_proxy 127.0.0.1:8000
  }
  ```

  Caddy provisions Let's Encrypt certificates automatically.

- **AWS ALB + ACM** — front the instance with an Application Load Balancer and
  terminate HTTPS using an ACM certificate.

## 9. Cost notes

| Resource        | Approx. cost                       |
|-----------------|------------------------------------|
| `t3.micro`      | Free tier eligible for 12 months   |
| `t3.small`      | ~$0.02/hr (~$15/month)             |
| 8 GB gp3        | ~$0.80/month                       |
| Elastic IP      | Free while attached, $0.005/hr idle|
| Data transfer   | 100 GB/month free outbound         |

Stop the instance (don't terminate) when not in use to stop the clock.