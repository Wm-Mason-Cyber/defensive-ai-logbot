# SYSTEM SYNOPSIS: AP Cybersecurity Automated Lab Framework  

## Role Context: 

You are an expert DevOps engineer, systems administrator, and computer science educator. You are helping an instructor design automated testing, grading, and logging infrastructure for a secondary school AP Cybersecurity course.

## Classroom Constraints:

* **Schedule:** 6 periods/day, high drift risk if students share environments  
* **Network:** Strict local containment / air-gapped classroom router. No public cloud or external SaaS. Instructor does not control the classroom router.  
* **Target Domain:** Applied engineering labs covering Linux operations, scripting, network configuration, and security concepts.

## 1\. THE THREE DEPLOYMENT ENVIRONMENT TIERS

Labs scaffold student independence through three stepping stones:

### Tier 1 — 1:1 Isolated Sandbox (Container-Per-Student)

A single central classroom host runs one Docker container per student (e.g., `p1-jsmith`). Home directories are mapped to persistent host volumes. Students SSH into their dedicated container via an SSH config alias (e.g., `ssh  0_5_1.get-comfy-in-command.lab`). All Tier 1 containers share a Docker bridge network (`lab_net`) with the nginx reverse proxy container. Each container shows a pre-auth SSH banner (lab name \+ big-idea bullets via sshd Banner directive) and a post-login MOTD (graded checklist \+ self-check command); Ubuntu or other dynamic MOTD suppressed. 

### Tier 2 — Shared Classroom Multi-User Container (One Container Per Period)

One container per class period (e.g., `period1-shared`). Students have distinct POSIX accounts. Home directories restricted (`chmod 700`). Teaches multi-user dynamics and file permissions. Each container shows a pre-auth SSH banner (lab name \+ big-idea bullets via sshd Banner directive) and a post-login MOTD (graded checklist \+ self-check command); Ubuntu or other dynamic MOTD suppressed.

### Tier 3 — Bare-Metal Ecosystem (Physical Local Partitions)

Students boot into a physical local Linux installation with `sudo` access. Grading via local script execution or push to the classroom Gitea instance.

## 2\. THE TESTING & CENTRAL GRADING PARADIGM

Every lab features a dual-use automated framework:

* **Student-Facing:** Students run a local test suite (`python3 -m pytest /opt/lab_tests/test_lab.py -v`) for instant granular feedback.  
* **Teacher-Facing:** A host-level compilation script runs the same suite in each container and aggregates results.  
* **Participation Assertion:** When the nginx RP is running, the grading compiler checks the access log for an entry matching `GET /<username>`. A confirmed login hit counts as one additional passed assertion. A missing hit counts as one additional failed assertion. If the nginx container is offline, this assertion is skipped entirely — no penalty. This assertion carries equal weight to any pytest assertion.

## 3\. STANDARDIZED DATA SCHEMAS  

**Input — Roster File (`infra/students.csv`)**

```
username,password,first_name,last_name,period,student_id,grade_level
jsmith,CyberDefender2026!,Jane,Smith,1,010101,11
bwilliams,SecurePass321!,Bob,Williams,1,676767,10
cwang,CryptoShield88!,Carlos,Wang,3,424242,12
```

**Output — Grade Book Summary (`grades_report.csv`)**

```
username,period,lab_id,passed_assertions,failed_assertions,grade_percentage
jsmith,1,lab_1_1,4,0,100.0
bwilliams,1,lab_1_1,3,1,75.0
cwang,3,lab_1_1,0,4,0.0
```

Note: `passed_assertions` and `failed_assertions` include the participation assertion when nginx is running.

## 4\. INTERACTION PROTOCOL FOR THE AI

When the instructor provides a new lab topic or concept, **do not generate code immediately.** Acknowledge this framework and prompt with the following scope request:

```
### Lab Blueprint Scope Request
To design the automated suite for this lab, please specify:
1. **Target Environment Tier:** (Tier 1 / Tier 2 / Tier 3?)
2. **Lab Parameters to Evaluate:** Files, permissions, environment variables, network conditions being modified?
3. **Security Constraints:** Peer-sabotage checks, permission bitmasks, loopback enforcement?
4. **Logging & Telemetry:** Is logging appropriate for this lab? (None / Standardized Nginx Logging for FRQ Practice)
```

 Once the instructor provides those details, generate the full implementation set: Dockerfile/orchestration, pytest/shell assessment logic, nginx RP config if applicable, and the grading compiler script.

## 5\. LOGGING & TELEMETRY STANDARDS (FRQ PREP)

All Tier 1 environments implement a standard nginx reverse proxy logging stack. Other tiers may include it when it fits the lesson content. When **Logging Enabled** is selected in the Lab Blueprint, the following apply.

### Infrastructure:

* An `infra/nginx/` directory contains the nginx container definition (`Dockerfile`, `nginx.conf`, `start.sh`, `generate_student_locations.sh`, `logrotate.conf`, `dashboard/dashboard.py`)  
* Container name: `lab-nginx-rp`, started automatically at the end of `setup_containers.sh`  
* All student containers and the nginx container share Docker bridge network `lab_net`  
* `setup_nginx.sh` handles standalone start/rebuild/teardown of the nginx container  

### Domain & Hostname Resolution (layered):

* **Baseline:** Docker host runs Avahi and advertises via mDNS. Student machines resolve `cyber.local` automatically (standard on Debian, no config required).  
* **Layer 2:** Each student machine has a one-line `/etc/hosts` entry mapping the Docker host LAN IP to a `comet-tech.org` subdomain (e.g., `cyber.comet-tech.org`). Provisioned during Lab 0.4.  
* **Layer 3 (advanced/optional):** `dnsmasq` on the Docker host acts as a classroom DNS resolver. Documented in `TEACHER_GUIDE.md` as a teaching opportunity, not assumed by default.    
* **Subdomain format:** `<context>.comet-tech.org`. Subdomains are trivially swappable; all lab documentation uses `cyber.local` as the baseline reference.

### URL Routes:

| Path | Purpose | Audiance |
| :---- | :---- | :---- |
| **`/<username>`** | HTTP check-in — generates log entry, returns confirmation        | Students (early curriculum)  |
| **`/logs/access`** | Raw access log as `text/plain` via symlink | Students (FRQ practice) |
| **`/logs/errors`** | Raw error log as `text/plain` via symlink        | Students (FRQ practice) |
| **`/dashboard`** |  Real-time connectivity dashboard | instructor |
| **`/api/status`** | JSON feed of student status | Instructor / tooling  |

### Two-Mode Log Access (same files, curriculum-stage-dependent):  

* **Early curriculum:** Students hit `cyber.local/logs/access` in a browser. nginx serves it as plain text via symlink from `/var/log/app/`.  
* **Later curriculum:** Students SSH into the nginx container directly and read `/var/log/app/access.log` at its standard Linux path. Same file, different access method — the direct-access stage is an explicit learning objective.

### Auto-Login Reporting:

Student containers include `/etc/profile.d/report_login.sh`. On every SSH login, it synchronously curls `http://lab-nginx-rp/$USER` (2-second max timeout) and prints:

* `[lab] Session logged.` on success  
* `[lab] Warning: lab logging server unreachable. Tell your teacher.` on failure

This requires no student action and automatically generates the participation log entry.  
    
**Log Format:** Standard nginx `combined` format (renamed `lab` internally to avoid nginx reserved name conflict). Matches the format referenced in AP exam FRQ materials.  
    
**Log Permissions:** `root`\-owned, mode `644` (students read-only).  
    
**Log Rotation:** Daily `logrotate`, 7-day retention, `nginx -s reopen` on rotate.  

### Dashboard (`/dashboard`):

 \- Python 3 stdlib HTTP server (`dashboard.py`), no external dependencies  
 \- Reads `students.csv` and nginx access log on each request  
 \- Groups students by period; shows Name, Username, Status, Last Access (America/New\_York), IP  
 \- Status: **Active** (last hit \< 5 min, green), **Idle** (last hit today, yellow), **No connection** (gray)  
 \- Auto-refreshes every 30 seconds with countdown; JSON API at `/api/status`  

### Participation Grading Integration:

`grade_sandbox.sh` checks `docker exec lab-nginx-rp grep "GET /<username>"` in the access log. Hit found → `passed + 1`. No hit → `failed + 1`. nginx offline → assertion skipped.

## 6\. SSH ACCESS & STUDENT CONNECTIVITY

### Student Access (Tier 1):

Students SSH into their dedicated container. They do not use nginx for container access — nginx is a separate HTTP logging layer.      

### SSH Config Generation:

`setup_containers.sh` generates `infra/ssh_config_lab.txt` on every run. Each student's stanza:

```
Host 0_5_1.get-comfy-in-command.lab
    HostName <docker-host-LAN-IP>  
    User jsmith
    Port 2003
```

The `HostName` is auto-detected from the host's primary LAN interface at run time. The `Host` alias encodes the lab ID so students know which lab an entry belongs to.  
    
**Distribution:** Teacher distributes the file or individual stanzas during **Lab 0.4** machine setup. Each student adds their own stanza to `~/.ssh/config`. Connection from then on: `ssh 0_5_1.get-comfy-in-command.lab`  
    
**Port Formula:** `1900 + (period × 100) + student_index_within_period` Period 1 starts at 2001, Period 2 at 2101, etc.

**Fallback (if SSH config not set up):** `ssh <username>@<docker-host-IP> -p <port>`

## Example Infrastructure for Every Lab:

### infra/nginx/dashboard/dashboard.py

```py
#!/usr/bin/env python3
"""
Lab dashboard server — real-time student connectivity by period.
Reads students.csv and the nginx access log; serves JSON + HTML.

Run inside the nginx container or on the Docker host with log access:
    python3 dashboard.py
    python3 dashboard.py --students /path/students.csv --log /var/log/app/access.log --port 8080

Nginx should proxy /dashboard and /api/status to this server.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

DISPLAY_TZ = ZoneInfo(os.environ.get("LAB_TIMEZONE", "America/New_York"))


# ── Defaults ───────────────────────────────────────────────────────────────────

DEFAULT_STUDENTS = Path("/opt/lab/students.csv")
DEFAULT_LOG      = Path("/var/log/app/access.log")
DEFAULT_PORT     = int(os.environ.get("DASHBOARD_PORT", "8080"))
ACTIVE_SECS      = 300   # last access within 5 min → Active; else → Idle

# Standard nginx combined-log first-path-segment capture
LOG_RE   = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] '
    r'"(?:GET|POST|PUT|DELETE|HEAD|OPTIONS) /([^/\s]+)'
)
TIME_FMT = "%d/%b/%Y:%H:%M:%S %z"


# ── Data ───────────────────────────────────────────────────────────────────────

def load_students(path: Path) -> dict[str, dict]:
    students: dict[str, dict] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            u = row["username"].strip()
            if u:
                students[u] = {k.strip(): v.strip() for k, v in row.items()}
    return students


def last_accesses(log_path: Path) -> dict[str, dict]:
    """Most recent access per username: {username: {time, ip}}."""
    best: dict[str, dict] = {}
    try:
        with open(log_path) as f:
            for line in f:
                m = LOG_RE.match(line)
                if not m:
                    continue
                ip, time_str, username = m.group(1), m.group(2), m.group(3)
                try:
                    t = datetime.strptime(time_str, TIME_FMT)
                except ValueError:
                    continue
                if username not in best or t > best[username]["time"]:
                    best[username] = {"time": t, "ip": ip}
    except FileNotFoundError:
        pass
    return best


def build_status(students: dict, accesses: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    for username, info in sorted(students.items(), key=lambda x: (x[1].get("period", ""), x[0])):
        access = accesses.get(username)
        if access:
            delta = (now - access["time"]).total_seconds()
            status = "active" if delta < ACTIVE_SECS else "idle"
            last   = access["time"].astimezone(DISPLAY_TZ).strftime("%H:%M:%S")
            ip     = access["ip"]
        else:
            status, last, ip = "none", "—", "—"
        rows.append({
            "username": username,
            "name":     f"{info.get('first_name', '')} {info.get('last_name', '')}".strip(),
            "period":   info.get("period", "?"),
            "status":   status,
            "last":     last,
            "ip":       ip,
        })
    return rows


# ── HTML ───────────────────────────────────────────────────────────────────────

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyber Lab — Dashboard</title>
<style>
  :root {
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #30363d;
    --text:    #e6edf3;
    --muted:   #8b949e;
    --green:   #3fb950;
    --yellow:  #d29922;
    --red:     #f85149;
    --blue:    #58a6ff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace;
    font-size: 13px;
    padding: 24px 32px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 14px;
    margin-bottom: 28px;
    border-bottom: 1px solid var(--border);
  }
  h1 { font-size: 16px; color: var(--blue); letter-spacing: 0.03em; }
  #meta { color: var(--muted); font-size: 11px; }

  .period { margin-bottom: 36px; }
  .period-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 6px;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }
  .period-title   { font-size: 14px; font-weight: bold; }
  .period-summary { font-size: 11px; color: var(--muted); }

  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left;
    color: var(--muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 4px 16px 4px 0;
  }
  td { padding: 7px 16px 7px 0; border-top: 1px solid var(--border); }
  tr:hover td { background: var(--surface); }

  .dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    margin-right: 7px;
    vertical-align: middle;
  }
  .active .dot { background: var(--green); box-shadow: 0 0 5px var(--green); }
  .idle   .dot { background: var(--yellow); }
  .none   .dot { background: var(--border); }
  .active { color: var(--green); }
  .idle   { color: var(--yellow); }
  .none   { color: var(--muted); }

  .ip   { color: var(--muted); }
  .name { color: var(--text); }
  .user { color: var(--muted); }

  #error { color: var(--red); margin-top: 16px; }
</style>
</head>
<body>
<header>
  <h1>Cyber Lab &mdash; Student Dashboard</h1>
  <div id="meta">
    Updated: <span id="updated">&mdash;</span>
    &nbsp;|&nbsp;
    Refresh in <span id="countdown">30</span>s
    &nbsp;|&nbsp;
    Times: Cincinnati (ET)
  </div>
</header>
<div id="content">Loading&hellip;</div>
<div id="error"></div>

<script>
const REFRESH = 30;
let t = REFRESH;

function statusCell(s) {
  const labels = { active: 'Active', idle: 'Idle', none: 'No connection' };
  return `<span class="${s}"><span class="dot"></span>${labels[s] ?? s}</span>`;
}

async function refresh() {
  try {
    const resp = await fetch('/api/status');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const { students } = await resp.json();

    const periods = {};
    for (const row of students)
      (periods[row.period] ??= []).push(row);

    let html = '';
    for (const [period, rows] of Object.entries(periods).sort()) {
      const active = rows.filter(r => r.status === 'active').length;
      html += `
      <div class="period">
        <div class="period-header">
          <span class="period-title">Period ${period}</span>
          <span class="period-summary">${active} / ${rows.length} active</span>
        </div>
        <table>
          <thead><tr>
            <th>Name</th><th>Username</th><th>Status</th><th>Last Access</th><th>IP</th>
          </tr></thead>
          <tbody>
            ${rows.map(r => `
            <tr>
              <td class="name">${r.name}</td>
              <td class="user">${r.username}</td>
              <td>${statusCell(r.status)}</td>
              <td>${r.last}</td>
              <td class="ip">${r.ip}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
    }

    document.getElementById('content').innerHTML = html;
    document.getElementById('updated').textContent = new Date().toLocaleTimeString();
    document.getElementById('error').textContent = '';
    t = REFRESH;
  } catch (e) {
    document.getElementById('error').textContent = 'Error fetching status: ' + e.message;
  }
}

setInterval(() => {
  t--;
  document.getElementById('countdown').textContent = t;
  if (t <= 0) refresh();
}, 1000);

refresh();
</script>
</body>
</html>
"""


# ── HTTP server ────────────────────────────────────────────────────────────────

ARGS = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/api/status", "/api/status/"):
            self._json()
        elif self.path in ("/", "/dashboard", "/dashboard/"):
            self._html()
        else:
            self.send_error(404)

    def _json(self):
        students  = load_students(ARGS.students)
        accesses  = last_accesses(ARGS.log)
        payload   = json.dumps({"students": build_status(students, accesses)}).encode()
        self._send(200, "application/json", payload)

    def _html(self):
        self._send(200, "text/html; charset=utf-8", HTML.encode())

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress per-request noise; add back for debug


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    global ARGS
    parser = argparse.ArgumentParser(description="Lab connectivity dashboard")
    parser.add_argument("--students", type=Path, default=DEFAULT_STUDENTS)
    parser.add_argument("--log",      type=Path, default=DEFAULT_LOG)
    parser.add_argument("--port",     type=int,  default=DEFAULT_PORT)
    ARGS = parser.parse_args()

    if not ARGS.students.exists():
        sys.exit(f"students.csv not found: {ARGS.students}")

    print(f"Dashboard: http://localhost:{ARGS.port}/dashboard")
    print(f"Students:  {ARGS.students}")
    print(f"Log:       {ARGS.log}")
    HTTPServer(("", ARGS.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

```

### infra/nginx/Dockerfile

```
FROM nginx:alpine

# Python for dashboard server; crond for logrotate schedule
RUN apk add --no-cache python3 logrotate dcron bash

# Log dirs — nginx will write here; symlinks expose them at /var/www/logs/
RUN mkdir -p /var/log/app /var/www/logs /etc/nginx/conf.d/students && \
    ln -sf /var/log/app/access.log /var/www/logs/access && \
    ln -sf /var/log/app/error.log  /var/www/logs/errors && \
    ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

COPY nginx.conf                   /etc/nginx/nginx.conf
COPY logrotate.conf               /etc/logrotate.d/lab
COPY generate_student_locations.sh /app/generate_student_locations.sh
COPY start.sh                     /app/start.sh
COPY dashboard/                   /app/dashboard/

RUN chmod +x /app/start.sh /app/generate_student_locations.sh

# Logrotate via cron — runs at 00:05 daily
RUN echo "5 0 * * * /usr/sbin/logrotate /etc/logrotate.d/lab" \
    | crontab -

# students.csv mounted at runtime by setup_containers.sh
VOLUME ["/opt/lab"]

EXPOSE 80

ENTRYPOINT ["/app/start.sh"]

```

### infra/nginx/generate\_student\_locations.sh

```sh
#!/usr/bin/env bash
# generate_student_locations.sh — build per-student nginx location blocks from students.csv
#
# Usage: ./generate_student_locations.sh [/path/to/students.csv]
# Output: /etc/nginx/conf.d/students/students.conf
#
# Each location is an HTTP check-in endpoint: hitting /username generates a
# log entry (participation credit) and returns a confirmation page.
# Students access their containers via SSH, not through nginx.

set -euo pipefail

STUDENTS_CSV="${1:-/opt/lab/students.csv}"
OUT_DIR="/etc/nginx/conf.d/students"
OUT="${OUT_DIR}/students.conf"

mkdir -p "$OUT_DIR"
: > "$OUT"

while IFS=, read -r username password first_name last_name period student_id grade_level; do
    username="${username//[$'\r\xef\xbb\xbf ']/}"
    [[ "$username" == "username" || -z "$username" ]] && continue
    period="${period// /}"

    cat >> "$OUT" << CONF
location = /${username} {
    add_header Content-Type text/plain;
    return 200 "Connected.\nStudent:   ${username}\nPeriod:    ${period}\n";
}
CONF

done < "$STUDENTS_CSV"

echo "[nginx] Generated student locations: $OUT"
nginx -t 2>&1 && echo "[nginx] Config OK" || echo "[nginx] Config ERROR — check above"

```

### infra/nginx/logrotate.conf

```
/var/log/app/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    sharedscripts
    postrotate
        nginx -s reopen 2>/dev/null || true
    endscript
}
```

### infra/nginx/nginx.conf

```
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    # Standard combined format — matches what FRQ materials reference
    log_format lab '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent"';

    access_log /var/log/app/access.log lab;
    error_log  /var/log/app/error.log warn;

    server {
        listen 80;
        server_name _;

        # Symlinked log files served as plain text (early curriculum / convenient paths)
        # /var/www/logs/access  -> /var/log/app/access.log
        # /var/www/logs/errors  -> /var/log/app/error.log
        root /var/www;
        location /logs/ {
            default_type text/plain;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }

        # Dashboard + API (served by dashboard.py on port 8080)
        location /dashboard {
            proxy_pass         http://127.0.0.1:8080/dashboard;
            proxy_set_header   X-Forwarded-For $remote_addr;
        }
        location /api/ {
            proxy_pass         http://127.0.0.1:8080/api/;
            proxy_set_header   X-Forwarded-For $remote_addr;
        }

        # Per-student locations generated from students.csv at container start
        include /etc/nginx/conf.d/students/*.conf;

        location / {
            return 200 "Cyber Lab\n";
            add_header Content-Type text/plain;
        }
    }
}
```

### infra/nginx/startup\_nginx.sh

```sh
#!/usr/bin/env bash
# setup_nginx.sh — build (if needed) and start the nginx reverse proxy container
#
# Usage:
#   ./setup_nginx.sh /path/to/students.csv        # start / restart
#   ./setup_nginx.sh /path/to/students.csv --rebuild  # force image rebuild
#   ./setup_nginx.sh --teardown                   # stop and remove

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDENTS="${1:-}"
ARG2="${2:-}"
IMAGE="lab-nginx-rp:latest"
CONTAINER="lab-nginx-rp"
LAB_NETWORK="lab_net"

# ── Teardown ──────────────────────────────────────────────────────────────────
if [[ "$STUDENTS" == "--teardown" ]]; then
    docker rm -f "$CONTAINER" 2>/dev/null && echo "Removed: $CONTAINER" || echo "Not running."
    exit 0
fi

if [[ -z "$STUDENTS" || ! -f "$STUDENTS" ]]; then
    echo "Usage: $0 /path/to/students.csv [--rebuild]"
    exit 1
fi

# ── Shared network (must exist before nginx starts) ───────────────────────────
docker network create "$LAB_NETWORK" 2>/dev/null || true

# ── Build image ───────────────────────────────────────────────────────────────
if [[ "$ARG2" == "--rebuild" ]] || ! docker image inspect "$IMAGE" &>/dev/null; then
    echo "Building $IMAGE ..."
    docker build -t "$IMAGE" "$SCRIPT_DIR"
fi

# ── Stop existing container ───────────────────────────────────────────────────
docker rm -f "$CONTAINER" 2>/dev/null || true

# ── Start ─────────────────────────────────────────────────────────────────────
docker run -d \
    --name "$CONTAINER" \
    --network "$LAB_NETWORK" \
    -v "${STUDENTS}:/opt/lab/students.csv:ro" \
    -p 80:80 \
    --restart unless-stopped \
    "$IMAGE"

echo ""
echo "nginx RP running."
echo "  Dashboard:   http://localhost/dashboard"
echo "  Access log:  http://localhost/logs/access"
echo "  Student URL: http://localhost/<username>"

```

### infra/nginx/start.sh

```sh
#!/bin/sh
set -e

STUDENTS_CSV="${STUDENTS_CSV:-/opt/lab/students.csv}"

if [ ! -f "$STUDENTS_CSV" ]; then
    echo "ERROR: students.csv not found at $STUDENTS_CSV"
    echo "Mount it with: -v /path/to/students.csv:/opt/lab/students.csv:ro"
    exit 1
fi

# Generate per-student nginx location blocks
/app/generate_student_locations.sh "$STUDENTS_CSV"

# Start dashboard server in background
python3 /app/dashboard/dashboard.py \
    --students "$STUDENTS_CSV" \
    --log /var/log/app/access.log \
    --port 8080 &

echo "[dashboard] Started on port 8080"

# Nginx in foreground (keeps container alive)
exec nginx -g 'daemon off;'

```

---

Everything below is very lab-specific, but can give a good impression of how these labs are put together. 

### Example Dockerfile for setup of Tier 1 containers:

```
FROM ubuntu:22.04

ARG NGINX_CONTAINER=lab-nginx-rp
ARG LAB_TIMEZONE=America/New_York
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=$LAB_TIMEZONE

# 1. Restore minimized Ubuntu content (man pages, docs stripped from base image)
RUN sed -i 's,^path-exclude=/usr/share/man/,#path-exclude=/usr/share/man/,' /etc/dpkg/dpkg.cfg.d/excludes \
    && sed -i 's,^path-exclude=/usr/share/locale/,#path-exclude=/usr/share/locale/,' /etc/dpkg/dpkg.cfg.d/excludes || true
RUN apt-get update && apt-get install -y man-db manpages manpages-posix \
    && rm -rf /var/lib/apt/lists/*
RUN yes | unminimize

# 2. Reinstall coreutils/bash so their man pages appear (unminimize may skip already-installed)
RUN apt-get update && apt-get install --reinstall -y \
    coreutils bash util-linux grep findutils \
    && rm -rf /var/lib/apt/lists/*

# 3. Base system (Now every single package installed here will keep its man page!)
RUN apt-get update && apt-get install -y \
    openssh-server sudo curl wget git make build-essential \
    fontconfig ghostscript gsfonts ttf-mscorefonts-installer \
    python3 python3-pip nano \
    # Required lab tools
    htop tmux fzf \
    cowsay figlet lolcat \
    imagemagick \
    chafa \
    tldr \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu installs bat as 'batcat' — expose as 'bat' too
RUN ln -sf /usr/bin/batcat /usr/local/bin/bat

# Pre-populate tldr cache in /etc/skel — copied to every new user's home at creation
# tldr 0.6.x (Haskell) respects XDG_DATA_HOME; cache lands at $XDG_DATA_HOME/tldr
RUN sudo mkdir -p /etc/skel/.local/share \
    && sudo XDG_DATA_HOME=/etc/skel/.local/share tldr --update

# 4. CRITICAL FINAL STEP: Overwrite the fake Ubuntu minimized message script 
# and rebuild the index database so 'man' works
RUN apt-get update && apt-get install --reinstall -y man-db && mandb -c

# ── Tools not in Ubuntu apt ───────────────────────────────────────────────────

# cbonsai: animated bonsai tree — compile from source
RUN sudo apt update && sudo apt install libncursesw5-dev make -y && \
    git clone https://gitlab.com/jallbrit/cbonsai && \
    cd cbonsai && \ 
    sudo make install

# fastfetch: system info display (replaces neofetch)
RUN curl -fsSL \
    "https://github.com/fastfetch-cli/fastfetch/releases/latest/download/fastfetch-linux-amd64.deb" \
    -o /tmp/fastfetch.deb \
    && dpkg -i /tmp/fastfetch.deb \
    && rm /tmp/fastfetch.deb

# ── Grading infrastructure ────────────────────────────────────────────────────
RUN pip3 install pytest --break-system-packages 2>/dev/null || pip3 install pytest

# Class default dotfiles — baseline for PS1/alias diff assertions
RUN git clone --quiet https://github.com/Wm-Mason-Cyber/.dotFiles /opt/lab_defaults

# Test suite (world-readable so student can see what's tested; results dir restricted)
COPY tests/ /opt/lab_tests/
RUN chmod -R 755 /opt/lab_tests/ \
    && mkdir -p /opt/lab_tests/results \
    && chmod 1733 /opt/lab_tests/results

# Sample image for imagemagick exercise — generated at build time, no external file needed
RUN mkdir -p /opt/lab_assets
RUN convert -size 1920x1080 gradient:DodgerBlue-MediumOrchid \
    -font DejaVu-Sans -pointsize 172 \
    -fill white -gravity Center -annotate 0 "AP Cybersecurity\nLab 0.5" \
    /opt/lab_assets/sample.jpg 2>/dev/null || \
    convert -size 1920x1080 gradient:blue-purple /opt/lab_assets/sample.jpg
RUN apt remove -y imagemagick && apt autoremove -y

# ── Login reporter ────────────────────────────────────────────────────────────
# On every SSH login, curl the nginx RP to record participation in the access
# log. Reports success or failure to the student (max 2s wait).
RUN printf '#!/bin/sh\nif curl -sf --max-time 2 "http://%s/$USER" >/dev/null 2>&1; then\n  echo "[lab] Session logged."\nelse\n  echo "[lab] Warning: lab logging server unreachable. Tell your teacher."\nfi\n' \
    "$NGINX_CONTAINER" > /etc/profile.d/report_login.sh \
    && chmod 644 /etc/profile.d/report_login.sh

# ── Lab identity: login banner + MOTD ────────────────────────────────────────
COPY sandbox/login_banner /etc/ssh/login_banner
COPY sandbox/MOTD         /etc/motd
RUN rm -f /etc/update-motd.d/*

# ── SSH configuration ─────────────────────────────────────────────────────────
RUN mkdir /var/run/sshd \
    && sed -i \
        -e 's/#PasswordAuthentication yes/PasswordAuthentication yes/' \
        -e 's/PermitRootLogin prohibit-password/PermitRootLogin no/' \
        /etc/ssh/sshd_config \
    && echo 'Banner /etc/ssh/login_banner' >> /etc/ssh/sshd_config

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]

```

### Example of login\_banner for Tier 1 containers:

```
 
  
  AP Cybersecurity — Lab 0.5.1
  ____      _      ____                 __         _         _   _          
 / ___| ___| |_   / ___|___  _ __ ___  / _|_   _  (_)_ __   | |_| |__   ___ 
| |  _ / _ \ __| | |   / _ \| '_ ` _ \| |_| | | | | | '_ \  | __| '_ \ / _ \
| |_| |  __/ |_  | |__| (_) | | | | | |  _| |_| | | | | | | | |_| | | |  __/
 \____|\___|\__|  \____\___/|_| |_| |_|_|  \__, | |_|_| |_|  \__|_| |_|\___|
                                           |___/                            
  ____                                          _   _     _            
 / ___|___  _ __ ___  _ __ ___   __ _ _ __   __| | | |   (_)_ __   ___ 
| |   / _ \| '_ ` _ \| '_ ` _ \ / _` | '_ \ / _` | | |   | | '_ \ / _ \
| |__| (_) | | | | | | | | | | | (_| | | | | (_| | | |___| | | | |  __/
 \____\___/|_| |_| |_|_| |_| |_|\__,_|_| |_|\__,_| |_____|_|_| |_|\___|
                                           
  ─────────────────────────────────────────────────────
  
  Big ideas:
    · The terminal is a power tool, not just for coders
    · Tools have documentation — read it before asking
    · Config lives in dotfiles and travels with you
    · Recording terminal sessions is a real-world skill
  
  ─────────────────────────────────────────────────────

```

### Example of MOTD for Tier 1 containers:

```

  Grading checklist — Lab 0.5.1
  Get Comfy in the Command Line
  ─────────────────────────────────────────────────────
  Required (all 9 must pass):
    [ ] bat installed
    [ ] eza installed
    [ ] asciinema installed
    [ ] ImageMagick installed (convert + identify)
    [ ] alias cat='bat' in dotfiles
    [ ] PS1 customized from class default
    [ ] at least one additional alias
    [ ] resized image in ~/ (560-960px wide, not sample.jpg)
    [ ] .cast recording file in ~/

  Optional gate — need any 6 of 9:
    cbonsai  fastfetch  lolcat  htop  fzf  figlet  cowsay  tldr  tmux

  Self-check: python3 -m pytest /opt/lab_tests/test_lab.py -v
  ─────────────────────────────────────────────────────
  
```

### Example PyTest for evaluation of completion in Tier 1:

```py
"""
Lab 0.5: Get Comfy in the Command Line — Tier 1 (Sandbox) Assertions

Student self-check:
  python3 -m pytest /opt/lab_tests/test_lab.py -v

Teacher grading (runs inside student container):
  docker exec -u <username> p<period>-<username> \
      python3 -m pytest /opt/lab_tests/test_lab.py -v --tb=short
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def has_cmd(*names: str) -> bool:
    return any(shutil.which(n) for n in names)


def image_width(path: Path) -> int | None:
    """Return pixel width of an image file, or None on failure."""
    result = subprocess.run(
        ["identify", "-format", "%w", str(path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip().split()[0])
    except (ValueError, IndexError):
        return None


# ── Required: tool installation ───────────────────────────────────────────────

@pytest.mark.required
def test_bat_installed():
    assert has_cmd("bat", "batcat"), (
        "bat not found.\n"
        "Install: sudo apt install bat\n"
        "Then verify: bat --version"
    )


@pytest.mark.required
def test_eza_installed():
    assert has_cmd("eza"), (
        "eza not found.\n"
        "Follow the instructions at https://github.com/eza-community/eza/blob/main/INSTALL.md#debian-and-ubuntu\n"
        "to install eza via apt. Then verify: eza --version"
    )


@pytest.mark.required
def test_asciinema_installed():
    assert has_cmd("asciinema"), (
        "asciinema not found.\n"
        "Install: sudo apt install asciinema"
    )


@pytest.mark.required
def test_imagemagick_installed():
    assert has_cmd("convert") and has_cmd("identify"), (
        "ImageMagick not found (need 'convert' and 'identify').\n"
        "Install: sudo apt install imagemagick"
    )


# ── Required: dotfile configuration ──────────────────────────────────────────

@pytest.mark.required
def test_cat_aliased_to_bat(dotfile_text):
    pattern = re.compile(r"^\s*alias\s+cat=['\"]?bat(?:cat)?['\"]?\s*$", re.MULTILINE)
    assert pattern.search(dotfile_text), (
        "alias cat='bat' not found in ~/.bashrc or ~/.bash_aliases.\n"
        "Add this line to ~/.bash_aliases:\n"
        "  alias cat='bat'\n"
        "Then reload: source ~/.bashrc"
    )


@pytest.mark.required
def test_ps1_modified(home, dotfile_text, default_bashrc_text):
    ps1_lines = [
        l.strip() for l in dotfile_text.splitlines()
        if l.strip().startswith("PS1=")
    ]
    assert ps1_lines, (
        "No PS1= line found in your dotfiles.\n"
        "Add a custom prompt to ~/.bashrc — search 'bash PS1 customization' to explore options."
    )

    if default_bashrc_text:
        default_ps1 = next(
            (l.strip() for l in default_bashrc_text.splitlines() if l.strip().startswith("PS1=")),
            None
        )
        if default_ps1:
            assert not any(l == default_ps1 for l in ps1_lines), (
                "Your PS1 still matches the class default.\n"
                "Change it to something that represents you."
            )


@pytest.mark.required
def test_custom_alias_present(dotfile_text):
    aliases = re.findall(r"^\s*alias\s+(\S+)=", dotfile_text, re.MULTILINE)
    non_cat = [a for a in aliases if a != "cat"]
    assert len(non_cat) >= 1, (
        f"No custom alias found (beyond cat=bat).\n"
        f"Add at least one to ~/.bash_aliases, e.g.:\n"
        f"  alias ll='eza -la --icons'\n"
        f"Then reload: source ~/.bashrc"
    )


# ── Required: produced outputs ────────────────────────────────────────────────

@pytest.mark.required
def test_imagemagick_resized_output(home):
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    candidates = [
        f for f in home.iterdir()
        if f.is_file() and f.suffix.lower() in image_exts
        and f.name != "sample.jpg"  # must be a converted output, not the original
    ]
    assert candidates, (
        "No converted image found in your home directory.\n"
        "Use ImageMagick to resize ~/sample.jpg and save the output:\n"
        "  convert ~/sample.jpg -resize 840x ~/resized.jpg\n"
        "The output file must have a different name than 'sample.jpg'."
    )

    in_range = [(f, image_width(f)) for f in candidates]
    valid = [(f, w) for f, w in in_range if w is not None and 560 <= w <= 960]

    assert valid, (
        "Found image(s) in ~, but none are 560–960px wide.\n"
        + "\n".join(
            f"  {f.name}: {w}px" if w else f"  {f.name}: could not read width"
            for f, w in in_range
        )
        + "\nResize to a width in that range:\n"
        "  convert ~/sample.jpg -resize 840x ~/resized.jpg"
    )


@pytest.mark.required
def test_asciinema_recording_exists(home):
    cast_files = (
        list(home.glob("*.cast"))
        + list((home / ".asciinema").glob("*.cast") if (home / ".asciinema").is_dir() else [])
    )
    assert cast_files, (
        "No asciinema recording (.cast file) found.\n"
        "Record a terminal session:\n"
        "  asciinema rec ~/my_session.cast\n"
        "  (do something interesting, then Ctrl-D to stop)"
    )


# ── Optional tools (must have ≥ 6 of 9) ──────────────────────────────────────

OPTIONAL_TOOLS: dict[str, list[str]] = {
    "cbonsai":    ["cbonsai"],
    "fastfetch":  ["fastfetch"],
    "lolcat":     ["lolcat"],
    "htop":       ["htop"],
    "fzf":        ["fzf"],
    "figlet":     ["figlet"],
    "cowsay":     ["cowsay"],
    "tldr":       ["tldr", "tealdeer"],
    "tmux":       ["tmux"],
}
OPTIONAL_MIN = 6


@pytest.mark.optional
def test_optional_tools_minimum():
    found = {name for name, cmds in OPTIONAL_TOOLS.items() if has_cmd(*cmds)}
    missing = sorted(set(OPTIONAL_TOOLS) - found)
    assert len(found) >= OPTIONAL_MIN, (
        f"Found {len(found)}/{len(OPTIONAL_TOOLS)} optional tools. Need at least {OPTIONAL_MIN}.\n"
        f"Not yet explored: {', '.join(missing)}\n"
        f"Most can be launched directly — check the lab guide for each one."
    )

```

### Example grading script for Tier1: 

```sh
#!/usr/bin/env bash
# grade_sandbox.sh — run pytest inside each student container, compile grades_report.csv
# Usage:
#   ./grade_sandbox.sh students.csv           # grade all periods
#   ./grade_sandbox.sh students.csv 1         # grade period 1 only
#
# Output: grades_report.csv (overwrites)

set -euo pipefail

ROSTER="${1:?Usage: $0 students.csv [period]}"
PERIOD_FILTER="${2:-}"
LAB_ID="lab_0_5"
TESTS="/opt/lab_tests/test_lab.py"
OUT="grades_report.csv"

echo "username,period,lab_id,passed_assertions,failed_assertions,grade_percentage" > "$OUT"

while IFS=, read -r username password first_name last_name period student_id grade_level; do
    username="${username//[$'\r\xef\xbb\xbf ']/}"
    [[ "$username" == "username" || -z "$username" ]] && continue
    period="${period// /}"
    [[ -n "$PERIOD_FILTER" && "$period" != "$PERIOD_FILTER" ]] && continue

    container="p${period}-${username}"

    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "${username},${period},${LAB_ID},0,0,ERR_OFFLINE" >> "$OUT"
        echo "[SKIP]  $container — not running"
        continue
    fi

    printf "[GRADE] %-30s ... " "$container"

    # Run pytest as the student user; capture all output; never fail the script on test failure
    raw=$(docker exec -u "$username" "$container" \
        python3 -m pytest "$TESTS" --tb=no -q 2>&1 || true)

    # Parse summary line: "3 passed, 1 failed in 0.42s"
    passed=$(echo "$raw" | grep -oP '\d+(?= passed)' | tail -1 || echo 0)
    failed=$(echo "$raw" | grep -oP '\d+(?= failed)' | tail -1 || echo 0)
    passed=${passed:-0}
    failed=${failed:-0}

    # Participation assertion — 1 point for any nginx access log entry for this student
    # Only counted if the nginx RP container is running (no penalty if it's offline)
    if docker ps --format '{{.Names}}' | grep -q "^lab-nginx-rp$"; then
        if docker exec lab-nginx-rp grep -q "\"GET /${username} " /var/log/app/access.log 2>/dev/null; then
            passed=$(( passed + 1 ))
        else
            failed=$(( failed + 1 ))
        fi
    fi

    total=$(( passed + failed ))

    if [[ "$total" -eq 0 ]]; then
        pct="0.0"
        echo "NO RESULTS (pytest may have errored)"
    else
        pct=$(awk "BEGIN { printf \"%.1f\", ($passed / $total) * 100 }")
        echo "${passed}/${total} passed (${pct}%)"
    fi

    echo "${username},${period},${LAB_ID},${passed},${failed},${pct}" >> "$OUT"

done < "$ROSTER"

echo ""
echo "Compiled: $OUT"
column -t -s, "$OUT"

```

### An example of a student self-grader for Tier 3: 

```sh
#!/usr/bin/env bash
# check_dotfiles.sh — Lab 0.5 Tier 3 self-grader
#
# Run this on your personal machine after customizing your dotfiles.
# It clones the class default dotfiles for comparison, checks each
# requirement, and writes a grade report you submit to Schoology.
#
# Usage:
#   bash check_dotfiles.sh
#   bash check_dotfiles.sh --no-fetch    # skip cloning defaults (offline mode)
#
# Output: ~/grade_report_<username>.txt

set -euo pipefail

USERNAME="$(whoami)"
REPORT="$HOME/grade_report_${USERNAME}.txt"
LAB_ID="lab_0_5"
DEFAULT_REPO_URLS=(
    "https://github.com/Wm-Mason-Cyber/.dotFiles"
    "http://classroom.local/Wm-Mason-Cyber/dotFiles.git"  # local Gitea mirror fallback
)
DEFAULT_DIR="/tmp/.dotfiles_default_$$"
FETCH_DEFAULTS=1

[[ "${1:-}" == "--no-fetch" ]] && FETCH_DEFAULTS=0

PASSED=0
FAILED=0
declare -a RESULTS

pass() { PASSED=$(( PASSED + 1 )); RESULTS+=("  PASS  $1"); }
fail() { FAILED=$(( FAILED + 1 )); RESULTS+=("  FAIL  $1\n        → $2"); }
warn() { RESULTS+=("  WARN  $1"); }

# ── Fetch class defaults ──────────────────────────────────────────────────────
if [[ "$FETCH_DEFAULTS" -eq 1 ]]; then
    echo "Fetching class default dotfiles for comparison..."
    fetched=0
    for url in "${DEFAULT_REPO_URLS[@]}"; do
        if git clone --quiet "$url" "$DEFAULT_DIR" 2>/dev/null; then
            fetched=1
            break
        fi
    done
    if [[ "$fetched" -eq 0 ]]; then
        echo "WARNING: Could not clone default dotfiles. Running without baseline comparison."
        echo "         Re-run with network access, or ask your teacher for the offline bundle."
        FETCH_DEFAULTS=0
    fi
fi

cleanup() { [[ -d "$DEFAULT_DIR" ]] && rm -rf "$DEFAULT_DIR"; }
trap cleanup EXIT

# ── Helpers ───────────────────────────────────────────────────────────────────
has_cmd() { command -v "$1" &>/dev/null; }

dotfile_text() {
    local out=""
    [[ -f "$HOME/.bashrc" ]]       && out+=$'\n'"$(< "$HOME/.bashrc")"
    [[ -f "$HOME/.bash_aliases" ]] && out+=$'\n'"$(< "$HOME/.bash_aliases")"
    printf '%s' "$out"
}

# ── LOW COMPLEXITY (4 required) ───────────────────────────────────────────────

# 1. bat installed
if has_cmd bat || has_cmd batcat; then
    pass "bat installed"
else
    fail "bat installed" \
        "not in PATH. Debian: sudo apt install bat  |  Ubuntu: sudo apt install bat then sudo ln -sf /usr/bin/batcat /usr/local/bin/bat"
fi

# 2. eza installed
if has_cmd eza; then
    pass "eza installed"
else
    fail "eza installed" \
        "not in PATH. See install instructions in the lab guide (Tier 3 section)."
fi

# 3. PS1 customized
if [[ ! -f "$HOME/.bashrc" ]]; then
    fail "PS1 customized" "~/.bashrc not found"
else
    student_ps1=$(grep -m1 '^PS1=' "$HOME/.bashrc" 2>/dev/null || true)

    if [[ -z "$student_ps1" ]]; then
        fail "PS1 customized" "no PS1= line found in ~/.bashrc"
    elif [[ "$FETCH_DEFAULTS" -eq 1 && -f "$DEFAULT_DIR/.bashrc" ]]; then
        default_ps1=$(grep -m1 '^PS1=' "$DEFAULT_DIR/.bashrc" 2>/dev/null || true)
        if [[ "$student_ps1" == "$default_ps1" ]]; then
            fail "PS1 customized" "PS1 matches class default — edit ~/.bashrc and change it"
        else
            pass "PS1 customized"
        fi
    else
        pass "PS1 customized (baseline unavailable — verified presence only)"
    fi
fi

# 4. custom alias present
content="$(dotfile_text)"
alias_count=$(printf '%s' "$content" | grep -cP '^\s*alias\s+(?!cat=)' 2>/dev/null || true)
if [[ "${alias_count:-0}" -ge 1 ]]; then
    pass "custom alias in dotfiles ($alias_count found)"
else
    fail "custom alias in dotfiles" \
        "add at least one alias to ~/.bash_aliases and reload: source ~/.bashrc"
fi

# ── MEDIUM COMPLEXITY (2 required) ───────────────────────────────────────────

# 5. asciinema recording (.cast file) exists
cast_files=$(find "$HOME" -maxdepth 3 -name "*.cast" 2>/dev/null | head -3 || true)
if [[ -n "$cast_files" ]]; then
    count=$(echo "$cast_files" | wc -l)
    pass "asciinema recording exists ($count .cast file(s) found)"
else
    fail "asciinema recording exists" \
        "no .cast file found. Record a session: asciinema rec ~/my_session.cast"
fi

# 6. imagemagick resized image (560–960px wide) in home dir
if ! has_cmd identify; then
    fail "imagemagick resized image" \
        "'identify' not found. Install: sudo apt install imagemagick"
else
    img_found=0
    while IFS= read -r -d '' img; do
        raw_width=$(identify -format "%w" "$img" 2>/dev/null | awk '{print $1}' || true)
        width="${raw_width:-0}"
        if [[ "$width" -ge 560 && "$width" -le 960 ]]; then
            pass "imagemagick resized image ($(basename "$img"), ${width}px wide)"
            img_found=1
            break
        fi
    done < <(find "$HOME" -maxdepth 1 -type f \
        \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) -print0 2>/dev/null)

    if [[ "$img_found" -eq 0 ]]; then
        fail "imagemagick resized image" \
            "no image (560–960px wide) found in ~. Example: convert original.jpg -resize 840x ~/resized.jpg"
    fi
fi

# ── REPORT ────────────────────────────────────────────────────────────────────

TOTAL=$(( PASSED + FAILED ))
if [[ "$TOTAL" -gt 0 ]]; then
    PCT=$(awk "BEGIN { printf \"%.1f\", ($PASSED / $TOTAL) * 100 }")
else
    PCT="0.0"
fi

{
    printf '================================================================\n'
    printf '  Lab 1.1 — Get Comfy in the Command Line\n'
    printf '  Grading Report  |  %s  |  %s\n' "$USERNAME" "$(date '+%Y-%m-%d %H:%M')"
    printf '================================================================\n\n'
    for r in "${RESULTS[@]}"; do
        printf '%b\n' "$r"
    done
    printf '\n  Score: %d / %d assertions passed  (%s%%)\n' "$PASSED" "$TOTAL" "$PCT"
    printf '================================================================\n'
    printf '\nSubmit this file to Schoology: %s\n' "$REPORT"
} | tee "$REPORT"

```

### An example of a teacher grader for Tier 3: 

```sh
#!/usr/bin/env bash
# grade_compile_t3.sh — aggregate Tier 3 student reports into grades_report_t3.csv
#
# Workflow:
#   1. Students download check_dotfiles.sh, run it, get ~/grade_report_<username>.txt
#   2. They submit that file to the Schoology assignment
#   3. Teacher batch-downloads submissions into a folder
#   4. Run this script against that folder
#
# Usage:
#   ./grade_compile_t3.sh <reports_dir> students.csv
#   ./grade_compile_t3.sh ~/Downloads/lab1_submissions/ students.csv
#
# Output: grades_report_t3.csv

set -euo pipefail

REPORTS_DIR="${1:?Usage: $0 <reports_dir> students.csv}"
ROSTER="${2:?Usage: $0 <reports_dir> students.csv}"
LAB_ID="lab_0_5"
OUT="grades_report_t3.csv"

# Build username → period lookup from roster
declare -A period_of

while IFS=, read -r username _ _ _ period _; do
    username="${username//[$'\r\xef\xbb\xbf ']/}"
    [[ "$username" == "username" || -z "$username" ]] && continue
    period_of["$username"]="${period// /}"
done < "$ROSTER"

echo "username,period,lab_id,passed_assertions,failed_assertions,grade_percentage" > "$OUT"

for report in "$REPORTS_DIR"/grade_report_*.txt; do
    [[ -f "$report" ]] || continue

    filename="$(basename "$report")"
    username="${filename#grade_report_}"
    username="${username%.txt}"

    period="${period_of[$username]:-unknown}"

    passed=$(grep -c '^\s*PASS' "$report" 2>/dev/null || echo 0)
    failed=$(grep -c '^\s*FAIL' "$report" 2>/dev/null || echo 0)
    passed=${passed:-0}
    failed=${failed:-0}
    total=$(( passed + failed ))

    if [[ "$total" -eq 0 ]]; then
        pct="0.0"
    else
        pct=$(awk "BEGIN { printf \"%.1f\", ($passed / $total) * 100 }")
    fi

    echo "${username},${period},${LAB_ID},${passed},${failed},${pct}" >> "$OUT"
    printf "  %-20s  period %-3s  %d/%d  (%s%%)\n" "$username" "$period" "$passed" "$total" "$pct"
done

echo ""
echo "Compiled: $OUT"
echo ""
column -t -s, "$OUT"

```

