# SysWatch — Server Health Monitoring System

A production-grade, multi-layered server monitoring system for Red Hat Enterprise Linux 10. It combines a Bash-based health-check engine, a real-time Python dashboard, email/Slack alerting, remote SSH monitoring, and historical trend charts — all of it open-source and deployable on any RHEL server.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Option A — Quick-start with Bash Only](#option-a--quick-start-with-bash-only)
  - [Option B — Full System with Live Dashboard](#option-b--full-system-with-live-dashboard)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
  - [The Bash Health-Check Engine](#the-bash-health-check-engine)
  - [The Live Dashboard API](#the-live-dashboard-api)
  - [Bonus Modules](#bonus-modules)
- [Configuration](#configuration)
- [Deployment](#deployment)
  - [Systemd Service](#systemd-service)
  - [Cron Scheduling](#cron-scheduling)
  - [Real Data Integration](#real-data-integration)
- [Using the Dashboard](#using-the-dashboard)
- [Running the Full Suite](#running-the-full-suite)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Overview

SysWatch was designed to give a DevOps engineer or system administrator an authoritative, real-time view of their server's health — at a glance. The system is split into two complementary layers:

| Layer | What it does | Tech |
|-------|-------------|------|
| **Bash Check Engine** | Runs cron-driven checks every 5 minutes, writes timestamped logs | Pure Bash + standard Linux tools |
| **Live Dashboard** | Visualises real CPU, memory, disk, and process data in a browser | Flask + `psutil` + Chart.js |

On top of those layers sit four *bonus* modules:

- **Email Alerts** — sends an email (via `mail`) whenever a check fails
- **Slack Webhooks** — posts a colour-coded notification into any Slack channel
- **Multi-Server SSH** — runs the same checks on remote servers through SSH keys
- **Historical Trend Chart** — renders an ASCII bar chart showing the last 10 readings for CPU, memory, and disk

The complete system works on RHEL 10 (and RHEL 8 / Rocky 9 / AlmaLinux 9) without any external dependencies beyond what ships with Red Hat.

---

## Architecture

```
  ┌─────────────────────── RHEL 10 Server ───────────────────────┐
  │                                                               │
  │  Firefox (local browser)                                      │
  │     │  fetches  http://127.0.0.1:5050/api/*                   │
  │     │  sends header:  X-API-Key: <your-key>                   │
  │     ▼                                                         │
  │  Python Flask API (metrics_api.py)                           │
  │     │  binds to 127.0.0.1 only — NOT reachable from network   │
  │     │  reads live data from psutil (kernel /proc data)        │
  │     │  reads historical logs from logs/health.log             │
  │     ▼                                                         │
  │  Linux Kernel  /proc/stat, /proc/meminfo, /proc/net/...       │
  │                                                               │
  │  ── Bonus layer ──                                           │
  │  check-email.sh  →  alerts via 'mail'                        │
  │  check-slack.sh  →  alerts via curl + Slack Incoming Webhook │
  │  check-remote.sh →  SSHes to remote servers (key-based)      │
  │  check-trend.sh  →  draws ASCII trend chart (awk)            │
  │                                                               │
  └───────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- The API binds to `127.0.0.1` **only** — it is never reachable from the network, even from another machine on the same subnet.
- Every API request carries a secret `X-API-Key` header. Without it, the API returns `401 Unauthorized`.
- The API key is stored in a file (`api/api.key`) with `0600` permissions — nobody but your user can read it.
- CORS is restricted to `file://` (browser-opened HTML files) and `localhost` origins only.

---

## Getting Started

### Prerequisites

| Tool | Why it's needed | Install (if missing) |
|------|----------------|----------------------|
| `python3 >= 3.9` | Flask API backend | `sudo dnf install -y python3` |
| `flask`, `flask-cors`, `psutil` | Python packages | `pip3 install flask flask-cors psutil --break-system-packages` |
| `nginx` (optional) | One of the monitored services | `sudo dnf install -y nginx` |
| `mail` or `s-nail` (optional) | Email alerts | `sudo dnf install -y s-nail` |
| `curl` (optional) | Slack webhooks | `sudo dnf install -y curl` |
| `ssh` (optional) | Remote checks | usually installed by default |

> The `--break-system-packages` flag on `pip3` is required on RHEL 10 because it enforces the externally-managed Python model. It is safe to use here.

---

### Option A — Quick-start with Bash Only

This is the foundational layer that works without any Python at all.

```bash
cd ~/health-monitor
./monitor.sh
```

It runs four checks:

| Check | How it works | Source |
|-------|-------------|--------|
| **CPU** | Reads `top -bn1` and computes `100 - idle%` | `top` |
| **Memory** | Reads `free -m` and computes used/total ratio | `free` |
| **Disk** | Reads `df -h /` and extracts the Use% column | `df` |
| **Services** | Loops over services in `config.cfg` and calls `systemctl is-active` | `systemctl` |

Each check prints a colour-coded PASS/ALERT to the terminal and appends a timestamped line to `logs/health.log`. An HTML report is also generated in `reports/report.html`.

---

### Option B — Full System with Live Dashboard

1. **Install Python packages**

   ```bash
   pip3 install flask flask-cors psutil --break-system-packages
   python3 -c "import flask, flask_cors, psutil; print('All packages OK')"
   ```

2. **Generate an API key**

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))" \
     > ~/health-monitor/api/api.key
   cat ~/health-monitor/api/api.key       # save this value
   chmod 600 ~/health-monitor/api/api.key  # lock it down
   ```

3. **Start the API**

   ```bash
   cd ~/health-monitor/api
   python3 metrics_api.py
   ```

   It prints:

   ```
     SysWatch Metrics API
     Listening on  http://127.0.0.1:5050
   ```

4. **Open the dashboard** in a browser (or a second terminal tab)

   ```bash
   firefox ~/health-monitor/reports/report.html
   ```

   Paste the API key you saved in step 2, click **Connect to Backend →**, and you will see live CPU, memory, disk, and process data — refreshing every two seconds.

---

## Project Structure

```
~/health-monitor/
│
├── monitor.sh                      # Main orchestrator (Bash)
├── config.cfg                      # Thresholds & service names (single source of truth)
├── remote_servers.cfg              # Server list for remote SSH checks (bonus)
│
├── checks/
│   ├── cpu.sh                      # CPU usage check
│   ├── memory.sh                   # Memory usage check
│   ├── disk.sh                     # Disk usage check
│   ├── services.sh                 # Service status check
│   ├── email_alert.sh              # Bonus 1: Email alert (optional)
│   ├── slack_alert.sh              # Bonus 2: Slack webhook (optional)
│   ├── remote_check.sh             # Bonus 3: SSH remote check (optional)
│   └── trend_chart.sh              # Bonus 4: ASCII trend chart (optional)
│
├── api/
│   ├── metrics_api.py              # Flask API backend (Python)
│   └── api.key                     # API key (0600)
│
├── reports/
│   └── report.html                 # Generated HTML report (static)
│      └── server-monitor-live.html # Live dashboard (static, wired to API)
│
└── logs/
    └── health.log                  # Timestamped log entries
```

---

## How It Works

### The Bash Health-Check Engine

```
config.cfg  →  loads thresholds
   │
   ├─► checks/cpu.sh       top -bn1  →  CPU %
   ├─► checks/memory.sh    free -m   →  Memory %
   ├─► checks/disk.sh      df -h /   →  Disk %
   └─► checks/services.sh  systemctl  →  service state
   │
   └─► logs/health.log     (append-only)
   │
   └─► reports/report.html (generated HTML)
```

Every script sources `config.cfg` at the top, reads the relevant live metric from the system, compares it against the configured threshold, and writes a single timestamped line to `logs/health.log`.

**`config.cfg`** looks like this:

```bash
CPU_THRESHOLD=80
MEMORY_THRESHOLD=75
DISK_THRESHOLD=90
SERVICES="sshd crond nginx"
```

This file is the single source of truth — change a number here and every check picks up the new value instantly.

---

### The Live Dashboard API

`metrics_api.py` is a Flask application that collects real metrics from your running system and serves them over HTTP to the browser dashboard.

#### Endpoints

| Endpoint | Auth? | What it returns |
|----------|-------|-----------------|
| `GET /api/health` | No | Simple liveness check (status + timestamp) |
| `GET /api/metrics` | Yes (`X-API-Key`) | CPU, memory, disk, and system info as JSON |
| `GET /api/processes` | Yes | Top processes by CPU / memory / disk I/O |
| `GET /api/logs` | Yes | Last 50 log lines from `health.log` |

The Flask app runs on a background thread that refreshes disk I/O counters every 2 seconds, so the I/O speed figures in the `/api/metrics` response are real deltas, not static values.

#### Security model

- Bound to `127.0.0.1` (never the network)
- Every authenticated endpoint rejects requests without a valid `X-API-Key` header
- The API key is read from a file on disk and never hardcoded
- CORS is restricted to `null` (file://) and localhost origins
- Process-list endpoint throws away per-user auth data

---

### Bonus Modules

| Module | File | Purpose | Trigger |
|--------|------|---------|---------|
| Email Alert | `checks/email_alert.sh` | Sends an email when any check fails | `MAIL_ALERTS_ENABLED=true` |
| Slack Webhook | `checks/slack_alert.sh` | Posts a red-highlighted message into Slack | `SLACK_ALERTS_ENABLED=true` |
| Remote SSH | `checks/remote_check.sh` | SSHes to servers in `remote_servers.cfg` and runs all checks | Key-based auth |
| Trend Chart | `checks/trend_chart.sh` | Renders the last 10 readings for CPU, memory, disk as ASCII bars | Always available |

To enable a bonus, edit `config.cfg` and set the corresponding `*_ENABLED=true`.

---

## Configuration

`config.cfg` lives in the project root. Every check script sources it at the top.

| Setting | Default | Description |
|---------|---------|-------------|
| `CPU_THRESHOLD` | `80` | Alert if CPU usage exceeds this % |
| `MEMORY_THRESHOLD` | `75` | Alert if memory usage exceeds this % |
| `DISK_THRESHOLD` | `90` | Alert if root partition usage exceeds this % |
| `SERVICES` | `"sshd crond nginx"` | Space-separated list of services to monitor |
| `EMAIL_ALERTS_ENABLED` | `false` | Enable or disable email alerts |
| `ALERT_EMAIL` | `"user@localhost"` | Where to send alerts |
| `EMAIL_FROM` | `"healthmonitor@localhost"` | Sender address |
| `EMAIL_SUBJECT_PREFIX` | `"[SERVER ALERT]"` | Email subject prefix |
| `SLACK_ALERTS_ENABLED` | `false` | Enable or disable Slack alerts |
| `SLACK_WEBHOOK_URL` | (empty) | Full Slack Incoming Webhook URL |

---

## Deployment

### Systemd Service

The project ships with `syswatch-api.service` to make the API start automatically on boot and survive crashes:

```bash
sudo cp syswatch-api.service /etc/systemd/system/syswatch-api.service
sudo sed -i 's/student/your-actual-username/g' /etc/systemd/system/syswatch-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now syswatch-api
sudo systemctl status syswatch-api
```

The service file includes:

- `NoNewPrivileges=yes` — cannot escalate privileges
- `PrivateTmp=yes` — private `/tmp`
- `ProtectSystem=strict` — filesystem is read-only except `/logs` and `/api`
- `Restart=on-failure` with a 5-second delay

### Cron Scheduling

The Bash engine runs via two cron jobs:

```cron
*/5 * * * * /home/student/health-monitor/monitor.sh >> /home/student/health-monitor/logs/health.log 2>&1
0 8 * * * /home/student/health-monitor/monitor.sh --report >> /home/student/health-monitor/logs/health.log 2>&1
```

The first runs checks every 5 minutes and appends results to the log file. The second runs every day at 8 AM and (re)generates the HTML report.

---

### Real Data Integration

Follow the integration guide to move from the Bash-only setup to the live dashboard:

1. Install `flask`, `flask-cors`, and `psutil`.
2. Generate an API key (`secrets.token_hex(32)`).
3. Copy `metrics_api.py` into `api/`.
4. Place `server-monitor-live.html` as your dashboard file.
5. Start the API and open the dashboard in Firefox.

The API polls the Linux kernel through `psutil` every 2–3 seconds, so all four panels (CPU, memory, disk, processes) update in real time as you browse the dashboard.

---

## Using the Dashboard

1. Open `reports/server-monitor-live.html` in Firefox.
2. You will see a dark login form with the SysWatch logo and an API-key field.
3. Paste the key from `api/api.key`, click **Connect to Backend →**.
4. The login form disappears and the dashboard loads.
5. Verify the data against the terminal:
   - **CPU card** should match `top` or `htop` output.
   - **Memory card** should match `free -m` output.
   - **Disk card** should match `df -h /` output.
   - **Process table** should show real processes (`sshd`, `systemd`, `nginx`).

If you want the dashboard to trigger danger alerts, temporarily lower the thresholds in the JavaScript `CFG` block (in `report.html`), refresh the browser, and observe them firing. Then raise them back to production values.

---

## Running the Full Suite

```bash
cd ~/health-monitor
./monitor.sh
```

This single command:

1. Runs all four Bash health checks (CPU, memory, disk, services).
2. Writes results to `logs/health.log`.
3. Generates an HTML report in `reports/report.html`.
4. (If configured) Sends email alerts for any failures.
5. (If configured) Posts Slack messages for any failures.
6. (If configured) Checks all remote servers listed in `remote_servers.cfg`.
7. (Always) Displays the ASCII trend chart if the log has at least five readings per metric.

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| API refuses connection from browser | Service not running | `sudo systemctl status syswatch-api` |
| `ModuleNotFoundError` | Python packages missing | Re-run `pip3 install flask flask-cors psutil` |
| "Permission denied" reading `api.key` | Wrong file mode | `chmod 600 ~/health-monitor/api/api.key` |
| Dashboard shows `---` for every metric | 401 auth failure | Verify you copied the full 64-character key; ensure no leading/trailing whitespace |
| Process table is empty or sparse | API runs under a restricted user | Set `User=root` in the systemd service file (for testing only) |
| Trend chart shows "No data found" | Not enough log entries | Run `./monitor.sh` five or more times, then retry |
| Remote SSH asks for a password | Key not installed on target | `ssh-copy-id user@host` |
| HTML report is blank | Log file is empty or misquoted | Run `./monitor.sh` at least three times first |

For detailed troubleshooting of each bonus module, see **Bonus Challenges — Automated Server Health Monitor** (`bonus challenge complete guide.md`).

---

## References

| Document | What it covers |
|----------|----------------|
| `bonus challenge complete guide.md` | Complete step-by-step guide for all four bonus modules (email, Slack, SSH, ASCII trend chart) |
| `Real_Data_Integration_Guide_01.md` | Full guide for wiring up the live dashboard (installation, service, firewall, cron) |
| `Server_Health_Monitor_Guide.md` | Original Bash-only guide — foundation layer (tasks 1–5) |
| `metrics_api.py` | Source code for the Flask API backend (every endpoint documented in this README) |
| `syswatch-api.service` | Systemd unit file (auto-start, restart, security hardening) |
| `server-monitor-live.html` | Live dashboard HTML (dark theme, Chart.js, responsive) |
| `Health_Monitor_Documentation.pdf` | Compressed documentation archive (all contents) |

---

*SysWatch — Monitor once, learn everything. Built on Red Hat Enterprise Linux 10.*
