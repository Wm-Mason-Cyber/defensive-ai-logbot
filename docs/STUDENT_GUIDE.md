# Student Lab Guide — Defensive AI & Automated Incident Response

**Time:** ~90 minutes (two class periods works well) · **Submit:** two
screenshots + answers to the questions in each step

> **Keep the Lab Notes handy** (`docs/STUDENT_NOTES.md`, or the Notes tab in the
> class Doc). It has a map of the folder, what each log field means, and a
> cheat sheet of every command below (`cd`, `ls`, `tail -f`, etc.).

---

## The scenario

You are the security engineer for *Acme Corp*. Your public website has a
staff-only admin console at `/admin/`. Attackers constantly try to guess staff
passwords by hammering that console. This is a **credential brute-force
attack**.

You'll build up to an automated defender **one piece at a time**:

| Step | What you add | What you learn |
|------|--------------|----------------|
| 1 | the website, alone | what's being defended |
| 2 | *your own* visits | where logs live and how to read them |
| 3 | normal visitors (a script) | what "normal" looks like, and how fast logs grow |
| 4 | an attacker (a script) | what an attack looks like in a log |
| 5 | a firewall rule *you* write | how blocking works, by hand |
| 6 | (reading) | why a human, or an AI, can't read the whole log |
| 7 | the batching script | how the log is cut into bite-size pieces |
| 8 | the Defensive AI | the whole system defending itself |

Each step builds on the one before it. **Don't skip ahead.** Step 8 only makes
sense once you've done Steps 1–7 yourself.

> **Stuck at any point?** Run the progress checker:
> ```bash
> python3 scripts/check_progress.py
> ```
> It's read-only and safe to run as often as you like. It shows which steps
> you've completed, marks the one you're on (`▶ ← you are here`), and gives you
> the exact command to try next.

---

## Step 0 — Setup (once)

Open your WSL terminal and run:

```bash
# in case you need an update or git
sudo apt update && sudo apt upgrade -y && sudo apt install git -y

# download the lab and check your machine is ready
git clone https://github.com/Wm-Mason-Cyber/defensive-ai-logbot ~/defensive-ai-logbot
cd ~/defensive-ai-logbot
./scripts/preflight.sh
```

Every line should show a green ✓. If something fails, follow the `→` hint or
ask your teacher. **Do not continue until preflight passes.**

---

## Step 1 — Start the website and explore it

```bash
./scripts/start_website.sh
```

This starts **one** container, `web`, the Acme Corp website. Nothing else is
running, so nobody is visiting the site except you.

Open <http://localhost:8080> in your browser and click around: Home, About,
News, Products. Then try the **Staff login** (`/admin/`). Your browser pops up
a username/password box. You don't have an account yet, so click **Cancel**.

> **Q1.** List the pages you visited. What happened when you went to
> `/admin/`? What did the page say after you clicked Cancel?

---

## Step 2 — Find your own traffic in the logs

Every time you load a page, the web server writes **one line** to a log file.
The server runs inside a container, but the log is shared out to your lab
folder, so you can read it directly:

```bash
ls logs/                  # access.json is the log of every request
cat logs/access.json      # everything logged so far — all of it is YOU
```

Now open a **second terminal tab** (`cd ~/defensive-ai-logbot` in it) and
watch the log live:

```bash
tail -f logs/access.json
```

Keep that tab visible. In your browser (a **private/incognito window** works
best), do these three things and watch a new line appear for each:

| Do this | Expected `status` |
|---------|-------------------|
| Visit a few normal pages (`/about`, `/news`…) | `200` OK |
| Go to `/admin/` and log in with a **wrong** password (any username) | `401` Unauthorized |
| Go to `/admin/` and log in as **`student`** / **`Defend2026!`** | `200` OK — you're in |

> **Browser being stubborn?** Once you log in, browsers remember the password,
> so you won't be asked again. Close the private window to "log out." You can
> also do all three from the terminal with `curl`. `-u` sends a username and
> password, and `-w` prints the status code:
> ```bash
> curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/about
> curl -s -o /dev/null -w "%{http_code}\n" -u student:wrongpass http://localhost:8080/admin/
> curl -s -o /dev/null -w "%{http_code}\n" -u 'student:Defend2026!' http://localhost:8080/admin/
> ```

Press `Ctrl-C` to stop `tail -f` when you're done. (The Lab Notes explain every
field in a log line.)

> **Q2.** What is the full path of the log file in your lab folder? Copy one
> of your `200` lines and your `401` line into your answers.
> (a) What is the `src_ip` on your lines? (It is *not* your laptop's real
> address. Docker forwards your browser's traffic, so it shows up as the
> network's gateway, usually ending in `.1`.)
> (b) What's different between your failed login and your successful login?
> Look at `status` and `user`.
> (c) What does the `ua` (user agent) field say for you?

---

## Step 3 — Turn on the "regular traffic"

```bash
./scripts/start_visitors.sh
```

This starts the `visitors` container. It's a script (`traffic/legit_users.py`)
pretending to be normal employees and customers: browsing pages and sometimes
logging in correctly as `alice`, `bob`, or `intern`.

Watch the log again with `tail -f logs/access.json` for 30 seconds or so. Then
measure how fast it's growing:

```bash
wc -l logs/access.json      # count the lines
# ...wait 60 seconds...
wc -l logs/access.json      # count again
```

> **Q3.** (a) How many lines did the log gain in 60 seconds? (b) Your own lines
> from Step 2 are still in there. How could you pick them out from the
> visitors' lines? (Hint: compare the `ua` and `src_ip` fields.) (c) Find a
> staff login in the log. Which user was it, and what `status` did it get?

---

## Step 4 — Turn on the attacker

```bash
./scripts/start_attacker.sh
```

> **Important: there is no real hacker here.** The "attacker" is a script
> (`traffic/attacker.py`) running in a container that *you* just started. It
> fakes a password-guessing attack so you have something to defend against. It
> **keeps attacking until you shut it down** with `./scripts/stop_lab.sh`.

Show only the failed logins (`grep` keeps only the lines that match):

```bash
grep '"status":401' logs/access.json | tail -20
```

The attacker doesn't guess at a steady rate. It sends a **burst** of guesses,
then pauses. To see the rhythm, count the failed logins in each second. The
`cut` part keeps just the timestamp from each line, and `uniq -c` counts
identical timestamps in a row:

```bash
grep '"status":401' logs/access.json | grep -v student | cut -c8-26 | uniq -c
```

You'll see a few seconds with 3–4 failed logins each, then a gap of several
seconds with none, then another burst. You can also ask the attacker what
it's doing: `docker logs lab-attacker`.

> **Q4.** (a) What is the attacker's `src_ip`? Write it down. You need it in
> Step 5. (b) Describe the burst pattern: about how many failed logins per
> burst, and how many seconds between bursts? (c) List three usernames the
> attacker tries. (d) Your own failed login in Step 2 was also a `401`. How is
> the attacker's `401` traffic different from yours?

---

## Step 5 — Block the attacker yourself (then unblock)

Before an AI does it, **you** be the firewall. The web server reads block rules
from `firewall/blocklist.conf`. A rule is one line: `deny <ip>;`

**Add the rule.** Use the attacker IP from Q4, *not* yours:

```bash
echo 'deny 172.xx.0.x;' >> firewall/blocklist.conf     # ← put the attacker's real IP here
cat firewall/blocklist.conf
```

> ⚠️ Don't block the IP that ends in `.1`. That's **you** (Step 2), and you'll
> lock yourself out of the website.

Within about a second the web server notices the change and reloads:

```bash
docker logs lab-web | grep firewall     # look for: reloaded nginx (1 active rules)
```

**Watch it work.** Wait for the attacker's next burst (about 10 seconds), then:

```bash
grep '"status":403' logs/access.json | tail -5   # 403 Forbidden = blocked
docker logs lab-attacker | tail -3               # the attacker notices
```

📸 **Screenshot 1:** your terminal showing the `deny` line in
`firewall/blocklist.conf` and the attacker's `403` lines.

**Now remove the rule.** Open the file, delete the `deny` line, and save
(`Ctrl-O`, `Enter`, `Ctrl-X`):

```bash
nano firewall/blocklist.conf
docker logs lab-web | grep firewall     # look for: reloaded nginx (0 active rules)
```

Wait 30–40 seconds (a blocked attacker backs off for a while), then confirm the
attacker's `401`s are back:

```bash
grep '"status":401' logs/access.json | tail -5
```

You **must** remove your rule before Step 8. Otherwise the AI will find the
attacker already blocked and have nothing to do.

> **Q5.** (a) What status code did the attacker get *before*, *during*, and
> *after* your rule? (b) Did the normal visitors notice anything while the rule
> was in place? Why not? (c) You did this by hand for **one** attacker in
> **one** class period. What would it be like to do this job 24 hours a day,
> for a website with hundreds of attackers?

---

## Step 6 — Think: the log gets long, fast

No new commands to start. This step is about *why* the rest of the lab exists.

Check how big the log is now:

```bash
wc -l logs/access.json        # lines
ls -lh logs/access.json       # size on disk
head -1 logs/access.json | wc -c     # characters in ONE line
```

**The AI context window.** An AI model can only "see" a limited amount of text
at once. That limit is its **context window**, measured in *tokens* (roughly 4
characters of English per token, and JSON logs are usually worse than that).
The model in this lab, `llama3.2:3b`, usually runs with a context window of a
few thousand tokens (often 4,096; it depends on your Ollama version and GPU
memory). It *can* stretch to about 128,000, but bigger is slower and uses much
more memory. Anything that doesn't fit, the model simply never sees. For the
math below, use **4,000 tokens**.

**The fix is batching.** Instead of giving the AI the whole log, cut it into
small time slices and look at one slice at a time. Open the batching script and
read it. It's short, and the comments explain each part:

```bash
less broker/batch_logs.py      # arrows to scroll, q to quit
```

Find the section marked `# ── The heart`. In plain English, it says:

1. Keep reading new log lines and collect them in a list.
2. When the time window (5 seconds) is up, **close the batch**: save it.
3. **Sieve** the batch: keep only the failed logins (`401` on `/admin/`),
   grouped by IP address. Everything else is thrown away.
4. **Compress** what's left into a tiny summary: how many failures, how many
   different usernames, which user agent.
5. Start a fresh, empty batch and repeat.

The real Defensive AI (`broker/soc_broker.py`) uses this **exact same loop**.
The only difference is that it hands each summary to the AI.

> **Q6.** (a) Use your measurements: about how many tokens is one log line
> (characters ÷ 4)? About how many log lines would fill a 4,000-token context
> window? (b) Using your answer to Q3(a), how many *minutes* of this small
> website's traffic would fill the window? (c) A real company website gets
> thousands of requests per *second*. Explain why "just paste the log into the
> AI" can't work. Give at least two reasons.

---

## Step 7 — Run the batching script

```bash
python3 broker/batch_logs.py
```

It watches the live log for 15 seconds and cuts it into **3 batches** of 5
seconds each, saved as files. Then it stops. For each batch it prints how many
lines came in, how many the sieve kept, and the tiny summary the AI *would* be
sent. (No AI is used in this step.)

Look at what it made:

```bash
ls batches/
wc -l logs/access.json batches/*.jsonl          # whole log vs. each batch
cat batches/batch_1.jsonl                       # one whole batch
grep -c '"status":401' batches/*.jsonl          # failed logins in each batch
```

Run it a second time if you like. It replaces the 3 files with fresh ones.

> **Q7.** (a) Fill in a small table: for each batch, the total lines and the
> number of `401`s. (b) Did every batch contain an attack? What does the script
> do with a batch that has no failed logins? (c) Compare the summary the script
> printed to the raw lines in the batch. How much smaller is it? What
> information was kept, and what was thrown away? (d) Sometimes one attack
> burst gets split across two batches. Why could that be a problem for a
> defender that only looks at one batch at a time?

---

## Step 8 — Turn on the Defensive AI

This is the payoff. Everything you did by hand in Steps 4–7 (spot the `401`
bursts, cut the log into batches, decide "that's an attack," write the `deny`
rule) is about to happen **automatically**.

First make sure your Step 5 rule is gone (`cat firewall/blocklist.conf` should
show no `deny` lines). Then start the broker:

```bash
python3 broker/soc_broker.py
```

Watch its output:

- `sieve: kept N … dropped M …`: the Step 7 batching and sieve, running live.
- `window closed: N failed logins from <ip>`: a batch looked suspicious, so
  its summary is going to the AI. The **first** AI answer takes about 30 seconds
  (the model is loading onto your GPU). After that it's fast.
- The AI's three-line verdict: `[STATUS]`, `[ATTACKER_IP]`, `[EXPLANATION]`.
- `*** [AUTOMATED RESPONSE] blocked <ip> ***`: the broker wrote the same kind
  of `deny` rule you wrote in Step 5, plus an incident report in `alerts/`.

Confirm it worked, exactly the way you checked your own rule in Step 5:

```bash
cat firewall/blocklist.conf
grep '"status":403' logs/access.json | tail -3
cat alerts/incident_*.json
python3 scripts/check_progress.py    # should be all green
```

📸 **Screenshot 2:** your broker terminal showing the `[STATUS] ALERT` verdict
and the `*** [AUTOMATED RESPONSE] blocked … ***` banner, with the attacker IP
and the AI's explanation visible.

### Step 8 reflection: the big picture

Take your time on these. They're the point of the lab, and they're worth more
than the earlier questions.

> **Q8. What the AI saw.** Copy the AI's three-line verdict. The AI never saw
> the raw log, only the small summary. What evidence in that summary pointed to
> an attack rather than an employee who forgot their password? Compare that
> with how *you* recognized the attack in Step 4.

> **Q9. The chain you built.** Trace what happened, in order, from the
> attacker's first failed login to the attacker getting `403`. For each link in
> the chain, name the lab step where you did that job **by hand** first.
> (Example: "noticing the `401` bursts: I did this in Step 4 with `grep`.")

> **Q10. SOC analyst jobs.** A Security Operations Center (SOC) analyst's day
> includes watching logs, spotting attacks, and blocking them. Which parts of
> that job did this lab automate? Which parts still need a human? (Who checks
> whether the AI was *right*? Who decided the rules and thresholds? Who reads
> `alerts/`?) Does a tool like this replace analysts or change what they do?
> Explain.

> **Q11. Is this good AI defense?** Give at least one strength and at least
> two weaknesses. Consider: What if the AI says `SAFE` to a real attack, or
> `ALERT` to a real employee who mistyped their password a few times? (The
> broker also has a backup rule that blocks anyone with 15+ failures in a
> window, even if the AI is down. Why include that?) What if an attacker
> guesses *slowly*, one password per minute, so no single batch looks
> suspicious? What if the attacker changes their user agent to look like a
> normal browser?

> **Q12. Make it better.** Propose two specific improvements to this system,
> and explain what problem each one fixes. Ideas: remembering IPs across
> batches, unblocking automatically after a timeout, a human approving each
> block, giving the AI more (or different) information, alerting a person
> instead of blocking, or something of your own.

---

## Submit

1. **Screenshot 1** (Step 5): your manual `deny` rule and the attacker's `403`s.
2. **Screenshot 2** (Step 8): the broker's `[STATUS] ALERT` and the
   automated-response banner.
3. **Answers** to Q1–Q12.

### ⚠️ When you're done: SHUT THE LAB DOWN

The attacker and visitor scripts keep running in the background until you stop
them. Always shut the lab down when you finish:

```bash
# 1. In your broker terminal, press Ctrl-C to stop the Defensive AI.
# 2. Then stop all the containers (this stops the attacker too):
./scripts/stop_lab.sh
```

Double-check nothing is still running:

```bash
docker ps        # you should NOT see lab-web, lab-visitors, or lab-attacker
```

Starting over? `./scripts/start_website.sh` wipes the old logs and starts again
at Step 1. To jump straight to a full lab (Steps 1, 3, and 4 all at once), use
`./scripts/run_lab.sh`.

---

## Advanced explorations (optional, for extra credit)

Run `./scripts/reset_lab.sh` between experiments to start clean.

- **Tune the window.** Run `python3 broker/soc_broker.py --help` and try
  different `--window` or `--suspect-threshold` values. What happens to
  detection speed and false alarms with a 1-second window vs. a 30-second one?
  Try the same `--window` values with `broker/batch_logs.py` to *see* the
  batches change.
- **No AI at all.** Run the broker with `--no-ai`. It blocks on the count alone.
  What's lost? What's gained?
- **Slow-and-low attack.** Edit `traffic/attacker.py` and raise `ATTACK_GAP` so
  guesses are spaced *minutes* apart. Can the broker still catch it? How would
  the broker need to *remember* past batches to catch a slow attacker?
  (Describe the design. You don't have to build it.)
- **Trick the AI.** Change the attacker's `User-Agent` or usernames to look more
  "human." Does the model still flag it? Where is the line between a cautious
  defender and one that cries wolf?
- **Scale it up.** Write a short paragraph: to defend 50,000 requests/second,
  what hardware and architecture would you add? (Think: streaming tools like
  Kafka, a database of known-bad patterns, dedicated inference GPUs.)
