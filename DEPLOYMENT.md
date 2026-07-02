# VARY — Production Deployment Guide

Deploy the VARY automation system to a Linux VPS so the API server runs 24/7
and all GitHub Actions workflows trigger correctly.

---

## Architecture Overview

```
GitHub (scheduled)
  ├── daily_short.yml       ─── 3x/day: runs pipeline directly on GitHub runner
  ├── performance_poll.yml  ─── Every 6h: polls YouTube stats, runs evolution
  └── weekly_channel_update.yml ─── Weekly: updates channel branding

VPS (24/7 Linux server)
  ├── Flask API server      ─── port 5001, used by n8n for manual/interactive runs
  ├── n8n (optional)        ─── Workflow orchestration (calls VARY API)
  ├── Evolution Engine      ─── Reads critique + performance data, mutates params
  └── Assets                ─── /opt/vary/assets/ (logs, clips, thumbnails)
```

**Key insight:** GitHub Actions runs the pipeline directly on GitHub's runners.
The VPS is **only needed for the API server** (if using n8n) and for persistent
long-term data storage. If you don't use n8n, you DON'T need a VPS at all —
GitHub Actions runs everything.

---

## 1. Choose a VPS Provider

| Provider | Price | RAM | Disk | Best for |
|----------|-------|-----|------|----------|
| **Hetzner** | ~€4/mo | 2 GB | 20 GB | Best value, EU/US datacenters |
| **DigitalOcean** | ~$6/mo | 1 GB | 25 GB | Easiest setup, great docs |
| **Oracle Cloud** | $0/mo | Up to 24 GB | 200 GB | Free but hard signup |
| **AWS Lightsail** | ~$5/mo | 1 GB | 40 GB | AWS ecosystem |

**Recommendation:** Start with **Hetzner CX22** (€4/mo, 2 GB RAM, 20 GB SSD)
or **DigitalOcean $6 droplet** (1 GB RAM, 25 GB SSD).

---

## 2. Initial Server Setup (Ubuntu 22.04/24.04)

SSH into your server:

```bash
ssh root@<your-server-ip>
```

### 2.1 System Update & Dependencies

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv ffmpeg git curl nginx
```

### 2.2 Create a Dedicated User

```bash
useradd -m -s /bin/bash vary
usermod -aG sudo vary
```

### 2.3 Clone the Repository

```bash
su - vary
git clone https://github.com/<your-username>/<your-repo>.git /opt/vary
cd /opt/vary
```

### 2.4 Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install flask python-dotenv yt-dlp pillow requests \
  google-api-python-client google-auth-httplib2 google-auth-oauthlib \
  gunicorn
```

### 2.5 Create .env File

```bash
nano /opt/vary/.env
```

Contents:

```env
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token
OUTPUT_DIR=/opt/vary/assets
API_PORT=5001
```

### 2.6 Create Asset Directories

```bash
mkdir -p /opt/vary/assets/{downloads,clips,thumbnails/variants,logs,channel_art}
```

### 2.7 Set Permissions

```bash
chown -R vary:vary /opt/vary
```

---

## 3. Systemd Service — Flask API Server

Create a systemd service so the API server starts on boot and restarts if it crashes:

```bash
sudo nano /etc/systemd/system/vary-api.service
```

```ini
[Unit]
Description=VARY — Daily Clip Pipeline API Server
After=network.target

[Service]
User=vary
WorkingDirectory=/opt/vary
Environment=PATH=/opt/vary/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EnvironmentFile=/opt/vary/.env
ExecStart=/opt/vary/venv/bin/python /opt/vary/api_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vary-api
sudo systemctl start vary-api
```

Check status:

```bash
sudo systemctl status vary-api
# Should show: active (running)
```

View logs:

```bash
sudo journalctl -u vary-api -f
```

---

## 4. Nginx Reverse Proxy (Optional — for public API)

If you want the API accessible at `https://vary.yourdomain.com` instead of
just `http://localhost:5001`:

```bash
sudo nano /etc/nginx/sites-available/vary
```

```nginx
server {
    listen 80;
    server_name vary.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vary /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

For HTTPS (recommended):

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d vary.yourdomain.com
```

---

## 5. GitHub Actions — Secrets Setup

The GitHub Actions workflows run **on GitHub's runners**, not on your VPS.
They don't need the VPS. But they need YouTube API credentials.
Set these in your GitHub repo:

### Go to: `Settings → Secrets and variables → Actions`

Add these secrets:

| Secret name | Value |
|---|---|
| `YOUTUBE_CLIENT_ID` | Your Google Cloud OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | Your Google Cloud OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | OAuth refresh token (get via `--auth-flow`) |
| `YOUTUBE_TOKEN_B64` | Base64-encoded pickle of the full token: `base64 -w0 youtube_token.pickle` |

### How to generate the token:

Run this **locally** (on your machine where YouTube auth works):

```bash
python -m modules.youtube_uploader --auth-flow
# Follow the browser to authorize

# Then encode it for GitHub:
base64 -w0 youtube_token.pickle > youtube_token.b64
# On Windows PowerShell:
# [Convert]::ToBase64String([IO.File]::ReadAllBytes("youtube_token.pickle")) > youtube_token.b64
```

Copy the entire contents of `youtube_token.b64` into the `YOUTUBE_TOKEN_B64` secret.

---

## 6. Cron Jobs on the VPS (Alternative to GitHub Actions)

If you prefer the VPS to handle everything instead of GitHub Actions:

```bash
sudo crontab -u vary -e
```

Add:

```cron
# VARY Pipeline — 3 times daily
33 7 * * * cd /opt/vary && /opt/vary/venv/bin/python run_pipeline.py >> /opt/vary/assets/logs/cron.log 2>&1
55 17 * * * cd /opt/vary && /opt/vary/venv/bin/python run_pipeline.py >> /opt/vary/assets/logs/cron.log 2>&1
18 22 * * * cd /opt/vary && /opt/vary/venv/bin/python run_pipeline.py >> /opt/vary/assets/logs/cron.log 2>&1

# Performance Poll — every 6 hours
0 */6 * * * cd /opt/vary && /opt/vary/venv/bin/python -c "from modules.performance_tracker import poll_all_videos; poll_all_videos(); from modules.evolution_engine import evolve; evolve()" >> /opt/vary/assets/logs/cron.log 2>&1

# Weekly Channel Update (Sunday at 12:00 UTC)
0 12 * * 0 cd /opt/vary && /opt/vary/venv/bin/python -c "from modules.channel_manager import check_and_update_channel; check_and_update_channel()" >> /opt/vary/assets/logs/cron.log 2>&1
```

---

## 7. Monitor & Health Check

### Quick health check:

```bash
curl http://127.0.0.1:5001/health
# Expected: {"status":"ok","channel":"VARY","timestamp":"..."}
```

### Systemd monitoring:

```bash
# Check service
sudo systemctl status vary-api

# Restart if hung
sudo systemctl restart vary-api

# Watch logs
sudo journalctl -u vary-api -n 50 -f
```

### Disk usage (clips accumulate):

```bash
du -sh /opt/vary/assets/
```

The pipeline auto-cleans clips older than 7 days, but check monthly.

---

## 8. Backup Strategy

### What to back up:

| Path | Why | Frequency |
|------|-----|-----------|
| `/opt/vary/assets/logs/` | Evolution state, critique history, performance log | Weekly |
| `/opt/vary/.env` | YouTube credentials | After changes |
| `/opt/vary/youtube_token.pickle` | YouTube auth token | After refresh |

### Simple backup script:

```bash
#!/bin/bash
# /opt/vary/backup.sh
BACKUP_DIR="/root/vary-backups"
mkdir -p $BACKUP_DIR
tar czf "$BACKUP_DIR/vary-logs-$(date +%Y%m%d).tar.gz" \
  /opt/vary/assets/logs/ \
  /opt/vary/.env \
  /opt/vary/youtube_token.pickle 2>/dev/null
# Keep only last 30 days
find $BACKUP_DIR -name "vary-logs-*.tar.gz" -mtime +30 -delete
```

Add to root's crontab: `0 3 * * 0 /opt/vary/backup.sh`

---

## 9. Updating the Server

```bash
# Pull latest code
cd /opt/vary
git pull

# Update Python packages
source venv/bin/activate
pip install --upgrade -r requirements.txt  # if exists

# Restart the API server
sudo systemctl restart vary-api
```

---

## Quick Reference

```bash
# Start server
sudo systemctl start vary-api

# Stop server
sudo systemctl stop vary-api

# Restart server
sudo systemctl restart vary-api

# View recent logs
sudo journalctl -u vary-api -n 50

# Follow logs live
sudo journalctl -u vary-api -f

# Test API is alive
curl http://127.0.0.1:5001/health

# Check evolution status
curl http://127.0.0.1:5001/evolution-status

# Run pipeline manually (on VPS)
cd /opt/vary && source venv/bin/activate && python run_pipeline.py --type movie

# Run performance poll manually
cd /opt/vary && source venv/bin/activate && python -m modules.performance_tracker --poll
```

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| API won't start | `sudo journalctl -u vary-api -n 20` — missing Python module? |
| YouTube upload fails | Token expired? Run `--auth-flow` again |
| Pipeline times out | `timeout-minutes: 180` in workflow — increase if downloads are slow |
| ffmpeg errors | `which ffmpeg` — must be installed |
| No critique data | Run pipeline at least once to generate clips to critique |
| Evolution not mutating | Need ≥3 real performance data points before trust threshold |

---

## Next: What You Can Do Now

☐ 1. Pick a VPS provider (Hetzner CX22 or DigitalOcean $6 droplet recommended)  
☐ 2. SSH in and run the initial setup commands  
☐ 3. Copy `.env` secrets and `youtube_token.pickle` to the server  
☐ 4. Start the systemd service: `sudo systemctl start vary-api`  
☐ 5. Set GitHub Actions secrets (3 workflows will start automatically on cron)  
☐ 6. (Optional) Set up cron on VPS for direct pipeline runs  
☐ 7. Verify: `curl http://127.0.0.1:5001/health` returns OK
