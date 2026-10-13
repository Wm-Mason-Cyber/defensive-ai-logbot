# Teacher Guide — Defensive AI & Automated Incident Response

This lab gives students a working, miniature Security Operations Center: a web
server under attack, a local LLM that recognizes the attack, and an automated
firewall response. It runs entirely on a student's Windows + WSL2 machine with
Docker Desktop and Ollama. No cloud, no API keys, no student-facing internet
after the one-time model pull.

## Learning objectives

Students will be able to:

1. Read structured (JSON) web-server access logs and distinguish normal traffic
   (`200`) from failed authentication (`401`) and blocked traffic (`403`).
2. Explain the **tiered SOC architecture** — cheap deterministic filters in
   front of an expensive AI tier — and why it's necessary at scale.
3. Describe an end-to-end **automated incident-response loop**: detect →
   decide → respond → enforce.
4. Reason about the trade-offs of using an LLM for security decisions
   (nuance and explanation vs. latency, cost, and false positives).

Maps naturally to AP Cybersecurity units on logging/monitoring, network
defense, incident response, and the ethics/limits of AI in security.

## Time & grouping

- ~60 minutes for Parts 0–4. Advanced explorations (Part 5) are a good second
  day or extension for fast finishers.
- Individual machines. The lab is identical for every student; there is no
  shared server, so there's no cross-student interference.

---

## One-time setup per machine

If your students' machines don't already have the toolchain, this is the full
list. (Many of your existing AP Cyber lab machines will already have Docker +
WSL.)

1. **WSL2 + a Linux distro** (Debian or Ubuntu). `wsl --install` on Windows.
2. **Docker Desktop**, with *Settings → Resources → WSL Integration* enabled
   for the distro.
3. **Ollama**: install from <https://ollama.com/download> (the Windows installer
   serves WSL too), then pull the model **once**:
   ```bash
   ollama pull llama3.2:3b
   ```
   This is a ~2 GB download. Do it ahead of class — see the air-gapped note
   below if your classroom router blocks it.
4. **Python 3 + the ollama client**:
   ```bash
   pip install ollama          # add --break-system-packages if pip refuses
   ```
5. **The lab**: clone this repo into each student's WSL home, or distribute it
   on a share. `git clone https://github.com/Wm-Mason-Cyber/defensive-ai-logbot.git`

Then have students run `./scripts/preflight.sh` — it checks all five items and
gives a specific fix hint for anything missing. **Preflight passing is a good
"machine is ready" gate before class.**

### Hardware

- A 6 GB GPU (e.g. RTX A2000) runs `llama3.2:3b` comfortably; first inference
  ~30 s (model load), then ~1–3 s each.
- **No GPU?** It still works on CPU, just slower (first answer can take a
  minute). If a machine is very slow, students can run the broker with
  `--no-ai` to demonstrate the deterministic tier while the GPU machines show
  the AI tier — or shorten the demo by raising `--suspect-threshold`.

### Air-gapped / locked-down classroom

The only step needing internet is pulling the model and the Docker base images
(`nginx:1.27-alpine`, `python:3.12-alpine`). To pre-stage on a machine with
internet and move offline:

```bash
# On a connected machine:
ollama pull llama3.2:3b
docker pull nginx:1.27-alpine && docker pull python:3.12-alpine
docker save nginx:1.27-alpine python:3.12-alpine -o lab-images.tar
# Ollama model blobs live in ~/.ollama (copy that dir to each machine)

# On each classroom machine:
docker load -i lab-images.tar
# restore ~/.ollama, then: ollama list  (should show llama3.2:3b)
```

After that the lab needs no network at all.

---

## How it works (so you can answer questions)

- **`docker-compose.yml`** starts three containers on an isolated bridge
  network: `web` (nginx target), `visitors` (normal traffic), `attacker`
  (brute-force bot). The containers only talk to each other.
- **`web/nginx.conf`** serves the site, protects `/admin/` with HTTP Basic auth
  (credentials in `web/htpasswd`), writes a JSON log to `logs/access.json`, and
  `include`s firewall rules from `firewall/`.
- **`web/firewall-watch.sh`** runs inside the web container and hot-reloads
  nginx whenever `firewall/blocklist.conf` changes. This is the *enforcement*
  half of the firewall — deliberately separate from the broker, mirroring how a
  real policy engine pushes rules to devices it doesn't run on.
- **`broker/soc_broker.py`** runs on the host (so it can reach the GPU-backed
  Ollama). It tails the log, drops `200`s, groups `401`s per IP per time
  window, sends a tiny JSON *summary* (never raw logs) to the model, parses the
  strict `[STATUS]/[ATTACKER_IP]/[EXPLANATION]` reply, and on `ALERT` writes a
  `deny` rule + an incident JSON in `alerts/`.
- A **deterministic threshold** (`--decide-threshold`, default 15) blocks a
  flood even if the AI is unavailable or returns junk, so the lab degrades
  gracefully. This is worth pointing out: the AI *augments* the defense, it
  isn't a single point of failure.

The broker has useful flags for live demos — `python3 broker/soc_broker.py --help`:
`--no-ai`, `--window`, `--suspect-threshold`, `--decide-threshold`, `--model`.

---

## Grading

The deliverable is a **screenshot + six short answers** (see
`docs/STUDENT_GUIDE.md`). This lab is about understanding, so grading is on the
explanations, not an automated test. Suggested 20-point rubric:

| Item | Points |
|------|-------:|
| Screenshot shows the AI `ALERT` verdict **and** the automated-block banner | 4 |
| Q1 — reads the log; identifies `src_ip`/`uri`; 401 vs 200 | 2 |
| Q2 — why drop the 200s (speed/cost at scale) | 2 |
| Q3 — interprets the AI's evidence | 2 |
| Q4 — traces all four tiers in order | 4 |
| Q5 — what AI adds vs. a fixed rule, and its risk (false positives) | 3 |
| Q6 — the 10k-req/s reflection + names a real sieve tool | 3 |

### Answer key (abbreviated)

- **Q1.** `401`s all come from the attacker container's IP (e.g. `172.21.0.x`),
  all targeting `/admin/`. A `401` shows `"status":401` and usually a `user`
  field from the guessed credentials; a `200` is a successful fetch of a normal
  page.
- **Q2.** `200`s are the overwhelming majority of traffic and carry no attack
  signal here. Sending them all to a ~1 s/call LLM would be impossibly slow and,
  in a paid/enterprise setting, hugely expensive. Cheap filters must shed volume
  first.
- **Q3.** Many failed logins from *one* IP in a *few seconds*, across *many
  different usernames*, all against the login endpoint, with an automated-looking
  `User-Agent` (`Python-urllib`). That pattern = scripted guessing, not a human
  mistyping once.
- **Q4.** (1) **Sieve** — Python keeps only `401`s. (2) **Correlate** — counts
  them per IP per window; one IP crosses the "suspect" threshold. (3) **Reason**
  — a compressed summary goes to the LLM, which returns `ALERT` + rationale.
  (4) **Respond** — broker writes `deny <ip>;` and an incident file; nginx's
  watch loop hot-reloads and the attacker now gets `403`.
- **Q5.** The AI can read context (username spread, timing, user-agent) and give
  a human-readable justification an analyst can review, and could spot subtler
  patterns a single count misses. Risks: it's slower, can be inconsistent, and
  may flag a legitimate burst (false positive) or be talked out of a real one.
  A fixed threshold is predictable but blind to context.
- **Q6.** 10,000 req/s × ~1 s/inference = a 10,000× backlog; the queue explodes
  and the system falls over (and, with a paid model, the bill does too). The
  tiered design sends only the tiny flagged fraction to the AI. Real "sieve"
  tools: Splunk / SPL, Vector, Cribl, a SIEM correlation-rule engine, or the
  WAF/firewall itself.

Advanced (Part 5) answers are open-ended; look for: understanding that catching
slow-and-low attacks requires **stateful memory across windows** (per-IP running
counters with decay), and that scaling means **streaming infrastructure**
(Kafka), **pattern stores** (vector DB / threat intel), and **dedicated
inference hardware** rather than one shared GPU.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `preflight.sh`: Docker not available | Start Docker Desktop; enable WSL integration for the distro. |
| `preflight.sh`: ollama server not reachable | Run `ollama serve`, or start the Ollama app. |
| Broker prints nothing after "window closed" for a long time | First inference loads the model (~30 s on GPU, longer on CPU). Be patient, or use `--no-ai` to demo the deterministic tier. |
| Broker never sees a window | Confirm containers are up (`docker ps`) and `logs/access.json` is growing (`tail -f logs/access.json`). |
| Attacker still getting 401, not 403, after a block | Check `docker logs lab-web | grep firewall` for the reload line; confirm `firewall/blocklist.conf` has a `deny` line. |
| Want a faster classroom demo | Lower `--window` to 2 and `--suspect-threshold` to 3. |
| Reset between runs | `./scripts/reset_lab.sh` clears logs, alerts, and firewall rules. |

## Resetting / cleaning up

- `./scripts/stop_lab.sh` — stop containers, keep this run's logs/alerts for review.
- `./scripts/reset_lab.sh` — wipe logs, alerts, and firewall rules back to empty.
- Images can be removed with `docker image rm nginx:1.27-alpine python:3.12-alpine`
  if you need the disk space back.
