# SysWatch — Real Data Integration Guide
## Connecting the Dashboard to Your RHEL 10 System

---

## ARCHITECTURE OVERVIEW

```
Your RHEL 10 Server
─────────────────────────────────────────────────────────
  Firefox (local browser)
      │  fetches http://127.0.0.1:5050/api/*
      │  sends header:  X-API-Key: <your-key>
      ▼
  Python Flask API  (metrics_api.py)
      │  binds to 127.0.0.1 only — NOT reachable from network
      │  reads from psutil (kernel /proc data)
      │  reads from logs/health.log
      ▼
  Linux Kernel  /proc/stat, /proc/meminfo, /proc/net/...
─────────────────────────────────────────────────────────

SECURITY MODEL:
  • API bound to 127.0.0.1 — no external access, ever
  • Every request must carry the secret X-API-Key header
  • Key lives in a file readable only by your user account
  • Key is stored in browser session memory — cleared on tab close
  • CORS restricted to localhost and file:// origins only
  • No passwords, hostnames, or auth data ever returned by API
```

---

## TABLE OF CONTENTS

1. [Install Python packages](#1-install-python-packages)
2. [Place the project files](#2-place-the-project-files)
3. [Generate your API key](#3-generate-your-api-key)
4. [Set file permissions](#4-set-file-permissions)
5. [Test the API manually](#5-test-the-api-manually)
6. [Set up as a systemd service](#6-set-up-as-a-systemd-service-auto-start)
7. [Configure the firewall](#7-configure-the-firewall-optional-but-recommended)
8. [Open the dashboard](#8-open-the-dashboard-in-firefox)
9. [Connect and verify live data](#9-connect-and-verify-live-data)
10. [Customise thresholds](#10-customise-thresholds-in-the-dashboard)
11. [Daily cron integration](#11-integrate-with-your-existing-cron-jobs)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Install Python Packages

The API backend needs Python 3, Flask, Flask-CORS, and psutil.
All are installed system-wide using pip with the RHEL flag.

### Step 1.1 — Verify Python 3 is available

```bash
python3 --version
```

Expected output (RHEL 10 ships Python 3.12):
```
Python 3.12.x
```

If you see "command not found":
```bash
sudo dnf install -y python3
```

### Step 1.2 — Install pip (if missing)

```bash
pip3 --version
```

If missing:
```bash
sudo dnf install -y python3-pip
```

### Step 1.3 — Install the three required packages

```bash
pip3 install flask flask-cors psutil --break-system-packages
```

> The `--break-system-packages` flag is required on RHEL 10 because
> it uses the externally-managed Python model. It is safe to use here.

### Step 1.4 — Verify all packages installed correctly

```bash
python3 -c "import flask, flask_cors, psutil; print('All packages OK')"
```

Expected output:
```
All packages OK
```

If any package is missing, you will see an ImportError — re-run Step 1.3.

---

## 2. Place the Project Files

### Step 2.1 — Create the api/ subdirectory inside your project

```bash
mkdir -p ~/health-monitor/api
```

### Step 2.2 — Copy metrics_api.py into the api/ folder

```bash
# If you received metrics_api.py as a download, move it here:
cp ~/Downloads/metrics_api.py ~/health-monitor/api/metrics_api.py

# OR create it directly with nano:
nano ~/health-monitor/api/metrics_api.py
# (paste the full content of metrics_api.py, then Ctrl+O, Enter, Ctrl+X)
```

### Step 2.3 — Copy the dashboard HTML into the reports/ folder

```bash
cp ~/Downloads/server-monitor-live.html ~/health-monitor/reports/report.html
```

> This replaces the previously generated report.html with the live version.

### Step 2.4 — Confirm the folder structure

```bash
find ~/health-monitor -type f | sort
```

You should see:
```
/home/<you>/health-monitor/api/metrics_api.py
/home/<you>/health-monitor/checks/cpu.sh
/home/<you>/health-monitor/checks/disk.sh
/home/<you>/health-monitor/checks/memory.sh
/home/<you>/health-monitor/checks/services.sh
/home/<you>/health-monitor/config.cfg
/home/<you>/health-monitor/logs/health.log
/home/<you>/health-monitor/monitor.sh
/home/<you>/health-monitor/reports/report.html
```

---

## 3. Generate Your API Key

The API key is a random 64-character hex string. It is generated once
and stored in a file. You paste it into the dashboard login screen.

### Step 3.1 — Generate the key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))" \
  > ~/health-monitor/api/api.key
```

### Step 3.2 — Display and copy the key

```bash
cat ~/health-monitor/api/api.key
```

You will see something like:
```
a3f8c2d1e4b7906a2c5d8e1f4b7a3c6d9e2f5a8b1c4d7e0f3a6b9c2d5e8f1a4
```

**Write this down or keep this terminal open** — you will paste it into
the browser dashboard when you open it.

---

## 4. Set File Permissions

This step locks the api.key file so only your user account can read it.

```bash
# api.key: readable only by you, no group or other access
chmod 600 ~/health-monitor/api/api.key

# metrics_api.py: readable and executable by you only
chmod 700 ~/health-monitor/api/metrics_api.py

# Verify permissions
ls -la ~/health-monitor/api/
```

Expected output:
```
-rwx------. 1 student student ... metrics_api.py
-rw-------. 1 student student ... api.key
```

The `600` on api.key means: owner can read/write, nobody else can.
If someone else on the server runs `cat api.key` they will get:
```
cat: api.key: Permission denied
```

---

## 5. Test the API Manually

Before setting up the service, run the API directly and test it works.

### Step 5.1 — Open a second terminal tab

Keep your original terminal open. In the new tab, run:

```bash
cd ~/health-monitor/api
python3 metrics_api.py
```

You should see:
```
  SysWatch Metrics API
  Listening on  http://127.0.0.1:5050
  API key file  /home/student/health-monitor/api/api.key
  Log file      /home/student/health-monitor/logs/health.log
  Network scope 127.0.0.1 only (not exposed)
```

**Leave this running.** Go back to the first terminal.

### Step 5.2 — Test the liveness endpoint (no key required)

```bash
curl http://127.0.0.1:5050/api/health
```

Expected output:
```json
{"status":"ok","ts":"2025-08-15T10:23:01.123456"}
```

### Step 5.3 — Test that auth rejection works

```bash
# This should return 401 Unauthorized
curl -w "\nHTTP STATUS: %{http_code}\n" http://127.0.0.1:5050/api/metrics
```

Expected output:
```
<!DOCTYPE HTML...
HTTP STATUS: 401
```

Good — the API is rejecting requests without the key.

### Step 5.4 — Test with the correct API key

```bash
# Read the key into a variable
MY_KEY=$(cat ~/health-monitor/api/api.key)

# Call the metrics endpoint
curl -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/metrics | python3 -m json.tool
```

You should see a large block of JSON like:
```json
{
  "cpu": {
    "core_count": 8,
    "freq_mhz": 2400.0,
    "load1": 0.45,
    "load15": 0.72,
    "load5": 0.61,
    "percent": 12.3,
    "per_core": [8.0, 15.0, 6.0, ...]
  },
  "disk": { ... },
  "memory": { ... },
  "system": { ... }
}
```

### Step 5.5 — Test the processes endpoint

```bash
curl -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/processes | python3 -m json.tool | head -40
```

You should see real processes from your system.

### Step 5.6 — Test the logs endpoint

```bash
# First make sure your health.log has some entries
cd ~/health-monitor && ./monitor.sh

# Now test
curl -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/logs
```

### Step 5.7 — Confirm it is NOT reachable from outside

If you have another machine on the same network, try:
```bash
# From another machine (replace 192.168.x.x with your server IP)
curl http://192.168.x.x:5050/api/health
```

Expected: connection refused or timeout. The API only accepts
connections from 127.0.0.1 — not from any other IP address.

### Step 5.8 — Stop the test server

Press `Ctrl+C` in the second terminal to stop the API.

---

## 6. Set Up as a Systemd Service (Auto-Start)

This makes the API start automatically when your server boots.

### Step 6.1 — Copy the service unit file

```bash
# Copy the service file to /etc/systemd/system/
sudo cp ~/Downloads/syswatch-api.service /etc/systemd/system/syswatch-api.service
```

### Step 6.2 — Edit the service file with your actual username

```bash
sudo nano /etc/systemd/system/syswatch-api.service
```

Find every line that says `student` and replace it with your actual
Linux username. To find your username:

```bash
whoami
```

For example, if your username is `devops`, change:
```
User=student
Group=student
WorkingDirectory=/home/student/health-monitor/api
ExecStart=/usr/bin/python3 /home/student/health-monitor/api/metrics_api.py
ReadWritePaths=/home/student/health-monitor/logs
ReadOnlyPaths=/home/student/health-monitor/api
```

to:
```
User=devops
Group=devops
WorkingDirectory=/home/devops/health-monitor/api
ExecStart=/usr/bin/python3 /home/devops/health-monitor/api/metrics_api.py
ReadWritePaths=/home/devops/health-monitor/logs
ReadOnlyPaths=/home/devops/health-monitor/api
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`.

### Step 6.3 — Verify python3 path matches what's in the service file

```bash
which python3
```

Expected: `/usr/bin/python3`

If it shows a different path (e.g., `/usr/local/bin/python3`), update
the `ExecStart=` line in the service file to match.

### Step 6.4 — Reload systemd, enable, and start the service

```bash
# Tell systemd to re-read all unit files
sudo systemctl daemon-reload

# Enable the service to start at boot
sudo systemctl enable syswatch-api

# Start it now
sudo systemctl start syswatch-api
```

### Step 6.5 — Check the service status

```bash
sudo systemctl status syswatch-api
```

Expected output:
```
● syswatch-api.service — SysWatch Metrics API
     Loaded: loaded (/etc/systemd/system/syswatch-api.service; enabled)
     Active: active (running) since ...
```

The key word is `active (running)`. If it says `failed`, see Section 12.

### Step 6.6 — Confirm it is listening on port 5050

```bash
ss -tlnp | grep 5050
```

Expected output:
```
LISTEN  0  5  127.0.0.1:5050  0.0.0.0:*  users:(("python3",...))
```

> Note: it shows `127.0.0.1:5050` — NOT `0.0.0.0:5050`.
> This confirms it is bound to localhost only.

### Step 6.7 — View live logs from the service

```bash
sudo journalctl -u syswatch-api -f
```

Press `Ctrl+C` to stop watching. You should see HTTP request logs
appear every 2–3 seconds once the dashboard is connected.

---

## 7. Configure the Firewall (Optional but Recommended)

Since the API binds to 127.0.0.1, it is already not accessible from
the network at the OS level. However, adding a firewall rule provides
an extra layer of defence in case the bind address is ever changed.

```bash
# Block all external access to port 5050
# (the API is already on 127.0.0.1 but this adds defence in depth)
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source NOT address="127.0.0.1" port protocol="tcp" port="5050" reject'
sudo firewall-cmd --reload

# Verify the rule was added
sudo firewall-cmd --list-rich-rules
```

You should see the rule listed.

---

## 8. Open the Dashboard in Firefox

### Step 8.1 — Open the HTML file in Firefox

```bash
firefox ~/health-monitor/reports/report.html
```

Or navigate via file manager:
```
/home/<your-username>/health-monitor/reports/report.html
```
Double-click the file to open it.

### Step 8.2 — You will see the API Key login screen

The page shows a dark login form with:
- The SysWatch logo
- An API key input field
- A Connect button

This screen only appears when the dashboard does not have a key stored.
Once connected, it will not appear again for the rest of the browser session.

---

## 9. Connect and Verify Live Data

### Step 9.1 — Retrieve your API key

In your terminal:
```bash
cat ~/health-monitor/api/api.key
```

Copy the full key string (it is 64 characters long).

### Step 9.2 — Paste the key into the dashboard

Click inside the API Key field in the browser and paste the key.
Press `Enter` or click **Connect to Backend →**.

The dashboard will test the connection. You should see:
- The login screen disappears
- The main dashboard loads with real data
- The top-right corner shows: **LIVE — 127.0.0.1:5050** in green

### Step 9.3 — Verify the data is real

Check these items to confirm real data is being shown:

| Element | How to verify |
|---------|--------------|
| CPU % card | Should match `top` or `htop` output |
| Memory card | Should match `free -m` output |
| Disk % | Should match `df -h /` output |
| Hostname | Should show your actual RHEL hostname |
| Kernel | Should show your actual kernel version |
| Process table | You should see real processes like sshd, systemd, crond |
| Core breakdown | Number of cores should match `nproc` output |

### Step 9.4 — Cross-check CPU reading

In a terminal:
```bash
# Watch CPU usage
watch -n1 "top -bn1 | grep 'Cpu(s)'"
```

The dashboard CPU card should change in sync with this output.

### Step 9.5 — Cross-check memory reading

```bash
free -m
```

The dashboard Memory card should show matching values for
Used MB and Total MB.

### Step 9.6 — Cross-check disk reading

```bash
df -h /
```

The dashboard Disk card should show the same percentage.

### Step 9.7 — Test the process table with a real load spike

```bash
# Generate temporary CPU load (runs for 30 seconds)
stress-ng --cpu 2 --timeout 30s &
```

If `stress-ng` is not installed:
```bash
sudo dnf install -y stress-ng
stress-ng --cpu 2 --timeout 30s &
```

Within 3 seconds, you should see `stress-ng` appear at the top of the
CPU % column in the process table, and possibly trigger a danger alert.

### Step 9.8 — Test the logs display

Run your health monitor script to generate log entries:

```bash
cd ~/health-monitor
./monitor.sh
./monitor.sh
./monitor.sh
```

Wait 5 seconds, then check the **System Log** panel at the bottom of
the dashboard. You should see the new entries appear automatically.

---

## 10. Customise Thresholds in the Dashboard

### CPU / Memory / Disk thresholds

Open `report.html` in a text editor:

```bash
nano ~/health-monitor/reports/report.html
```

Find this block near the top of the `<script>` section:

```javascript
const CFG = {
  API_URL:          'http://127.0.0.1:5050',
  CPU_THRESHOLD:    80,    // dashboard card turns red above this
  MEM_THRESHOLD:    75,    // dashboard card turns red above this
  DISK_THRESHOLD:   90,    // dashboard card turns red above this
  DANGER_CPU_PROC:  70,    // process table row turns red above this
  DANGER_MEM_MB:    500,   // process using more than 500 MB triggers danger alert
  DANGER_DISK_MB:   1000,  // process cumulative I/O above 1 GB triggers danger alert
  ...
};
```

Change the numbers to match your `config.cfg` thresholds.

For example, if your `config.cfg` has:
```
CPU_THRESHOLD=70
MEMORY_THRESHOLD=60
DISK_THRESHOLD=85
```

Update the CFG block to:
```javascript
CPU_THRESHOLD:    70,
MEM_THRESHOLD:    60,
DISK_THRESHOLD:   85,
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`, then refresh the browser.

---

## 11. Integrate with Your Existing Cron Jobs

Your cron jobs from the original project already write to `health.log`.
The dashboard reads this file via the `/api/logs` endpoint.

No changes to your cron jobs are needed. The existing setup is:
```cron
*/5 * * * * /home/student/health-monitor/monitor.sh >> /home/student/health-monitor/logs/health.log 2>&1
0 8 * * * /home/student/health-monitor/monitor.sh --report >> /home/student/health-monitor/logs/health.log 2>&1
```

The dashboard polls logs every 5 seconds, so new log entries appear
within 5 seconds of being written by the cron job.

### To also start the API automatically at boot via cron (alternative to systemd)

If you prefer not to use systemd, add this to your crontab:

```bash
crontab -e
```

Add this line:
```cron
@reboot /usr/bin/python3 /home/student/health-monitor/api/metrics_api.py >> /home/student/health-monitor/logs/api.log 2>&1 &
```

> However, the systemd service method (Section 6) is more reliable and
> is the recommended approach.

---

## 12. Troubleshooting

### Problem: "Cannot reach API at 127.0.0.1:5050" on the key screen

**Step 1** — Check if the service is running:
```bash
sudo systemctl status syswatch-api
```

**Step 2** — If it shows `failed`, view the error:
```bash
sudo journalctl -u syswatch-api --no-pager -n 30
```

**Step 3** — Common causes and fixes:

| Error in journal | Fix |
|-----------------|-----|
| `ModuleNotFoundError: No module named 'flask'` | Run Step 1.3 again |
| `ModuleNotFoundError: No module named 'psutil'` | Run Step 1.3 again |
| `Permission denied: api.key` | Run `chmod 600 ~/health-monitor/api/api.key` |
| `FileNotFoundError: api.key` | Run Step 3.1 again |
| `Address already in use` | Another process is on port 5050: `sudo ss -tlnp \| grep 5050` |
| `No such file or directory: python3` | Fix ExecStart= path: `which python3` |

**Step 4** — Start the API manually to see the error directly:
```bash
cd ~/health-monitor/api
python3 metrics_api.py
```

Read the error output and fix accordingly.

---

### Problem: Wrong API key error in the browser

The browser shows: *Wrong API key — check api.key file*

**Check 1** — View the key:
```bash
cat ~/health-monitor/api/api.key
```

**Check 2** — Make sure you copied the entire 64-character key.
Leading or trailing spaces cause auth failures. In the browser,
click inside the key field, press `Ctrl+A` to select all, then paste again.

**Check 3** — Verify the key file has no newline at the end:
```bash
xxd ~/health-monitor/api/api.key | tail -2
```
The last bytes should be `0a` (one newline). If there are multiple,
regenerate: `python3 -c "import secrets; print(secrets.token_hex(32))" > ~/health-monitor/api/api.key`

---

### Problem: Dashboard connects but shows — (dashes) for all values

The API is reachable but not returning data.

```bash
# Test the metrics endpoint manually
MY_KEY=$(cat ~/health-monitor/api/api.key)
curl -v -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/metrics
```

Look for the HTTP status code. If you see `500 Internal Server Error`:
```bash
sudo journalctl -u syswatch-api -n 20
```

The most common cause is a psutil version incompatibility:
```bash
pip3 show psutil
# Should be 5.9+ for RHEL 10
pip3 install --upgrade psutil --break-system-packages
sudo systemctl restart syswatch-api
```

---

### Problem: Process table shows no processes / very few

The API may not have permission to read other users' processes.

Run the API as root temporarily to test:
```bash
sudo python3 ~/health-monitor/api/metrics_api.py
```

If you then see all processes, you need to either:
- Run the systemd service as root (change `User=root` in service file), or
- Accept that only your user's processes are visible (recommended for security)

---

### Problem: systemd service starts but stops immediately

```bash
sudo journalctl -u syswatch-api --no-pager -n 50
```

Look for the actual Python traceback. Fix the error shown, then:
```bash
sudo systemctl restart syswatch-api
sudo systemctl status syswatch-api
```

---

### Problem: Logs panel shows "No entries yet"

The dashboard reads from `health.log`. Generate entries:
```bash
cd ~/health-monitor
./monitor.sh
./monitor.sh
./monitor.sh
```

Then wait 5 seconds — the log panel auto-refreshes.

Also verify the log file path:
```bash
ls -lh ~/health-monitor/logs/health.log
wc -l ~/health-monitor/logs/health.log
```

---

### Problem: Danger alerts never appear

The alert thresholds in the dashboard CFG block may be set too high
for your system's typical load. Lower them temporarily to test:

In `report.html`, change:
```javascript
DANGER_CPU_PROC:  70,
DANGER_MEM_MB:    500,
```
to:
```javascript
DANGER_CPU_PROC:  5,    // any process using >5% CPU triggers alert
DANGER_MEM_MB:    50,   // any process using >50 MB triggers alert
```

Refresh the browser. You should now see many alerts (to prove the system
works), then raise the thresholds back to sensible values.

---

### Problem: Firewall blocks the API even from localhost

On RHEL 10, firewalld sometimes applies rules to loopback traffic.

Allow loopback traffic explicitly:
```bash
sudo firewall-cmd --permanent --add-interface=lo --zone=trusted
sudo firewall-cmd --reload
```

Then test again:
```bash
curl http://127.0.0.1:5050/api/health
```

---

## FINAL VERIFICATION CHECKLIST

Run these commands to confirm everything is working end-to-end:

```bash
# 1. API service is running
sudo systemctl is-active syswatch-api

# 2. API is listening on localhost only
ss -tlnp | grep 5050

# 3. Liveness check
curl -s http://127.0.0.1:5050/api/health

# 4. Auth check (should return 401)
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:5050/api/metrics

# 5. Authenticated call returns JSON
MY_KEY=$(cat ~/health-monitor/api/api.key)
curl -s -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/metrics | python3 -m json.tool | head -10

# 6. Process list returns data
curl -s -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/processes | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"count\"]} processes returned')"

# 7. Log file has entries
wc -l ~/health-monitor/logs/health.log

# 8. Log endpoint returns entries
curl -s -H "X-API-Key: $MY_KEY" http://127.0.0.1:5050/api/logs | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"count\"]} log entries returned')"

# 9. Dashboard file is in place
ls -lh ~/health-monitor/reports/report.html

# 10. Service is enabled at boot
sudo systemctl is-enabled syswatch-api
```

All 10 checks should return meaningful output with no errors.
Open the dashboard in Firefox and confirm real data is flowing.

---

*End of Guide — SysWatch Real Data Integration — RHEL 10*
