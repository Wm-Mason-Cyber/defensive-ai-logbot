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
4. Explain why raw logs can't be handed to an LLM (volume vs. **context
   window**) and how **batching + sieving + summarizing** solve that.
5. Reason about the trade-offs of using an LLM for security decisions
   (nuance and explanation vs. latency, cost, and false positives), and its
   impact on SOC analyst work.

Maps naturally to AP Cybersecurity units on logging/monitoring, network
defense, incident response, and the ethics/limits of AI in security.

## Time & grouping

- ~90 minutes for Steps 0–8; two class periods works well. A natural break
  is after Step 5 (stop the lab; on day 2, `./scripts/run_lab.sh` brings back
  website + visitors + attacker in one command before Step 6).
- The steps add one component at a time so students do each job **by hand**
  before the AI automates it:

  | Step | Adds | Student does by hand |
  |------|------|----------------------|
  | 1 | `web` only (`start_website.sh`) | explore the site |
  | 2 | — | generate 200 / 401 / 200-login and find them in `logs/access.json` |
  | 3 | `visitors` (`start_visitors.sh`) | measure log growth; tell own lines from scripted ones |
  | 4 | `attacker` (`start_attacker.sh`) | find the 401 bursts and the attacker IP |
  | 5 | — | write, then delete, a `deny` rule; watch 401 → 403 → 401 |
  | 6 | — | reading: log size vs. context window; read `broker/batch_logs.py` |
  | 7 | — | run `broker/batch_logs.py` → 3 batch files in `batches/` |
  | 8 | broker + LLM (`soc_broker.py`) | watch it all happen automatically; reflect |

- Advanced explorations are a good extension for fast finishers.
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

- **`docker-compose.yml`** defines three containers on an isolated bridge
  network: `web` (nginx target), `visitors` (normal traffic), `attacker`
  (brute-force bot). The `start_*.sh` scripts bring them up one at a time;
  `run_lab.sh` starts all three. The containers only talk to each other.
- **`web/nginx.conf`** serves the site, protects `/admin/` with HTTP Basic auth
  (credentials in `web/htpasswd`, including the student account
  `student` / `Defend2026!`), writes a JSON log to `logs/access.json`, and
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
- **`broker/batch_logs.py`** (Step 7) runs the broker's core loop with the AI
  removed: it imports `follow`, `is_failed_login`, and `compress` from
  `soc_broker.py`, cuts the live log into three 5-second windows, writes each
  to `batches/batch_N.jsonl`, and prints the sieve counts and the summary the AI
  would receive.
- A **deterministic threshold** (`--decide-threshold`, default 15) blocks a
  flood even if the AI is unavailable or returns junk, so the lab degrades
  gracefully. This is worth pointing out: the AI *augments* the defense, it
  isn't a single point of failure.

The broker has useful flags for live demos — `python3 broker/soc_broker.py --help`:
`--no-ai`, `--window`, `--suspect-threshold`, `--decide-threshold`, `--model`.

---

## Student self-check (cuts down "it's not working" questions)

Students can run `python3 scripts/check_progress.py` at any time. It's
read-only and checks each step that leaves evidence behind, labeled with the
guide's step number (Step 6 is reading only, so it isn't checked):

- **2** a non-script request (any user agent other than `Python-urllib`) with a
  200 on a page, a 401 on `/admin/`, and a 200 on `/admin/`
- **3** `lab-visitors` up and a staff login (`alice`/`bob`/`intern`) logged
- **4** a scripted 401 in the log
- **5** a 403 logged *before* the broker's first incident (i.e. from the
  student's own rule), and the rule since removed
- **7** `batches/batch_*.jsonl` exist
- **8** an incident file, a `deny` rule, and 403s after the incident

It marks the step they're on with the exact next command. It only checks that
they *ran* the lab, not their written answers. Point stuck students here first.
Most "nothing is happening" cases in Step 8 are the ~30 s first AI inference.

## Grading

The deliverable is **two screenshots + twelve short answers** (see
`docs/STUDENT_GUIDE.md`). This lab is about understanding, so grading is on the
explanations, not an automated test. The Step 8 reflection (Q8–Q12) carries the
most weight. Suggested 40-point rubric:

| Item | Points |
|------|-------:|
| Screenshot 1 (Step 5): manual `deny` rule + attacker `403`s | 2 |
| Screenshot 2 (Step 8): AI `ALERT` verdict **and** automated-block banner | 2 |
| Q1 — explored the site; describes the `/admin/` prompt and 401 page | 1 |
| Q2 — log path; own 200/401 lines; gateway `src_ip`; `status`/`user`/`ua` differences | 3 |
| Q3 — log growth rate; distinguishes own lines by `ua`/`src_ip`; finds a staff login | 2 |
| Q4 — attacker IP; burst pattern; usernames; how it differs from one human 401 | 3 |
| Q5 — 401→403→401; visitors unaffected; humans can't do this 24/7 at scale | 3 |
| Q6 — token/line math; minutes to fill the window; ≥2 reasons raw logs can't go to the AI | 3 |
| Q7 — batch table; empty batches skip the AI; summary vs. raw; split-burst problem | 3 |
| Q8 — interprets the AI's evidence; compares with own Step 4 reasoning | 3 |
| Q9 — full chain in order, each link tied to the step done by hand | 4 |
| Q10 — SOC jobs: what's automated vs. still human; replace vs. change | 4 |
| Q11 — ≥1 strength, ≥2 weaknesses; explains the backup threshold | 4 |
| Q12 — two specific, justified improvements | 3 |

### Answer key (abbreviated)

- **Q1.** Home/About/News/Products load normally. `/admin/` pops a
  username/password box (HTTP Basic auth); Cancel shows a "401 Authorization
  Required" page.
- **Q2.** `logs/access.json` (inside the container it's `/var/log/lab/access.json`,
  bind-mounted). (a) `src_ip` is the Docker bridge gateway, typically
  `172.x.0.1`, not the laptop's real address. (b) The failure is
  `"status":401`, the success `"status":200`, both with `"user":"student"` (or
  whatever username was typed). A Cancel gives `"user":""`. (c) `ua` is the
  browser's user agent (or `curl/x.y`).
- **Q3.** (a) Roughly 50–100 lines/min from the visitor script (varies).
  (b) The student's lines have a browser/curl `ua` and the `.1` gateway IP; the
  visitors' have `Python-urllib/3.12` and a container IP (`172.x.0.3`-ish).
  (c) e.g. `"user":"alice"`, `"status":200` on `/admin/`.
- **Q4.** (a) A container IP like `172.x.0.4`. (b) About 12 failed logins
  over ~3 s (3–4 per second), then ~8 s of quiet. (c) `root`, `admin`,
  `administrator`, `test`, `oracle`, `guest`. (d) Many failures, fast, from one
  IP, many usernames, a script user agent; a human fails once or twice with
  their own username.
- **Q5.** (a) 401 → 403 → 401. (b) No. The rule denies only the attacker's IP;
  visitors come from a different IP. (c) Answers should note round-the-clock
  coverage, reaction time, volume, fatigue/human error, and that attackers
  change IPs.
- **Q6.** (a) A line is ~150 characters ÷ 4 ≈ 35–40 tokens (in practice JSON
  tokenizes worse, closer to 60), so ~70–100 lines fill 4,000 tokens. (b) With
  ~50–100 lines/min, about 1–2 minutes. (c) Volume far exceeds any context window; each call takes
  ~1 s+ so it can't keep up; cost; most lines are irrelevant noise that dilutes
  the signal; big prompts are slower and less accurate.
- **Q7.** (a) Varies, e.g. 16 lines/12×401, 4/0, 13/8. (b) No. A batch with
  no failed logins (or fewer than the suspect threshold) is never sent to the AI.
  (c) A batch of dozens of ~150-char lines becomes a one-line summary; counts,
  usernames, path, and user agent are kept, while individual timestamps,
  visitor traffic, and byte counts are dropped. (d) Each half may fall below
  the threshold, so the attack is missed or delayed. This is the root of the
  "slow-and-low" problem and the reason for memory across windows.
- **Q8.** Many failed logins from *one* IP in a *few seconds*, across *many
  different usernames*, all against `/admin/`, with an automated `User-Agent`
  (`Python-urllib`). That's the same pattern the student saw by hand with `grep`
  and `uniq -c` in Step 4.
- **Q9.** Attacker sends 401s (Step 4 observed) → broker tails the log and
  batches it into 5 s windows (Steps 6–7) → **sieve** keeps only `/admin` 401s,
  grouped per IP (Step 4 `grep` / Step 7) → **correlate**: one IP crosses the
  suspect threshold (Step 4 burst count) → **reason**: compressed summary to the
  LLM, which returns `ALERT` (Step 4 "that's an attack" judgment) → **respond**:
  `deny <ip>;` + incident file (Step 5 `echo`) → **enforce**: nginx hot-reloads
  and the attacker gets 403 (Step 5 `docker logs lab-web`, `grep 403`).
- **Q10.** Automated: watching, triage of the obvious, the block itself.
  Still human: setting thresholds/prompts, reviewing incidents in `alerts/`,
  handling false positives and unblocks, investigating what the attacker
  touched, tuning for new attacks, accountability. Strong answers argue the job
  shifts from staring at logs toward supervising and tuning automation and
  handling the hard cases.
- **Q11.** Strengths: speed, 24/7, readable explanation, cheap because the
  AI sees only a tiny fraction. Weaknesses: false positives (locking out a real
  user), false negatives, inconsistency, slow-and-low attacks slip between
  windows, easily spoofed signals (user agent), attacker rotates IPs, block is
  permanent with no review. The backup threshold means defense doesn't depend
  on the AI being up or parseable: the AI augments, it isn't a single point of
  failure.
- **Q12.** Any two well-justified improvements: per-IP memory across windows
  with decay; auto-expiring blocks; human approval before blocking (or for
  borderline cases); richer context (geo/reputation, success-after-failures);
  alerting/ticketing; rate-limiting instead of hard blocks; allow-listing known
  staff IPs.

Advanced answers are open-ended. Look for an understanding that catching
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
| Student locked themselves out (blocked the `.1` gateway IP in Step 5) | Delete that line from `firewall/blocklist.conf`; nginx reloads within ~1 s. |
| Step 8 broker says "already blocked; no action" | The student's Step 5 rule is still there. Remove it (or `cp firewall/blocklist.conf.template firewall/blocklist.conf`). |
| Browser never re-prompts for the admin password | Basic auth credentials are cached. Use a private window, or the `curl` commands in Step 2. |
| Broker never sees a window | Confirm containers are up (`docker ps`) and `logs/access.json` is growing (`tail -f logs/access.json`). |
| Attacker still getting 401, not 403, after a block | Check `docker logs lab-web | grep firewall` for the reload line; confirm `firewall/blocklist.conf` has a `deny` line. |
| Want a faster classroom demo | Lower `--window` to 2 and `--suspect-threshold` to 3. |
| Reset between runs | `./scripts/reset_lab.sh` clears logs, alerts, and firewall rules. |

## Resetting / cleaning up

- `./scripts/stop_lab.sh` — stop containers, keep this run's logs/alerts for review.
- `./scripts/reset_lab.sh` — wipe logs, alerts, batches, and firewall rules back to empty.
  (`start_website.sh` and `run_lab.sh` do this automatically.)
- Images can be removed with `docker image rm nginx:1.27-alpine python:3.12-alpine`
  if you need the disk space back.
