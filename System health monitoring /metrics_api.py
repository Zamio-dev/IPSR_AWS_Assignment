#!/usr/bin/env python3
"""
metrics_api.py — SysWatch Local Metrics API
============================================
Collects real RHEL 10 system metrics and serves them to the dashboard.

SECURITY MODEL:
  - Binds to 127.0.0.1 only → never reachable from the network
  - Every request must include X-API-Key header → rejects unknown callers
  - CORS restricted to localhost origins only
  - No sensitive data (passwords, keys) in responses
  - API key stored in a separate file, not in this script

Author: SysWatch project
Usage:  python3 metrics_api.py
"""

import os
import time
import json
import threading
import subprocess
from datetime import datetime
from functools import wraps

import psutil
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

# ─────────────────────────────────────────────────────────────
# APP & CORS SETUP
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)

# Allow requests from: local file:// pages and localhost only
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "null",              # file:// origin (browser-opened HTML)
            "http://127.0.0.1",
            "http://127.0.0.1:5050",
            "http://localhost",
            "http://localhost:5050",
        ]
    }
})

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE    = os.path.join(BASE_DIR, "api.key")
LOG_FILE    = os.path.join(BASE_DIR, "..", "logs", "health.log")
PORT        = 5050
HOST        = "127.0.0.1"   # NEVER change this to 0.0.0.0

# Load API key from file
try:
    with open(KEY_FILE) as f:
        API_KEY = f.read().strip()
    if not API_KEY:
        raise ValueError("api.key is empty")
except FileNotFoundError:
    raise SystemExit(
        f"\n[ERROR] api.key not found at {KEY_FILE}\n"
        "Run:  python3 -c \"import secrets; open('api/api.key','w').write(secrets.token_hex(32))\"\n"
        "from your project root directory first.\n"
    )

# ─────────────────────────────────────────────────────────────
# DISK I/O TRACKING (delta between readings)
# ─────────────────────────────────────────────────────────────
_io_lock        = threading.Lock()
_last_io_time   = time.time()
_last_io        = psutil.disk_io_counters()
_io_read_mbs    = 0.0
_io_write_mbs   = 0.0

def _refresh_io():
    """Called from background thread every 2 seconds to track real I/O speed."""
    global _last_io_time, _last_io, _io_read_mbs, _io_write_mbs
    while True:
        time.sleep(2)
        try:
            now_io   = psutil.disk_io_counters()
            now_time = time.time()
            with _io_lock:
                dt = max(now_time - _last_io_time, 0.001)
                _io_read_mbs  = round((now_io.read_bytes  - _last_io.read_bytes)  / dt / 1e6, 2)
                _io_write_mbs = round((now_io.write_bytes - _last_io.write_bytes) / dt / 1e6, 2)
                _last_io_time = now_time
                _last_io      = now_io
        except Exception:
            pass

threading.Thread(target=_refresh_io, daemon=True).start()

# ─────────────────────────────────────────────────────────────
# AUTH DECORATOR
# ─────────────────────────────────────────────────────────────
def require_key(f):
    """Reject any request that does not supply the correct X-API-Key header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key or key != API_KEY:
            abort(401)
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _uptime_str(secs):
    d = secs // 86400
    h = (secs % 86400) // 3600
    m = (secs % 3600)  // 60
    return f"{d}d {h}h {m}m"

def _safe_disk_usage(path):
    try:
        u = psutil.disk_usage(path)
        return {
            "mountpoint": path,
            "total_gb":   round(u.total / 1e9, 1),
            "used_gb":    round(u.used  / 1e9, 1),
            "free_gb":    round(u.free  / 1e9, 1),
            "pct":        u.percent,
        }
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    """Simple liveness check — no auth required."""
    return jsonify({"status": "ok", "ts": datetime.now().isoformat()})


@app.route("/api/metrics")
@require_key
def metrics():
    """
    Returns all system metrics in one call.
    Polled every 2 seconds by the dashboard.
    """
    # ── CPU ──────────────────────────────────────────────────
    cpu_pct      = psutil.cpu_percent(interval=0.2)
    cpu_per_core = psutil.cpu_percent(interval=0.2, percpu=True)
    cpu_freq     = psutil.cpu_freq()
    load1, load5, load15 = os.getloadavg()

    # ── Memory ───────────────────────────────────────────────
    mem  = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # ── Disk ─────────────────────────────────────────────────
    root_disk = psutil.disk_usage("/")
    with _io_lock:
        io_read  = _io_read_mbs
        io_write = _io_write_mbs

    # Partitions (skip pseudo-filesystems)
    SKIP_FS = {"tmpfs","devtmpfs","squashfs","overlay","proc","sysfs",
               "devpts","cgroup","cgroup2","pstore","bpf","tracefs"}
    partitions = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        if part.fstype in SKIP_FS or part.mountpoint in seen:
            continue
        seen.add(part.mountpoint)
        info = _safe_disk_usage(part.mountpoint)
        if info and info["total_gb"] > 0:
            info["device"]  = part.device
            info["fstype"]  = part.fstype
            partitions.append(info)

    # ── System ───────────────────────────────────────────────
    boot_time   = psutil.boot_time()
    uptime_secs = int(time.time() - boot_time)
    uname       = os.uname()

    # ── Inodes (root) ─────────────────────────────────────────
    try:
        st = os.statvfs("/")
        inode_total = st.f_files
        inode_free  = st.f_ffree
        inode_pct   = round((1 - inode_free / max(inode_total, 1)) * 100, 1)
    except Exception:
        inode_pct = 0

    return jsonify({
        "cpu": {
            "percent":      round(cpu_pct, 1),
            "per_core":     [round(c, 1) for c in cpu_per_core],
            "core_count":   psutil.cpu_count(logical=True),
            "phys_count":   psutil.cpu_count(logical=False),
            "freq_mhz":     round(cpu_freq.current, 0) if cpu_freq else 0,
            "load1":        round(load1,  2),
            "load5":        round(load5,  2),
            "load15":       round(load15, 2),
        },
        "memory": {
            "total_mb":     round(mem.total     / 1e6),
            "used_mb":      round(mem.used      / 1e6),
            "available_mb": round(mem.available / 1e6),
            "cached_mb":    round(getattr(mem, "cached",  0) / 1e6),
            "buffers_mb":   round(getattr(mem, "buffers", 0) / 1e6),
            "percent":      mem.percent,
            "swap_total_mb":round(swap.total / 1e6),
            "swap_used_mb": round(swap.used  / 1e6),
            "swap_percent": swap.percent,
        },
        "disk": {
            "root_pct":     round(root_disk.percent, 1),
            "root_used_gb": round(root_disk.used  / 1e9, 1),
            "root_total_gb":round(root_disk.total / 1e9, 1),
            "root_free_gb": round(root_disk.free  / 1e9, 1),
            "io_read_mbs":  max(io_read,  0),
            "io_write_mbs": max(io_write, 0),
            "inode_pct":    inode_pct,
            "partitions":   partitions,
        },
        "system": {
            "hostname":     uname.nodename,
            "kernel":       uname.release,
            "os":           "RHEL 10",
            "uptime_secs":  uptime_secs,
            "uptime_str":   _uptime_str(uptime_secs),
            "proc_count":   len(psutil.pids()),
            "timestamp":    datetime.now().isoformat(),
        }
    })


@app.route("/api/processes")
@require_key
def processes():
    """
    Returns the live process list with cpu, mem, disk I/O.
    Polled every 3 seconds by the dashboard.
    """
    result = []
    # First pass: collect all processes (cpu_percent needs two samples)
    procs = list(psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_info",
         "status", "io_counters", "username"]
    ))
    # Small sleep so cpu_percent delta is meaningful
    time.sleep(0.1)

    for p in procs:
        try:
            info = p.as_dict(attrs=[
                "pid","name","cpu_percent","memory_info",
                "status","io_counters","username"
            ])
            mem_rss  = info["memory_info"].rss if info["memory_info"] else 0
            io       = info["io_counters"]
            io_total = ((io.read_bytes + io.write_bytes) / 1e6) if io else 0

            result.append({
                "pid":     info["pid"],
                "name":    (info["name"] or "?")[:30],
                "cpu":     round(info["cpu_percent"] or 0, 1),
                "mem_mb":  round(mem_rss / 1e6, 1),
                "disk_mb": round(io_total, 1),   # cumulative MB (not speed per-proc)
                "status":  info["status"] or "unknown",
                "user":    (info["username"] or "?")[:16],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return jsonify({"processes": result, "count": len(result)})


@app.route("/api/logs")
@require_key
def logs():
    """
    Returns the last 50 lines from health.log.
    Polled every 5 seconds by the dashboard.
    """
    try:
        log_path = os.path.normpath(LOG_FILE)
        # Safety: only read file inside the project tree
        with open(log_path, "r", errors="replace") as f:
            lines = f.readlines()
        entries = [l.strip() for l in lines[-50:] if l.strip()]
        return jsonify({"logs": entries, "count": len(entries)})
    except FileNotFoundError:
        return jsonify({"logs": [], "count": 0})
    except Exception as e:
        return jsonify({"logs": [], "error": str(e), "count": 0})


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n  SysWatch Metrics API")
    print(f"  Listening on  http://{HOST}:{PORT}")
    print(f"  API key file  {KEY_FILE}")
    print(f"  Log file      {os.path.normpath(LOG_FILE)}")
    print(f"  Network scope 127.0.0.1 only (not exposed)\n")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
