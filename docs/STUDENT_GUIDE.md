# Student Lab Guide — Defensive AI & Automated Incident Response

**Time:** ~60 minutes · **Submit:** one screenshot + answers to 6 questions

> **Keep the Lab Notes handy** (`docs/STUDENT_NOTES.md`, or the Notes tab in the
> class Doc). It has a map of the folder, what each log field means, and a
> cheat sheet of every command below (`cd`, `ls`, `tail -f`, etc.).

---

## The scenario

You are the security engineer for *Acme Corp*. Your public website has a
staff-only admin console at `/admin/`. Attackers constantly try to guess staff
passwords by hammering that console — this is a **credential brute-force
attack**, and it shows up in the logs as a flood of `401 Unauthorized`
responses.

Your job: build an automated defender. It will read the web server's logs, use
a **local AI model** to recognize an attack in progress, and **automatically
block the attacker's IP** at the firewall — no human in the loop.

You will not write the whole system from scratch; it's provided. Your job is to
**run it, understand each tier, observe it working, and explain why it's built
this way.** The advanced section lets you modify it.

---

## Part 0 — Setup (once)

Open your WSL terminal and move into the lab folder:

```bash
# incase you need an update or git
sudo apt update && sudo apt upgrade -y && sudo apt install git -y

# download the lab and run automated setup
git clone https://github.com/Wm-Mason-Cyber/defensive-ai-logbot ~/defensive-ai-logbot
cd ~/defensive-ai-logbot
./scripts/preflight.sh
```

Every line should show a green ✓. If something fails, follow the `→` hint or
ask your teacher. **Do not continue until preflight passes.**

> **Stuck at any point in this lab?** Run the progress checker:
> ```bash
> python3 scripts/check_progress.py
> ```
> It's read-only and safe to run as often as you like. It shows which steps
> you've completed, marks the one you're on (`▶ ← you are here`), and gives you
> the exact command to try next. Use it whenever you're not sure a step worked.

---

## Part 1 — Start the environment

```bash
./scripts/run_lab.sh
```

This starts three containers:

- **web** — the Acme Corp site (nginx). Browse it: open <http://localhost:8080>.
  Try the staff console at <http://localhost:8080/admin/> — you'll be asked for
  a password you don't have. Click *Cancel*; that failed attempt is a `401`.
- **visitors** — simulated normal employees and visitors browsing the site and
  logging in correctly. This is the harmless background noise.
- **attacker** — a bot repeatedly guessing admin passwords. This is the threat.

> **Important — there is no real hacker here.** The "attacker" is a script
> (`traffic/attacker.py`) running in a container that *you* just started. It
> fakes a password-guessing attack so you have something to defend against. It
> will **keep attacking until you shut it down**, so don't forget Part 4's
> `./scripts/stop_lab.sh` when you finish. Same goes for the "visitors" — also
> a script, playing the role of normal users.

Peek at the raw log the web server is writing (one JSON object per request):

```bash
tail -f logs/access.json
```

You'll see a mix of `"status":200` (normal) and `"status":401` (failed logins).
Press `Ctrl-C` to stop watching.

> **Q1.** Open `logs/access.json` and find a few `401` entries. What is the
> `src_ip`, and what `uri` is being targeted? How is a `401` entry visibly
> different from a normal `200` entry?

---

## Part 2 — Launch the Defensive AI

Leave the lab running. In the **same terminal**, start the broker:

```bash
python3 broker/soc_broker.py
```

Watch its output. Within a few seconds it reports a "window closed" with a
count of failed logins from one IP, then sends a small summary to the AI. The
**first** AI answer takes ~30 seconds (the model is loading into your GPU);
after that it's fast.

When the AI returns `[STATUS] ALERT`, the broker writes a firewall rule and an
incident file, and prints a big `*** [AUTOMATED RESPONSE] blocked ... ***`
banner.

> **Q2.** The broker prints a line like `sieve: kept N failed-login events,
> dropped M normal events`. Why does the broker throw away the `200` events
> instead of sending them to the AI? (Hint: think about speed and cost at
> enterprise scale — see the table in the README.)

> **Q3.** Copy the AI's three-line verdict (`[STATUS]` / `[ATTACKER_IP]` /
> `[EXPLANATION]`). In your own words, what evidence did the summary give the
> AI that pointed to an attack rather than a forgetful employee?

---

## Part 3 — Confirm the automated response worked

The broker only *wrote a rule to a file*. Something else has to *enforce* it.
Check that the web server picked it up and is now blocking the attacker:

```bash
cat firewall/blocklist.conf          # you should see a 'deny <ip>;' line
docker logs lab-web | grep firewall  # '...reloaded nginx (1 active rules)'
docker logs lab-attacker | tail -5   # the attacker notices it's been blocked
```

The attacker's requests now return `403 Forbidden` instead of `401`. Confirm it
in the log:

```bash
grep '"status":403' logs/access.json | tail -3
```

> **Q4.** Trace the full chain of events, in order, from the attacker's failed
> login to it being blocked. Name each of the four tiers (sieve, correlate,
> reason, respond) and what each one did.

> **Q5.** The broker also works with a `--no-ai` flag, which blocks purely on a
> count threshold. What does the AI tier *add* that a simple "block after 15
> failures" rule does not? What might it get *wrong* that a fixed rule wouldn't?

---

## Part 4 — Submit

First, confirm you finished every step — this should show all 7 green:

```bash
python3 scripts/check_progress.py
```

1. **Screenshot:** your broker terminal showing the `[STATUS] ALERT` verdict and
   the `*** [AUTOMATED RESPONSE] blocked ... ***` banner. Make sure the attacker
   IP and the AI explanation are visible.
2. **Answers:** Q1–Q5 above, plus Q6 below.

> **Q6 (reflection).** A real website might get 10,000 requests per *second*. If
> every request went to an AI model that takes 1 second to answer, what would
> happen? Explain how the tiered design in this lab avoids that problem, and
> name one real tool a company might use for the "sieve" tier.

### ⚠️ When you're done — SHUT THE LAB DOWN

The attacker and visitor scripts keep running in the background until you stop
them. Always shut the lab down when you finish so nothing is left hammering the
web server after class:

```bash
# 1. In your broker terminal, press Ctrl-C to stop the Defensive AI.
# 2. Then stop all the containers (this stops the attacker too):
./scripts/stop_lab.sh
```

Double-check nothing is still running:

```bash
docker ps        # you should NOT see lab-web, lab-visitors, or lab-attacker
```

---

## Part 5 — Advanced explorations (optional, for extra credit)

Run `./scripts/reset_lab.sh` between experiments to start clean.

- **Tune the window.** Edit the `--window` or `--suspect-threshold` values
  (run `python3 broker/soc_broker.py --help`). What happens to detection speed
  and false alarms if the window is 1 second vs. 30 seconds?
- **Slow-and-low attack.** The attacker bursts fast. Edit `traffic/attacker.py`
  and raise `ATTACK_GAP` so guesses are spaced *minutes* apart. Can the broker
  still catch it? What would you have to change about how the broker *remembers*
  past windows to catch a slow attacker? (You don't have to build it — describe
  the design.)
- **Trick the AI.** Change the attacker's `User-Agent` or usernames to look more
  "human." Does the model still flag it? Where is the line between a cautious
  defender and one that cries wolf?
- **Scale it up.** Write a short paragraph: to defend 50,000 requests/second,
  what hardware and architecture would you add (think: streaming tools like
  Kafka, a vector database of known-bad patterns, dedicated inference GPUs)?
