# Bonus Challenges — Automated Server Health Monitor
## Complete Step-by-Step Guide for RHEL 10
### Email Alert · Slack Webhook · Multi-Server SSH · Historical ASCII Graph

---

> **How this guide is organised:**
> Each bonus challenge is fully self-contained. You can implement them in any order. Every challenge builds on top of your existing `~/health-monitor/` project from the main guide. Read each section completely before typing a single command.

---

## TABLE OF CONTENTS

1. [Before You Begin — Prerequisites](#before-you-begin)
2. [Bonus 1 — Email Alert with mail/sendmail](#bonus-1-email-alert)
3. [Bonus 2 — Slack Webhook Notification](#bonus-2-slack-webhook)
4. [Bonus 3 — Multi-Server SSH Remote Checks](#bonus-3-multi-server-ssh)
5. [Bonus 4 — Historical ASCII Trend Chart with awk](#bonus-4-ascii-trend-chart)
6. [Integrating All Bonuses into monitor.sh](#integrating-all-bonuses)
7. [Testing All Four Bonuses Together](#testing-all-four-bonuses)
8. [Final File Checklist](#final-file-checklist)
9. [Troubleshooting](#troubleshooting)

---

## Before You Begin

### What You Need

Your original `~/health-monitor/` project must be fully working before starting any bonus challenge. Confirm this now:

```bash
cd ~/health-monitor
./monitor.sh
```

You should see PASS/ALERT results printed to the terminal and an HTML report generated in `reports/report.html`. The file `logs/health.log` must have at least 10 entries.

If anything above is not working, **fix the main project first** before attempting these bonus challenges.

### Check Your Current Folder Structure

```bash
find ~/health-monitor -type f | sort
```

Expected output (at minimum):

```
/home/<your-username>/health-monitor/checks/cpu.sh
/home/<your-username>/health-monitor/checks/disk.sh
/home/<your-username>/health-monitor/checks/memory.sh
/home/<your-username>/health-monitor/checks/services.sh
/home/<your-username>/health-monitor/config.cfg
/home/<your-username>/health-monitor/logs/health.log
/home/<your-username>/health-monitor/monitor.sh
/home/<your-username>/health-monitor/reports/report.html
```

If your structure looks correct, proceed to Bonus 1.

---

## Bonus 1 — Email Alert

### What This Does

When any health check returns **ALERT** status (CPU, Memory, Disk, or a service is down), the system automatically sends an email to an address you configure. The email contains the exact check that failed, the current metric value, and the threshold it exceeded.

### How It Works

The script:
1. Runs all four checks
2. Reads the most recent log entries and searches for lines containing `ALERT`
3. If any ALERT lines are found, it formats an email body and calls `mail` (or `sendmail`) to deliver it

### Step 1.1 — Install the mail Utilities

On RHEL 10, the `mail` command comes from the `s-nail` or `mailx` package. Install it:

```bash
sudo dnf install -y s-nail
```

Verify it installed correctly:

```bash
mail --version
```

You should see version output like `s-nail v14.x.x`. If not, try:

```bash
sudo dnf install -y mailx
```

### Step 1.2 — Understand How Email Sending Works on a Local RHEL Server

On most lab/classroom RHEL systems, there is no connection to an external email provider. The `mail` command will deliver email to the **local system mailbox** of the user you specify. This means:

- Emails sent to `student@localhost` are delivered to `/var/spool/mail/student` on the same machine
- You read them by typing `mail` in the terminal — not with Gmail or Outlook
- This is completely normal for testing and lab environments

> **If your RHEL system has a real SMTP server or is connected to a relay**, you can send to a real external email address (like `yourname@gmail.com`). Ask your instructor if external email is configured.

### Step 1.3 — Configure Email Settings in config.cfg

Open `config.cfg` and add the email settings at the bottom:

```bash
nano ~/health-monitor/config.cfg
```

Add these lines at the **end** of the file (after the existing SERVICES line):

```bash
# ============================================================
# Email Alert Settings (Bonus Challenge 1)
# ============================================================

# Set to "true" to enable email alerts, "false" to disable
EMAIL_ALERTS_ENABLED=true

# Email address to send alerts to
# Use user@localhost for local delivery on a lab system
# Use a real address if your server has SMTP configured
ALERT_EMAIL="student@localhost"

# The "From" address shown in the email
EMAIL_FROM="healthmonitor@localhost"

# Subject prefix for alert emails
EMAIL_SUBJECT_PREFIX="[SERVER ALERT]"
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

Verify the additions:

```bash
tail -15 ~/health-monitor/config.cfg
```

### Step 1.4 — Create the Email Alert Script

```bash
nano ~/health-monitor/checks/email_alert.sh
```

Type (or paste) the following — read each comment carefully to understand what every section does:

```bash
#!/bin/bash
# ============================================================
# email_alert.sh — Email Alert Script
# Reads the most recent health.log entries looking for ALERT
# If any ALERT is found, sends an email using 'mail' command
# Called by monitor.sh after all checks have run
# ============================================================

# --- Step 1: Find the project root (one level above checks/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Step 2: Source the configuration file to load all settings
source "$PROJECT_DIR/config.cfg"

# --- Step 3: Check if email alerts are enabled in config
if [ "$EMAIL_ALERTS_ENABLED" != "true" ]; then
    echo "[EMAIL] Email alerts are disabled in config.cfg. Skipping."
    exit 0
fi

# --- Step 4: Define paths
LOG_FILE="$PROJECT_DIR/logs/health.log"

# --- Step 5: Collect ALL alert lines from the most recent run
# Strategy: get the last 20 lines of the log (covers one full run)
# then filter only lines containing "ALERT"
RECENT_LOGS=$(tail -20 "$LOG_FILE")
ALERT_LINES=$(echo "$RECENT_LOGS" | grep "ALERT")

# --- Step 6: Only send an email if at least one ALERT was found
if [ -z "$ALERT_LINES" ]; then
    echo "[EMAIL] No ALERT conditions detected. No email sent."
    exit 0
fi

# --- Step 7: Build the email body
# We use a HERE document (<<EOF) to create multi-line text
HOSTNAME=$(hostname)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

EMAIL_BODY=$(cat <<EOF
SERVER HEALTH ALERT
===================
Host:      $HOSTNAME
Timestamp: $TIMESTAMP
-------------------------------------------
The following health checks have FAILED:

$ALERT_LINES
-------------------------------------------
Full last 20 log entries:

$RECENT_LOGS
-------------------------------------------
This message was sent automatically by:
~/health-monitor/checks/email_alert.sh
EOF
)

# --- Step 8: Send the email using the 'mail' command
# -s sets the subject line
# -r sets the From address
# We pipe the body text into 'mail' via stdin (the <<< operator)
echo "$EMAIL_BODY" | mail \
    -s "${EMAIL_SUBJECT_PREFIX} ${HOSTNAME} — $(echo "$ALERT_LINES" | wc -l) alert(s) detected" \
    -r "$EMAIL_FROM" \
    "$ALERT_EMAIL"

# --- Step 9: Check if the mail command succeeded
if [ $? -eq 0 ]; then
    echo "[EMAIL] Alert email sent to: $ALERT_EMAIL"
else
    echo "[EMAIL] ERROR: Failed to send alert email. Check that 'mail' is installed."
    echo "[EMAIL] Run: sudo dnf install -y s-nail"
fi
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 1.5 — Make the Script Executable

```bash
chmod +x ~/health-monitor/checks/email_alert.sh
```

Verify:

```bash
ls -la ~/health-monitor/checks/email_alert.sh
```

You should see `-rwxrwxr-x` (the `x` bits are set).

### Step 1.6 — Test the Email Alert Script Directly

First, generate at least one ALERT entry in your log. The easiest way is to temporarily lower a threshold so a PASS becomes an ALERT:

```bash
# Open config.cfg and change CPU_THRESHOLD to 1 (so any CPU usage triggers ALERT)
nano ~/health-monitor/config.cfg
```

Change `CPU_THRESHOLD=80` to `CPU_THRESHOLD=1`, save and exit.

Now run the CPU check:

```bash
bash ~/health-monitor/checks/cpu.sh
```

You should see `[CPU] Status: ALERT`. Now test the email script:

```bash
bash ~/health-monitor/checks/email_alert.sh
```

Expected output:

```
[EMAIL] Alert email sent to: student@localhost
```

### Step 1.7 — Read the Alert Email

```bash
mail
```

You will enter the `mail` interactive reader. You should see a message at the top like:

```
"/var/spool/mail/student": 1 message 1 new
>N  1 healthmonitor@lo  Sat Aug 15 10:30  SERVER ALERT hostname — 1 alert(s)
```

Press `1` then `Enter` to read message 1. Press `q` then `Enter` to quit.

### Step 1.8 — Reset the Threshold

Don't forget to put the threshold back:

```bash
nano ~/health-monitor/config.cfg
# Change CPU_THRESHOLD=1 back to CPU_THRESHOLD=80
```

Save and exit.

---

## Bonus 2 — Slack Webhook

### What This Does

When any health check returns **ALERT** status, the system sends a formatted notification message directly to a Slack channel using `curl`. The message appears in Slack in real time.

### How It Works

Slack provides a feature called **Incoming Webhooks**. You create a webhook URL in Slack, and then any application can send a `curl` POST request to that URL with a JSON payload — and it appears as a message in your channel. No login, no API keys, just one URL.

### Step 2.1 — Create a Slack Incoming Webhook

> **You need a Slack workspace to do this.** If you do not have one, create a free workspace at https://slack.com/get-started.

Follow these steps exactly:

1. Open a web browser and go to: `https://api.slack.com/apps`
2. Click **"Create New App"**
3. Select **"From scratch"**
4. Enter an App Name: `ServerHealthMonitor`
5. Choose your Slack workspace from the dropdown
6. Click **"Create App"**
7. In the left sidebar, click **"Incoming Webhooks"**
8. Toggle **"Activate Incoming Webhooks"** to **ON**
9. Scroll down and click **"Add New Webhook to Workspace"**
10. Select the Slack channel where you want alerts to appear (for example: `#general` or create a new channel called `#server-alerts`)
11. Click **"Allow"**
12. You will be returned to the webhooks page. Copy the **Webhook URL** — it looks like:

```
PASTE_YOUR_SLACK_WEBHOOK_URL_HERE
```

> **Keep this URL private.** Anyone with this URL can post to your Slack channel.

### Step 2.2 — Add the Webhook URL to config.cfg

```bash
nano ~/health-monitor/config.cfg
```

Add these lines at the **end** of the file:

```bash
# ============================================================
# Slack Webhook Settings (Bonus Challenge 2)
# ============================================================

# Set to "true" to enable Slack alerts, "false" to disable
SLACK_ALERTS_ENABLED=true

# Paste your full Slack Incoming Webhook URL here
# Replace the example URL below with your real URL
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/REPLACE/WITH/YOUR_REAL_URL"
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

> **Important:** Replace `https://hooks.slack.com/services/REPLACE/WITH/YOUR_REAL_URL` with the actual URL you copied from Step 2.1.

### Step 2.3 — Verify curl Is Available

```bash
curl --version
```

You should see output beginning with `curl 7.x.x` or `curl 8.x.x`. If curl is missing:

```bash
sudo dnf install -y curl
```

### Step 2.4 — Create the Slack Alert Script

```bash
nano ~/health-monitor/checks/slack_alert.sh
```

Type (or paste) the following:

```bash
#!/bin/bash
# ============================================================
# slack_alert.sh — Slack Webhook Notification Script
# Reads the most recent health.log entries looking for ALERT
# If any ALERT is found, sends a formatted message to Slack
# Uses curl to POST a JSON payload to the Slack webhook URL
# Called by monitor.sh after all checks have run
# ============================================================

# --- Step 1: Find the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Step 2: Source the configuration file
source "$PROJECT_DIR/config.cfg"

# --- Step 3: Check if Slack alerts are enabled
if [ "$SLACK_ALERTS_ENABLED" != "true" ]; then
    echo "[SLACK] Slack alerts are disabled in config.cfg. Skipping."
    exit 0
fi

# --- Step 4: Check that a real webhook URL has been configured
if [[ "$SLACK_WEBHOOK_URL" == *"REPLACE"* ]]; then
    echo "[SLACK] ERROR: You have not set your Slack webhook URL in config.cfg."
    echo "[SLACK] Edit config.cfg and replace the placeholder URL with your real webhook URL."
    exit 1
fi

# --- Step 5: Define paths and collect data
LOG_FILE="$PROJECT_DIR/logs/health.log"
RECENT_LOGS=$(tail -20 "$LOG_FILE")
ALERT_LINES=$(echo "$RECENT_LOGS" | grep "ALERT")

# --- Step 6: Only send if there are ALERT conditions
if [ -z "$ALERT_LINES" ]; then
    echo "[SLACK] No ALERT conditions detected. No Slack message sent."
    exit 0
fi

# --- Step 7: Build the Slack message payload
# Slack uses JSON with a "text" field. We use \n for newlines inside JSON.
# The 'jq' tool can build JSON safely, but since jq may not be installed
# we build the JSON manually and escape special characters.

HOSTNAME=$(hostname)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ALERT_COUNT=$(echo "$ALERT_LINES" | wc -l)

# Escape the alert lines for safe inclusion in JSON:
# Replace double quotes with escaped quotes, replace newlines with \n
ALERT_ESCAPED=$(echo "$ALERT_LINES" | sed 's/"/\\"/g' | awk '{printf "%s\\n", $0}')

# Build the JSON payload
# We use a Slack "attachment" to get the red colour bar on the left side
JSON_PAYLOAD=$(cat <<EOF
{
  "attachments": [
    {
      "color": "#FF0000",
      "title": ":rotating_light: SERVER HEALTH ALERT — ${HOSTNAME}",
      "text": "Timestamp: ${TIMESTAMP}\nHost: ${HOSTNAME}\nAlerts detected: ${ALERT_COUNT}\n\n*Failed checks:*\n${ALERT_ESCAPED}",
      "footer": "health-monitor | RHEL 10",
      "mrkdwn_in": ["text"]
    }
  ]
}
EOF
)

# --- Step 8: Send the payload to Slack using curl
# -s = silent (no progress bar)
# -o /tmp/slack_response = save response to temp file
# -w "%{http_code}" = print the HTTP status code
# -X POST = HTTP POST method
# -H "Content-type: application/json" = tell Slack we are sending JSON
# -d = the JSON data payload

HTTP_CODE=$(curl -s \
    -o /tmp/slack_response.txt \
    -w "%{http_code}" \
    -X POST \
    -H "Content-type: application/json" \
    -d "$JSON_PAYLOAD" \
    "$SLACK_WEBHOOK_URL")

# --- Step 9: Check the response
SLACK_RESPONSE=$(cat /tmp/slack_response.txt 2>/dev/null)

if [ "$HTTP_CODE" = "200" ] && [ "$SLACK_RESPONSE" = "ok" ]; then
    echo "[SLACK] Alert message sent successfully to Slack (HTTP $HTTP_CODE)."
else
    echo "[SLACK] ERROR: Slack returned HTTP $HTTP_CODE | Response: $SLACK_RESPONSE"
    echo "[SLACK] Check your webhook URL in config.cfg is correct."
fi

# Clean up temp file
rm -f /tmp/slack_response.txt
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 2.5 — Make the Script Executable

```bash
chmod +x ~/health-monitor/checks/slack_alert.sh
```

### Step 2.6 — Test the Slack Alert

Temporarily lower the CPU threshold to force an ALERT (same method as Bonus 1):

```bash
nano ~/health-monitor/config.cfg
# Change CPU_THRESHOLD=80 to CPU_THRESHOLD=1
```

Run the CPU check and then the Slack alert script:

```bash
bash ~/health-monitor/checks/cpu.sh
bash ~/health-monitor/checks/slack_alert.sh
```

Expected terminal output:

```
[CPU]   Status: ALERT | Usage: 8% | Threshold: 1%
[SLACK] Alert message sent successfully to Slack (HTTP 200).
```

Check your Slack channel — you should see a red-highlighted alert message appear within a few seconds.

### Step 2.7 — Reset the Threshold

```bash
nano ~/health-monitor/config.cfg
# Change CPU_THRESHOLD=1 back to CPU_THRESHOLD=80
```

---

## Bonus 3 — Multi-Server SSH Remote Checks

### What This Does

The system SSHes into one or more remote servers and runs all four health checks (CPU, Memory, Disk, Services) remotely. The results are pulled back to your local machine, printed to the terminal, and logged in your local `health.log` — all without manually logging into each remote server.

### How It Works

The script:
1. Reads a list of remote server addresses from a new file called `remote_servers.cfg`
2. For each server, uses `ssh` to execute the check scripts remotely
3. Captures the output and writes it to your local log file with a `[REMOTE]` tag

### Step 3.1 — Understand SSH Key Authentication

SSH normally asks for a password every time. For automated scripts (and cron jobs), this is not acceptable — a password prompt would cause the script to hang. The solution is **SSH key authentication**:

- You generate a key pair (a private key kept on your machine, and a public key)
- You copy the public key to the remote server
- After that, SSH never asks for a password — it authenticates automatically

### Step 3.2 — Set Up a Remote Test Server

> **If you do not have a second physical server**, you can test this by SSH-ing back to `localhost` (your own machine). This is a valid technique and is used throughout this guide. The script works identically whether the target is localhost or a real remote host.

**To use localhost as your test remote server:**

All commands below that say "remote server" can use `127.0.0.1` or `localhost` as the server address.

**To use a real remote RHEL server:**

You need its IP address. Ask your instructor or get it by running this command on the remote machine:

```bash
ip a | grep "inet " | grep -v "127.0.0.1"
```

The address will look like `192.168.x.x` or `10.x.x.x`.

### Step 3.3 — Generate an SSH Key Pair (If You Don't Have One Already)

Check if you already have a key:

```bash
ls -la ~/.ssh/id_rsa.pub
```

If the file exists, skip to Step 3.4. If you see "No such file or directory", generate one now:

```bash
ssh-keygen -t rsa -b 4096 -C "healthmonitor@$(hostname)"
```

When prompted:
- **"Enter file in which to save the key"** — press `Enter` to accept the default (`~/.ssh/id_rsa`)
- **"Enter passphrase"** — press `Enter` for NO passphrase (required for automation)
- **"Enter same passphrase again"** — press `Enter` again

You will see output showing the key fingerprint and a randomart image. This confirms the key was created.

Verify:

```bash
ls -la ~/.ssh/
```

You should see both `id_rsa` (private key) and `id_rsa.pub` (public key).

### Step 3.4 — Copy Your Public Key to the Remote Server

Replace `<remote-user>` with the username on the remote server (usually `student` or `root`) and `<remote-ip>` with the server's IP address:

```bash
ssh-copy-id <remote-user>@<remote-ip>
```

For localhost testing:

```bash
ssh-copy-id $(whoami)@localhost
```

You will be asked for the remote user's password this **one time only**. After entering it, the key is installed and you will never need the password again for SSH.

Verify the key works by doing a test SSH login (should NOT ask for a password):

```bash
ssh <remote-user>@<remote-ip> "echo SSH_TEST_OK"
```

For localhost:

```bash
ssh $(whoami)@localhost "echo SSH_TEST_OK"
```

Expected output: `SSH_TEST_OK` with no password prompt.

> **If you see a "host authenticity" prompt** saying something like `Are you sure you want to continue connecting (yes/no)?`, type `yes` and press Enter. This only happens on first connection.

### Step 3.5 — Copy the health-monitor Project to the Remote Server

The remote checks need the same scripts to exist on the remote server. Copy the entire project:

```bash
scp -r ~/health-monitor <remote-user>@<remote-ip>:~/
```

For localhost testing, skip this step — the files already exist.

Verify the copy worked:

```bash
ssh <remote-user>@<remote-ip> "ls ~/health-monitor/checks/"
```

Expected output:

```
cpu.sh  disk.sh  memory.sh  services.sh
```

### Step 3.6 — Create the Remote Servers Configuration File

```bash
nano ~/health-monitor/remote_servers.cfg
```

Add one server per line. The format is: `username@hostname_or_ip`

```bash
# ============================================================
# remote_servers.cfg — Remote Server List
# health-monitor Bonus Challenge 3
#
# Format: one server per line as user@host
# Lines starting with # are comments and are ignored
# ============================================================

# Example: your localhost (for testing)
student@localhost

# Example: a real remote server (replace with real values)
# student@192.168.1.50
# admin@10.0.0.25
```

Uncomment and edit the lines as needed. For a localhost-only test, leave only `student@localhost` (replace `student` with your actual username):

```bash
# Get your actual username
whoami
```

Use that username. Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 3.7 — Create the Remote Check Script

```bash
nano ~/health-monitor/checks/remote_check.sh
```

Type (or paste):

```bash
#!/bin/bash
# ============================================================
# remote_check.sh — Multi-Server SSH Remote Health Check
# Reads server list from remote_servers.cfg
# SSHes to each server, runs all checks, logs results locally
# ============================================================

# --- Step 1: Find the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Step 2: Source local configuration
source "$PROJECT_DIR/config.cfg"

# --- Step 3: Define paths
LOG_FILE="$PROJECT_DIR/logs/health.log"
REMOTE_SERVERS_FILE="$PROJECT_DIR/remote_servers.cfg"
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Step 4: Check that the remote servers file exists
if [ ! -f "$REMOTE_SERVERS_FILE" ]; then
    echo "[REMOTE] ERROR: $REMOTE_SERVERS_FILE not found."
    echo "[REMOTE] Create this file with one user@host entry per line."
    exit 1
fi

echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${BOLD}${CYAN}   REMOTE SERVER HEALTH CHECKS${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"

# --- Step 5: Loop through each server in the config file
# Skip blank lines and comment lines (those starting with #)
while IFS= read -r SERVER || [[ -n "$SERVER" ]]; do

    # Skip empty lines
    [ -z "$SERVER" ] && continue

    # Skip comment lines (lines that start with #)
    [[ "$SERVER" =~ ^# ]] && continue

    echo ""
    echo -e "${CYAN}--- Checking remote server: $SERVER ---${NC}"

    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    # --- Step 6: Test SSH connectivity before running checks
    # ConnectTimeout=5 means give up after 5 seconds if unreachable
    # -o StrictHostKeyChecking=no prevents the interactive "yes/no" prompt
    # -o BatchMode=yes prevents any interactive prompts (required for automation)
    SSH_TEST=$(ssh -o ConnectTimeout=5 \
                   -o StrictHostKeyChecking=no \
                   -o BatchMode=yes \
                   "$SERVER" "echo CONNECTED" 2>&1)

    if [ "$SSH_TEST" != "CONNECTED" ]; then
        echo -e "${RED}[REMOTE] ALERT: Cannot connect to $SERVER via SSH${NC}"
        echo "$TIMESTAMP [REMOTE] $SERVER | Status: ALERT | Reason: SSH connection failed" >> "$LOG_FILE"
        continue  # Skip to the next server
    fi

    echo -e "${GREEN}[REMOTE] SSH connection to $SERVER: OK${NC}"

    # --- Step 7: Run CPU check remotely
    # We send the entire check script content to the remote shell via stdin
    # This avoids needing to know the exact remote path to the scripts
    CPU_RESULT=$(ssh -o ConnectTimeout=10 \
                     -o StrictHostKeyChecking=no \
                     -o BatchMode=yes \
                     "$SERVER" "bash ~/health-monitor/checks/cpu.sh 2>/dev/null" 2>&1)

    # Strip ANSI colour codes from remote output for clean logging
    CPU_CLEAN=$(echo "$CPU_RESULT" | sed 's/\x1b\[[0-9;]*m//g')
    echo "[REMOTE] $SERVER | $CPU_CLEAN"
    echo "$TIMESTAMP [REMOTE] $SERVER | $CPU_CLEAN" >> "$LOG_FILE"

    # --- Step 8: Run Memory check remotely
    MEM_RESULT=$(ssh -o ConnectTimeout=10 \
                     -o StrictHostKeyChecking=no \
                     -o BatchMode=yes \
                     "$SERVER" "bash ~/health-monitor/checks/memory.sh 2>/dev/null" 2>&1)
    MEM_CLEAN=$(echo "$MEM_RESULT" | sed 's/\x1b\[[0-9;]*m//g')
    echo "[REMOTE] $SERVER | $MEM_CLEAN"
    echo "$TIMESTAMP [REMOTE] $SERVER | $MEM_CLEAN" >> "$LOG_FILE"

    # --- Step 9: Run Disk check remotely
    DISK_RESULT=$(ssh -o ConnectTimeout=10 \
                      -o StrictHostKeyChecking=no \
                      -o BatchMode=yes \
                      "$SERVER" "bash ~/health-monitor/checks/disk.sh 2>/dev/null" 2>&1)
    DISK_CLEAN=$(echo "$DISK_RESULT" | sed 's/\x1b\[[0-9;]*m//g')
    echo "[REMOTE] $SERVER | $DISK_CLEAN"
    echo "$TIMESTAMP [REMOTE] $SERVER | $DISK_CLEAN" >> "$LOG_FILE"

    # --- Step 10: Run Services check remotely
    SVC_RESULT=$(ssh -o ConnectTimeout=10 \
                     -o StrictHostKeyChecking=no \
                     -o BatchMode=yes \
                     "$SERVER" "bash ~/health-monitor/checks/services.sh 2>/dev/null" 2>&1)
    # Services check outputs multiple lines — process each one
    while IFS= read -r SVC_LINE; do
        SVC_CLEAN=$(echo "$SVC_LINE" | sed 's/\x1b\[[0-9;]*m//g')
        [ -z "$SVC_CLEAN" ] && continue
        echo "[REMOTE] $SERVER | $SVC_CLEAN"
        echo "$TIMESTAMP [REMOTE] $SERVER | $SVC_CLEAN" >> "$LOG_FILE"
    done <<< "$SVC_RESULT"

    echo -e "${GREEN}[REMOTE] All checks complete for: $SERVER${NC}"

done < "$REMOTE_SERVERS_FILE"

echo ""
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${GREEN}  Remote check run complete.${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 3.8 — Make the Script Executable

```bash
chmod +x ~/health-monitor/checks/remote_check.sh
```

### Step 3.9 — Test the Remote Check Script

```bash
cd ~/health-monitor
bash checks/remote_check.sh
```

For localhost, expected output will look like:

```
============================================================
   REMOTE SERVER HEALTH CHECKS
============================================================

--- Checking remote server: student@localhost ---
[REMOTE] SSH connection to student@localhost: OK
[REMOTE] student@localhost | [CPU]    Status: PASS | Usage: 12% | Threshold: 80%
[REMOTE] student@localhost | [MEMORY] Status: PASS | Usage: 45% | Threshold: 75%
[REMOTE] student@localhost | [DISK]   Status: PASS | Usage: 22% | Threshold: 90%
[REMOTE] student@localhost | [SERVICE] sshd  | Status: PASS | State: active
[REMOTE] student@localhost | [SERVICE] crond | Status: PASS | State: active
[REMOTE] student@localhost | [SERVICE] nginx | Status: PASS | State: active

[REMOTE] All checks complete for: student@localhost
============================================================
  Remote check run complete.
============================================================
```

Verify the log entries were written:

```bash
grep "\[REMOTE\]" ~/health-monitor/logs/health.log
```

---

## Bonus 4 — Historical ASCII Trend Chart

### What This Does

Parses `health.log` and generates a visual ASCII bar chart directly in the terminal showing the trend of CPU, Memory, and Disk usage over the last 10 recorded check runs. This lets you see at a glance whether resource usage is climbing (a warning sign) or staying stable.

### How It Works

The script uses `awk` to:
1. Read `health.log` line by line
2. Extract numeric usage values from CPU, Memory, and Disk log lines
3. Store the last 10 values for each metric
4. Draw an ASCII bar chart using `#` characters scaled to the value

### Step 4.1 — Ensure You Have Enough Log Data

The trend chart needs at least 5 log entries per metric to be meaningful. Run the monitor several times if needed:

```bash
cd ~/health-monitor
./monitor.sh
./monitor.sh
./monitor.sh
./monitor.sh
./monitor.sh
```

Check the log:

```bash
grep "\[CPU\]" ~/health-monitor/logs/health.log | wc -l
```

This should return 5 or higher. If not, run `./monitor.sh` a few more times.

### Step 4.2 — Create the Trend Chart Script

```bash
nano ~/health-monitor/checks/trend_chart.sh
```

Type (or paste) the following. This script is the most complex of the four bonuses — every section is explained in detail:

```bash
#!/bin/bash
# ============================================================
# trend_chart.sh — Historical ASCII Trend Chart Generator
# Parses health.log using awk to extract metric history
# Renders a bar chart using # characters scaled to usage %
# Shows last 10 readings for CPU, Memory, and Disk
# ============================================================

# --- Step 1: Find the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Step 2: Define the log file path
LOG_FILE="$PROJECT_DIR/logs/health.log"

# Colour codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Step 3: Check that the log file exists and has data
if [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; then
    echo "[TREND] ERROR: Log file is empty or does not exist."
    echo "[TREND] Run ./monitor.sh at least 5 times first to generate data."
    exit 1
fi

echo ""
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${BOLD}${CYAN}   SERVER HEALTH — HISTORICAL TREND CHART${NC}"
echo -e "${BOLD}${CYAN}   (Last 10 readings per metric from health.log)${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""

# ============================================================
# FUNCTION: draw_chart
# Arguments:
#   $1 = metric name to display (e.g., "CPU Usage")
#   $2 = log tag to search for (e.g., "[CPU]")
#   $3 = threshold value (e.g., 80)
#   $4 = bar colour code
#
# This function:
#   1. Uses grep to find all log lines matching the metric tag
#      (excludes REMOTE lines so only local checks are shown)
#   2. Uses awk to extract the "Usage: XX%" value from each line
#   3. Stores the last 10 values in an array
#   4. Prints a bar chart where each bar's length = value / 2
#      (so 100% usage = 50 # characters, fits in an 80-col terminal)
# ============================================================

draw_chart() {
    local METRIC_NAME="$1"
    local LOG_TAG="$2"
    local THRESHOLD="$3"
    local BAR_COLOUR="$4"

    echo -e "${BOLD}${YELLOW}  $METRIC_NAME  (threshold: ${THRESHOLD}%)${NC}"
    echo -e "  ${CYAN}Scale: each # = 2%  |  Max bar = 50 chars (100%)${NC}"
    echo -e "  ${CYAN}┌──────────────────────────────────────────────────────┐${NC}"

    # Use awk to:
    # 1. Read only lines containing our LOG_TAG but NOT "[REMOTE]"
    # 2. Extract the number after "Usage: "
    # 3. Keep the last 10 values in a rolling array
    # 4. Print each value with its bar
    grep "$LOG_TAG" "$LOG_FILE" | grep -v "\[REMOTE\]" | \
    awk -v tag="$LOG_TAG" -v threshold="$THRESHOLD" '
    BEGIN {
        n = 0          # counter for values found
        max_bars = 10  # how many readings to show
    }

    # For each line that contains "Usage: "
    /Usage: / {
        # Extract the number after "Usage: " and before "%"
        # split() divides the line at "Usage: " giving us the number after it
        split($0, parts, "Usage: ")
        val_str = parts[2]      # e.g., "45% | Threshold..."
        split(val_str, num, "%") # split at % to get just the number
        val = num[1] + 0         # convert to integer

        # Store value in circular array (only keep last max_bars values)
        values[n % max_bars] = val
        n++
    }

    END {
        # Determine start index for the last max_bars values
        total = (n < max_bars) ? n : max_bars
        start = (n > max_bars) ? (n % max_bars) : 0

        # Loop through the stored values in order
        for (i = 0; i < total; i++) {
            idx = (start + i) % max_bars
            v = values[idx]
            bar_len = int(v / 2)   # scale: 100% = 50 chars

            # Build the bar string using printf
            bar = ""
            for (j = 0; j < bar_len; j++) bar = bar "#"

            # Determine if this reading is an ALERT
            alert_label = (v >= threshold) ? " ALERT" : ""

            # Print the row: reading number, bar, value
            printf "  │ %2d │ %-50s│ %3d%%%s\n", (i+1), bar, v, alert_label
        }

        # If no data was found
        if (total == 0) {
            print "  │  No data found. Run ./monitor.sh at least once.       │"
        }
    }
    '

    echo -e "  ${CYAN}└──────────────────────────────────────────────────────┘${NC}"
    echo ""
}

# --- Step 4: Draw charts for each metric
# Source config.cfg to get threshold values
source "$PROJECT_DIR/config.cfg"

draw_chart "CPU Usage    " "[CPU]"    "$CPU_THRESHOLD"    "$RED"
draw_chart "Memory Usage " "[MEMORY]" "$MEMORY_THRESHOLD" "$YELLOW"
draw_chart "Disk Usage   " "[DISK]"   "$DISK_THRESHOLD"   "$GREEN"

# --- Step 5: Print chart legend
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "  ${YELLOW}LEGEND:${NC}"
echo -e "  ${GREEN}#${NC} = 2% usage per character"
echo -e "  ${RED}ALERT${NC} = reading exceeded the configured threshold"
echo -e "  Numbers on the left = reading order (1 = oldest shown)"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""

# --- Step 6: Print a summary of min/max/average for each metric

echo -e "${BOLD}${YELLOW}  STATISTICS SUMMARY (all-time from health.log)${NC}"
echo ""

for METRIC in "CPU|[CPU]" "Memory|[MEMORY]" "Disk|[DISK]"; do
    MNAME=$(echo "$METRIC" | cut -d'|' -f1)
    MTAG=$(echo "$METRIC" | cut -d'|' -f2)

    STATS=$(grep "$MTAG" "$LOG_FILE" | grep -v "\[REMOTE\]" | \
    awk '/Usage: / {
        split($0, p, "Usage: ")
        split(p[2], n, "%")
        v = n[1] + 0
        sum += v; count++
        if (count == 1 || v < min) min = v
        if (v > max) max = v
    }
    END {
        if (count > 0)
            printf "Min: %d%%  Max: %d%%  Avg: %.1f%%  Readings: %d", min, max, sum/count, count
        else
            print "No data"
    }')

    echo -e "  ${CYAN}${MNAME}:${NC} $STATS"
done

echo ""
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 4.3 — Make the Script Executable

```bash
chmod +x ~/health-monitor/checks/trend_chart.sh
```

### Step 4.4 — Test the Trend Chart

```bash
cd ~/health-monitor
bash checks/trend_chart.sh
```

Expected output (values will vary based on your system's actual usage):

```
============================================================
   SERVER HEALTH — HISTORICAL TREND CHART
   (Last 10 readings per metric from health.log)
============================================================

  CPU Usage    (threshold: 80%)
  Scale: each # = 2%  |  Max bar = 50 chars (100%)
  ┌──────────────────────────────────────────────────────┐
  │  1 │ ######                                           │  12%
  │  2 │ #######                                          │  14%
  │  3 │ ######                                           │  12%
  │  4 │ ########                                         │  16%
  │  5 │ ######                                           │  12%
  └──────────────────────────────────────────────────────┘

  Memory Usage  (threshold: 75%)
  ...
```

> If you see "No data found", run `./monitor.sh` a few more times and retry.

---

## Integrating All Bonuses into monitor.sh

Now that all four bonus scripts are working individually, add them to `monitor.sh` so they run automatically every time the main script runs.

### Step 5.1 — Back Up the Current monitor.sh

Always back up before editing:

```bash
cp ~/health-monitor/monitor.sh ~/health-monitor/monitor.sh.backup
```

Confirm the backup:

```bash
ls -lh ~/health-monitor/monitor.sh.backup
```

### Step 5.2 — Open monitor.sh for Editing

```bash
nano ~/health-monitor/monitor.sh
```

### Step 5.3 — Locate the Correct Position to Add the Bonus Calls

Scroll to the **bottom** of `monitor.sh`. Find the section that looks like this (near the very end):

```bash
# --- Step 8: Call the report generation function
generate_html_report

echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${GREEN}  Health check run complete.${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""
```

### Step 5.4 — Add the Bonus Script Calls

**Insert** the following lines **between** the `generate_html_report` call and the final `echo` banner lines. The final section should look like this after your edit:

```bash
# --- Step 8: Call the report generation function
generate_html_report

# ============================================================
# BONUS CHALLENGES — Called after main checks and HTML report
# Each is guarded by its own enable/disable flag in config.cfg
# ============================================================

# Bonus 1: Email Alert — sends email if any ALERT was detected
echo -e "${YELLOW}  Running email alert check...${NC}"
bash "$CHECKS_DIR/email_alert.sh"

# Bonus 2: Slack Webhook — sends Slack message if any ALERT was detected
echo -e "${YELLOW}  Running Slack alert check...${NC}"
bash "$CHECKS_DIR/slack_alert.sh"

# Bonus 3: Remote SSH Checks — checks all servers in remote_servers.cfg
echo -e "${YELLOW}  Running remote server checks...${NC}"
bash "$CHECKS_DIR/remote_check.sh"

# Bonus 4: Trend Chart — displays ASCII chart of historical data
echo -e "${YELLOW}  Generating trend chart...${NC}"
bash "$CHECKS_DIR/trend_chart.sh"

echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${GREEN}  Health check run complete.${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""
```

Save: `Ctrl + O`, `Enter`, `Ctrl + X`.

### Step 5.5 — Test the Full Integrated Run

```bash
cd ~/health-monitor
./monitor.sh
```

The output should now include all original checks, the HTML report, email status, Slack status, remote server results, and the trend chart — all in one run.

---

## Testing All Four Bonuses Together

### Final Integration Test Checklist

Run through each item below to confirm everything is working:

**Test 1 — Full run produces no errors:**

```bash
cd ~/health-monitor
./monitor.sh 2>&1 | tee /tmp/monitor_test.txt
```

The `2>&1` redirects any error messages to the screen. Review the output for any lines containing `ERROR` or `command not found`.

**Test 2 — Log file contains all entry types:**

```bash
grep "\[CPU\]"     ~/health-monitor/logs/health.log | tail -3
grep "\[MEMORY\]"  ~/health-monitor/logs/health.log | tail -3
grep "\[DISK\]"    ~/health-monitor/logs/health.log | tail -3
grep "\[SERVICE\]" ~/health-monitor/logs/health.log | tail -3
grep "\[REMOTE\]"  ~/health-monitor/logs/health.log | tail -3
```

Each `grep` command should return at least 1 result.

**Test 3 — Email delivery confirmed:**

```bash
mail
```

You should see at least 1 message. If no alerts have triggered, temporarily lower `CPU_THRESHOLD=1` in `config.cfg`, run `./monitor.sh`, then check mail again.

**Test 4 — Slack message received:**

Open your Slack workspace. The `#server-alerts` channel (or whichever channel you chose) should show a message.

**Test 5 — Trend chart shows at least 5 readings:**

```bash
bash ~/health-monitor/checks/trend_chart.sh
```

Each metric section should show at least 5 bars.

**Test 6 — All scripts have execute permission:**

```bash
ls -la ~/health-monitor/checks/
```

Every `.sh` file should show `-rwxrwxr-x` (the three `x` characters indicate execute permission for owner, group, and others).

---

## Final File Checklist

| # | File | Location | Purpose |
|---|------|----------|---------|
| 1 | `monitor.sh` | `~/health-monitor/` | Main orchestrator (updated with bonus calls) |
| 2 | `config.cfg` | `~/health-monitor/` | Config (updated with email/Slack settings) |
| 3 | `email_alert.sh` | `~/health-monitor/checks/` | Bonus 1: Email alert |
| 4 | `slack_alert.sh` | `~/health-monitor/checks/` | Bonus 2: Slack webhook |
| 5 | `remote_check.sh` | `~/health-monitor/checks/` | Bonus 3: Remote SSH checks |
| 6 | `trend_chart.sh` | `~/health-monitor/checks/` | Bonus 4: ASCII trend chart |
| 7 | `remote_servers.cfg` | `~/health-monitor/` | Server list for remote checks |
| 8 | `monitor.sh.backup` | `~/health-monitor/` | Backup of original monitor.sh |
| 9 | `logs/health.log` | `~/health-monitor/logs/` | Log file (now includes REMOTE entries) |

Verify everything exists:

```bash
find ~/health-monitor -type f | sort
```

---

## Troubleshooting

### Problem: `mail` command not found

**Solution:**

```bash
sudo dnf install -y s-nail
# OR
sudo dnf install -y mailx
```

After installing, test with:

```bash
echo "Test message" | mail -s "Test Subject" $(whoami)@localhost
mail
```

---

### Problem: Slack returns HTTP 400 or "no_text"

**Cause:** The JSON payload has a formatting error — usually an unescaped special character in the alert text.

**Solution:** Test the webhook with a minimal payload first to confirm the URL works:

```bash
curl -s -X POST \
  -H "Content-type: application/json" \
  -d '{"text":"Test alert from health-monitor"}' \
  "YOUR_WEBHOOK_URL_HERE"
```

Replace `YOUR_WEBHOOK_URL_HERE` with your actual URL. Expected response: `ok`

If this works but the full script does not, the issue is special characters in the log text. Check `logs/health.log` for any lines with double-quotes or backslashes.

---

### Problem: SSH asks for a password / `Permission denied (publickey)`

**Solution:** The public key was not copied correctly. Redo Step 3.4:

```bash
ssh-copy-id $(whoami)@localhost
```

Then test again:

```bash
ssh -o BatchMode=yes $(whoami)@localhost "echo test"
```

If you still get an error, check that `sshd` is running:

```bash
sudo systemctl status sshd
```

And check that the `~/.ssh/` directory has correct permissions (SSH is very strict):

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
chmod 600 ~/.ssh/authorized_keys
```

---

### Problem: Trend chart shows "No data found" for a metric

**Cause:** The log file does not have enough entries for that metric, or the log format does not match what `awk` expects.

**Solution:**

Run the monitor several more times:

```bash
cd ~/health-monitor
for i in {1..10}; do ./monitor.sh; done
```

Then check the log format manually:

```bash
grep "\[CPU\]" ~/health-monitor/logs/health.log | head -3
```

Expected format:

```
2025-08-15 10:23:01 [CPU] Status: PASS | Usage: 12% | Threshold: 80%
```

If the format looks different (for example, if a previous version of the scripts wrote the log differently), the `awk` pattern `Usage: ` must match exactly. Check for any extra spaces or different capitalisation in your log entries.

---

### Problem: remote_check.sh connects but the remote scripts fail

**Cause:** The `health-monitor` project was not copied to the remote server.

**Solution:**

```bash
# Copy the entire project to the remote server
scp -r ~/health-monitor student@<remote-ip>:~/

# Verify the scripts exist remotely
ssh student@<remote-ip> "ls ~/health-monitor/checks/"

# Make the scripts executable on the remote server
ssh student@<remote-ip> "chmod +x ~/health-monitor/checks/*.sh"
```

---

### Problem: monitor.sh crashes after adding bonus calls

**Solution:** Restore the backup and try again:

```bash
cp ~/health-monitor/monitor.sh.backup ~/health-monitor/monitor.sh
```

Re-open `monitor.sh` with `nano` and carefully re-apply the changes from Step 5.4. Make sure you are inserting the new lines in the correct position — **before** the final echo banner lines, **after** `generate_html_report`.

---

*End of Bonus Challenges Guide — Automated Server Health Monitor — RHEL 10*
