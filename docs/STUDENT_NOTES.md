# Lab Notes & Reference — Defensive AI Lab

Keep this open in a second window while you work. It's a map of the lab plus a
cheat sheet of the commands you'll use. You don't need to memorize anything —
just come back here when you're unsure where something lives or how to look at
it.

---

## The big picture: two terminals, three containers, one AI

This lab has moving parts in a few places. You turn them on **one step at a
time**. Here's the whole thing on one page:

```
  YOUR WSL TERMINALS                        DOCKER (the fake "company network")
  ───────────────────                       ───────────────────────────────────
  Step 1: ./scripts/start_website.sh  ───▶  ┌─ web       (the website + /admin/)
  Step 3: ./scripts/start_visitors.sh ───▶  ├─ visitors  (fake normal users)
  Step 4: ./scripts/start_attacker.sh ───▶  └─ attacker  (fake password-guesser)
                                                      │
          Step 2: you, in a browser ──▶ web           │ every request is written to
                                                      ▼
                                                 logs/access.json
                                                      │
  Step 7: python3 broker/batch_logs.py  ◀────────────┤  (cuts the log into batches/)
  Step 8: python3 broker/soc_broker.py  ◀────────────┘  (batches + asks the AI)
                    │
                    ▼
  firewall/blocklist.conf  → web blocks the attacker
  (in Step 5, YOU write this file by hand)
```

**You typically have TWO terminal tabs open at once:** one to run commands, and
one watching the log with `tail -f` (or, in Step 8, running the AI broker).
That's normal and expected.

> ### ⚠️ The "attacker" is a script you started — remember to stop it
> There is no real hacker. The `attacker` container runs `traffic/attacker.py`,
> a program that fakes a password-guessing attack so you have something to
> defend against. It **keeps running until you stop it.** When you're done,
> always run `./scripts/stop_lab.sh` to shut the attacker (and the other
> containers) down. Don't leave it running after class.

---

## What's in the lab folder

Run `ls` to see the top level, or `tree -L 2` for the whole map. Here's what
each part is for:

```
defensive-ai-logbot/
├── docker-compose.yml     ← defines the 3 containers (you don't edit this)
├── scripts/               ← the helper commands you run
│   ├── preflight.sh          check your machine is ready
│   ├── start_website.sh      Step 1: start the website only
│   ├── start_visitors.sh     Step 3: add the normal-traffic script
│   ├── start_attacker.sh     Step 4: add the attacker script
│   ├── run_lab.sh            shortcut: Steps 1+3+4 all at once
│   ├── check_progress.py     "where am I / what's next?"  (run anytime)
│   ├── stop_lab.sh           STOP the lab  ← don't forget this!
│   └── reset_lab.sh          wipe logs/alerts/batches to start fresh
├── broker/
│   ├── batch_logs.py      ← Step 7: cuts the log into 3 batch files (no AI)
│   └── soc_broker.py      ← Step 8: the Defensive AI
├── traffic/
│   ├── legit_users.py        the "normal visitors" script
│   └── attacker.py           the "attacker" script  ← this is the fake threat
├── web/                   ← the website being attacked (config + pages)
├── logs/                  ← ★ WHERE THE ACTION IS LOGGED ★
│   ├── access.json           every web request, one JSON line each
│   └── error.log             web server errors
├── batches/               ← batch_1/2/3.jsonl, written by batch_logs.py
├── firewall/
│   └── blocklist.conf        block rules (you write one in Step 5; the AI in Step 8)
├── alerts/                ← incident files the AI writes when it blocks someone
└── docs/                  ← the guides (including this one)
```

### The three places worth watching

| You want to see… | Look here |
|------------------|-----------|
| Every request hitting the website (the live action) | `logs/access.json` |
| Who is blocked (by you or the AI) | `firewall/blocklist.conf` |
| The log cut into small pieces | `batches/batch_*.jsonl` |
| The AI's incident reports | `alerts/incident_*.json` |

---

## Reading the log

`logs/access.json` has **one JSON object per line** — one line per web request.
A single line looks like this (pretty-printed here; in the file it's one line):

```json
{"ts":"2026-10-13T12:30:53+00:00","src_ip":"172.21.0.4","method":"GET",
 "uri":"/admin/","status":401,"user":"root","ua":"Python-urllib/3.12", ...}
```

What the fields mean:

| Field | Meaning | What to notice |
|-------|---------|----------------|
| `src_ip` | who made the request | the attacker is always the **same** IP; *you* show up as the gateway, usually ending in `.1` |
| `uri` | what they asked for | `/admin/` = the protected login |
| `status` | how the server answered | **200** = OK · **401** = login failed · **403** = BLOCKED |
| `user` | the username they tried | the attacker cycles through `root`, `admin`, …; yours is `student` |
| `ua` | the "user agent" (browser/tool) | the scripts' is `Python-urllib`, yours is your browser (or `curl`) |

The whole lab is really just the story of those `status` numbers: lots of
`401`s from one IP → someone notices (you in Step 4, the AI in Step 8) → that
IP starts getting `403`.

### Logins for the admin console

| Username | Password | Who |
|----------|----------|-----|
| `student` | `Defend2026!` | **you** (Step 2) |
| `alice`, `bob`, `intern` | (secret) | the fake staff the visitor script logs in as |

---

## Command cheat sheet

You only need a handful of commands. `cd` into the lab folder first
(`cd ~/defensive-ai-logbot`).

### Moving around and looking at files

| Command | What it does |
|---------|--------------|
| `pwd` | print working directory — "where am I?" |
| `cd ~/defensive-ai-logbot` | change into the lab folder |
| `cd ..` | go up one folder |
| `ls` | list files here |
| `ls -la logs` | list everything in `logs/`, with details |
| `tree -L 2` | draw the folder as a tree (2 levels deep)¹ |
| `cat firewall/blocklist.conf` | dump a whole (small) file to the screen |
| `less logs/access.json` | scroll through a big file (arrows; press `q` to quit) |

### Watching the log live  ← you'll use this a lot

| Command | What it does |
|---------|--------------|
| `tail logs/access.json` | show the **last few** lines of the log |
| `tail -f logs/access.json` | **follow** the log — new lines appear as they happen |
| *(press `Ctrl-C`)* | stop following and get your prompt back |
| `grep '"status":401' logs/access.json` | show only the failed-login lines |
| `grep '"status":403' logs/access.json` | show only the blocked lines |
| `wc -l logs/access.json` | count the lines (requests) in the log |
| `grep '"status":401' logs/access.json \| grep -v student \| cut -c8-26 \| uniq -c` | failed logins per second: shows the attack bursts |

> `tail -f` is "live mode" — it keeps running and printing until you press
> `Ctrl-C`. That's not an error; it's waiting for the next log line.

> ¹ If `tree` says "command not found," install it once with
> `sudo apt install tree`, or just use `ls` — you don't need `tree` for the lab.

### Running the lab

| Command | What it does |
|---------|--------------|
| `./scripts/preflight.sh` | check the machine is ready (run first) |
| `./scripts/start_website.sh` | Step 1: start the website (also wipes old logs) |
| `./scripts/start_visitors.sh` | Step 3: add normal traffic |
| `./scripts/start_attacker.sh` | Step 4: add the attacker |
| `echo 'deny <ip>;' >> firewall/blocklist.conf` | Step 5: block an IP by hand |
| `nano firewall/blocklist.conf` | Step 5: delete your rule (`Ctrl-O` `Enter` saves, `Ctrl-X` exits) |
| `python3 broker/batch_logs.py` | Step 7: cut the log into 3 batch files |
| `python3 broker/soc_broker.py` | Step 8: run the Defensive AI |
| `./scripts/run_lab.sh` | shortcut: start all 3 containers at once |
| `python3 scripts/check_progress.py` | see which steps are done + what's next |
| `./scripts/stop_lab.sh` | **stop the lab (and the attacker!)** |
| `./scripts/reset_lab.sh` | clear logs/alerts/batches to start over |

### Peeking at the containers (optional, for the curious)

| Command | What it does |
|---------|--------------|
| `docker ps` | list the running containers (`lab-web`, `lab-visitors`, `lab-attacker`) |
| `docker logs lab-attacker` | see what the attacker script is printing |
| `docker logs lab-web | grep firewall` | see the web server reload its block rules |

---

## Keyboard survival kit

| Keys | Does |
|------|------|
| `Ctrl-C` | stop the program running in this terminal (the broker, or `tail -f`) |
| `↑` / `↓` | scroll through commands you've already typed |
| `Tab` | auto-complete a file or folder name you've started typing |
| `clear` | clear the screen |
| `q` | quit out of `less` or a man page |

---

## "Something's weird" — quick answers

- **The broker just sits there after "window closed."** The first AI answer
  takes ~30 seconds while the model loads. Wait for it. After the first one,
  it's fast.
- **`tail -f` won't give my prompt back.** That's normal — it's live. Press
  `Ctrl-C`.
- **`./scripts/...` says permission denied.** Run it with `bash` in front, e.g.
  `bash scripts/start_website.sh`.
- **The browser won't ask for the admin password again.** It remembered your
  login. Use a private/incognito window and close it to "log out," or use the
  `curl` commands in Step 2.
- **I blocked myself (the `.1` IP) by accident.** `nano firewall/blocklist.conf`,
  delete that line, save. The site comes back within a second.
- **I'm lost / not sure what's done.** Run `python3 scripts/check_progress.py`.
- **I want a clean slate.** `./scripts/stop_lab.sh` then `./scripts/reset_lab.sh`.
- **Is the attacker still running?** `docker ps` — if you see `lab-attacker`,
  yes. Stop it with `./scripts/stop_lab.sh`.
