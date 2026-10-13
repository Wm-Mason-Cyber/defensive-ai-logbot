# Defensive AI & Automated Incident Response

A self-contained AP Cybersecurity lab. Students stand up a small enterprise
network in Docker, point a **local AI model** at its logs, and watch an
automated Security Operations Center (SOC) detect a brute-force attack and
**firewall the attacker on its own** — the same tiered design real SOCs use to
keep AI fast and cheap.

Everything runs on a student's Windows + WSL2 machine. No cloud, no API keys,
no internet needed after setup.

```
  ┌────────────┐  failed logins   ┌──────────────┐   JSON log   ┌──────────────┐
  │  attacker  │ ──────────────▶ │   web (nginx)│ ───────────▶ │  SOC broker  │
  │ (container)│    (HTTP 401)    │  /admin/     │   (tail)     │  (host + AI) │
  └────────────┘                  └──────────────┘              └──────┬───────┘
         ▲                               ▲                             │
         │        403 Forbidden          │   deny <ip>;  (hot-reload)  │ writes rule
         └───────────────────────────────┴─────────────────────────────┘
                              automated response
```

## What a student does

1. `./scripts/preflight.sh` — confirm Docker, Ollama, and the model are ready.
2. `./scripts/run_lab.sh` — start the target site, normal visitors, and the attacker.
3. `python3 broker/soc_broker.py` — run the defensive AI in a second terminal.
4. Watch the broker filter the log firehose, ask the AI about the suspicious
   burst, and write a firewall rule. Confirm the attacker starts getting `403`.
5. Screenshot the block + answer the review questions (see `docs/STUDENT_GUIDE.md`).

Stuck at any point? `python3 scripts/check_progress.py` is a read-only checker
that shows which of the 7 run steps are done and spells out the next command.

## The idea the lab teaches

A web server can emit thousands of log lines a second. An LLM takes ~1 second
per answer. You cannot — and should not — ask the AI about every request. So
the broker works in tiers, which is exactly how production SOCs (Splunk,
Vector, Cribl, SIEM rule engines) are built:

| Tier | Tool | Job | Volume handled |
|------|------|-----|----------------|
| 1. Sieve | plain Python | drop all normal `200`s, keep only `401`s | ~99.9% |
| 2. Correlate | counters per IP/window | flag IPs over a threshold | the suspicious few |
| 3. Reason | local LLM (llama3.2:3b) | "is this really an attack?" + explain | a handful/minute |
| 4. Respond | write `deny` rule | block the IP, log an incident | confirmed threats |

The AI is the *expensive, smart* tier you protect with cheap filters — and a
deterministic threshold still blocks egregious floods if the model is slow or
unavailable, so the defense never depends on the AI alone.

## Layout

```
docker-compose.yml        the 3-container lab network
web/                      nginx target: site, /admin/ console, JSON logs, firewall reload
  nginx.conf  htpasswd  html/  firewall-watch.sh
traffic/                  simulated actors
  legit_users.py  attacker.py
broker/soc_broker.py      the Defensive AI SOC broker (students run this)
firewall/                 blocklist the broker writes; nginx enforces it
logs/  alerts/            runtime output (JSON access log; incident records)
scripts/                  preflight / run / stop / reset + check_progress helpers
docs/STUDENT_GUIDE.md     student-facing lab instructions + questions
docs/STUDENT_NOTES.md     student reference: folder map, log fields, command cheat sheet
docs/TEACHER_GUIDE.md     setup, grading, troubleshooting, answer key
```

## Requirements

- Windows 10/11 with **WSL2** and a Linux distro (Debian/Ubuntu)
- **Docker Desktop** with WSL integration enabled
- **Ollama** with `llama3.2:3b` pulled (~2 GB). A 6 GB GPU runs it comfortably;
  CPU-only works but inference is slower.
- Python 3 with the `ollama` package (`pip install ollama`)

See `docs/TEACHER_GUIDE.md` for a full setup walkthrough and an offline/air-gapped
classroom note.
