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

The lab is built up one piece at a time, so students do each job **by hand**
before the AI automates it:

1. `./scripts/start_website.sh` — start just the website and explore it.
2. Find their own traffic in `logs/access.json`: `200` pages, a failed `401`
   login, and a successful `200` login as `student` / `Defend2026!`.
3. `./scripts/start_visitors.sh` — add scripted "regular traffic" and watch the
   log grow.
4. `./scripts/start_attacker.sh` — add the scripted attacker and find its
   `401` bursts.
5. Block the attacker **by hand** with a `deny` rule, watch `401` → `403`, then
   remove the rule.
6. Reflect: the log grows fast, and an AI's context window is small. Read the
   heart of the batching loop.
7. `python3 broker/batch_logs.py` — cut the live log into 3 batch files and
   see what the sieve keeps.
8. `python3 broker/soc_broker.py` — the Defensive AI does Steps 4–7 on its own
   and firewalls the attacker. Big-picture reflection on AI in the SOC.

Full instructions and questions: `docs/STUDENT_GUIDE.md`. Stuck at any point?
`python3 scripts/check_progress.py` is a read-only checker that shows which
steps are done and spells out the next command.

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
broker/soc_broker.py      the Defensive AI SOC broker (Step 8)
broker/batch_logs.py      the broker's batching loop without the AI (Step 7)
firewall/                 blocklist the broker writes; nginx enforces it
logs/  alerts/  batches/  runtime output (JSON access log; incident records; batch files)
scripts/                  preflight, start_website/visitors/attacker, run_lab (all at once),
                          stop / reset, check_progress
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
