#!/usr/bin/env python3
"""check_progress.py — instant feedback on how far through the lab run you are.

Run this ANY time, as often as you like. It never changes anything — it just
looks at what's happening and tells you the next thing to do. Use it when
you're not sure whether a step worked, or when you're stuck.

    python3 scripts/check_progress.py

It walks the lab in order and stops guiding you at the first step that isn't
done yet, with an exact command to try. When every step is green, it tells you
exactly what your submission screenshot should show.

This checks that you RAN the lab correctly. It does not grade your written
answers — those are yours to answer.
"""
import collections
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "access.json")
BLOCKLIST = os.path.join(ROOT, "firewall", "blocklist.conf")
ALERTS = os.path.join(ROOT, "alerts")
BATCHES = os.path.join(ROOT, "batches")

# ── tiny color helpers (degrade to plain text if not a terminal) ─────────────
_TTY = sys.stdout.isatty()
def c(code, s): return f"\033[{code}m{s}\033[0m" if _TTY else s
GREEN = lambda s: c("32", s)
RED = lambda s: c("31", s)
YELLOW = lambda s: c("33", s)
BLUE = lambda s: c("34;1", s)
DIM = lambda s: c("2", s)


# ── data the checks share ────────────────────────────────────────────────────

def docker_ps():
    """Return a dict {container_name: status_string}, or None if docker is absent."""
    try:
        out = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        return dict(
            line.split("\t", 1)
            for line in out.stdout.strip().splitlines()
            if "\t" in line
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def read_log_events():
    """Return list of parsed log events (may be empty)."""
    events = []
    try:
        with open(LOG) as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return events


def deny_rules():
    """Return list of IPs in the firewall blocklist."""
    ips = []
    try:
        with open(BLOCKLIST) as f:
            for line in f:
                s = line.strip()
                if s.startswith("deny "):
                    ips.append(s.split()[1].rstrip(";"))
    except FileNotFoundError:
        pass
    return ips


def incident_files():
    return sorted(glob.glob(os.path.join(ALERTS, "incident_*.json")))


# ── the ordered checklist ────────────────────────────────────────────────────
# Each step is (title, check) where check() returns (done: bool, detail: str,
# hint: str). detail prints on success; hint prints when it's your next step.
#
# The visitor and attacker scripts both send the User-Agent "Python-urllib".
# Anything else (a browser, curl) is YOU — that's how Step 2 finds your traffic.

SCRIPT_UA = "Python-urllib"
STAFF = {"alice", "bob", "intern"}


def is_mine(e):
    return not e.get("ua", "").startswith(SCRIPT_UA)


def is_admin(e):
    return e.get("uri", "").startswith("/admin")


def container_up(ps, name):
    return bool(ps) and ps.get(name, "").startswith("Up")


def first_incident_ts():
    """ISO timestamp of the broker's first incident, or None."""
    for path in incident_files():
        try:
            return json.load(open(path)).get("timestamp")
        except Exception:
            continue
    return None


def step_website(ps):
    if ps is None:
        return (False, "",
                "Docker isn't responding. Start Docker Desktop (enable WSL\n"
                "integration), then run:  ./scripts/preflight.sh")
    if container_up(ps, "lab-web"):
        return (True, "website container is running", "")
    return (False, "",
            "Start the website with:  ./scripts/start_website.sh\n"
            "Then browse http://localhost:8080")


def step_my_traffic(events):
    mine = [e for e in events if is_mine(e)]
    page_200 = any(e.get("status") == 200 and not is_admin(e) for e in mine)
    login_401 = any(e.get("status") == 401 and is_admin(e) for e in mine)
    login_200 = any(e.get("status") == 200 and is_admin(e) for e in mine)
    if page_200 and login_401 and login_200:
        return (True, "found your 200 pages, a failed 401 login, and a 200 login", "")
    todo = []
    if not page_200:
        todo.append("visit a few public pages (200)")
    if not login_401:
        todo.append("try /admin/ with a WRONG password (401)")
    if not login_200:
        todo.append("log in to /admin/ as student / Defend2026! (200)")
    return (False, "",
            "Still to do: " + "; ".join(todo) + ".\n"
            "Watch them land with:  tail -f logs/access.json")


def step_visitors(ps, events):
    logins = sum(1 for e in events
                 if e.get("status") == 200 and e.get("user") in STAFF)
    if container_up(ps, "lab-visitors") and logins:
        return (True, f"regular traffic flowing ({logins} staff logins so far)", "")
    if container_up(ps, "lab-visitors"):
        return (False, "",
                "Visitors are running but no staff login yet — wait ~30s and re-check.")
    return (False, "", "Start the regular traffic with:  ./scripts/start_visitors.sh")


def step_attacker(ps, events):
    counts = collections.Counter(e.get("src_ip", "?") for e in events
                                 if e.get("status") == 401 and not is_mine(e))
    if counts:
        ip, n = counts.most_common(1)[0]
        return (True, f"attack in the log ({n} failed logins from {ip})", "")
    if container_up(ps, "lab-attacker"):
        return (False, "",
                "Attacker is running — its bursts come every ~10s. Re-check soon, or\n"
                "watch:  grep '\"status\":401' logs/access.json | tail")
    return (False, "", "Start the attacker with:  ./scripts/start_attacker.sh")


def step_manual_block(events):
    # A 403 that happened BEFORE the AI's first incident was caused by your rule.
    cutoff = first_incident_ts()
    manual = [e for e in events if e.get("status") == 403
              and (cutoff is None or e.get("ts", "") < cutoff)]
    rules = deny_rules()
    if manual and (cutoff or not rules):
        return (True, f"your rule blocked the attacker ({len(manual)} x 403), "
                      "then you removed it", "")
    if manual:
        return (False, "",
                f"Your rule works ({len(manual)} x 403)! Now DELETE it so the AI can\n"
                "do the blocking later:  nano firewall/blocklist.conf")
    if rules:
        return (False, "",
                "Rule written but no 403 yet. Wait for the next attack burst (~10s),\n"
                "and check the reload:  docker logs lab-web | grep firewall")
    return (False, "",
            "Add a block rule for the attacker IP:\n"
            "echo 'deny <attacker-ip>;' >> firewall/blocklist.conf")


def step_batches():
    files = glob.glob(os.path.join(BATCHES, "batch_*.jsonl"))
    if files:
        return (True, f"{len(files)} batch file(s) in batches/", "")
    return (False, "",
            "Run the batching script:  python3 broker/batch_logs.py\n"
            "(Do the Step 6 reading and questions first.)")


def step_ai(events):
    incs = incident_files()
    ips = deny_rules()
    if not incs:
        return (False, "",
                "Run the Defensive AI:  python3 broker/soc_broker.py\n"
                "The FIRST AI answer takes ~30s (the model is loading). Wait for it.")
    if not ips:
        return (False, "",
                "The AI raised an incident but the rule is gone. Did you edit\n"
                "firewall/blocklist.conf? Re-run the broker.")
    cutoff = first_incident_ts() or ""
    n = sum(1 for e in events if e.get("status") == 403
            and e.get("src_ip") in ips and e.get("ts", "") >= cutoff)
    if n:
        return (True, f"AI blocked {', '.join(ips)}; attacker got {n} x 403", "")
    return (False, "",
            "The AI wrote the rule. Waiting for the attacker's next try to bounce\n"
            "off with 403 — re-run this check in ~30s.")


def main():
    events = read_log_events()

    ps = docker_ps()

    # (guide step number, title, result). Step 6 is reading + questions only,
    # so there is nothing for this script to check there.
    steps = [
        (1, "Website is running",                     step_website(ps)),
        (2, "Your own traffic is in the log",         step_my_traffic(events)),
        (3, "Regular traffic is flowing",             step_visitors(ps, events)),
        (4, "Attacker is hitting /admin/",            step_attacker(ps, events)),
        (5, "You blocked it by hand, then unblocked", step_manual_block(events)),
        (7, "Log split into batches",                 step_batches()),
        (8, "Defensive AI blocked the attacker",      step_ai(events)),
    ]

    print()
    print(BLUE("  Lab progress check") + DIM("   (read-only — safe to run anytime)"))
    print("  " + "─" * 58)

    done_count = 0
    next_shown = False
    for i, title, (done, detail, hint) in steps:
        if done:
            done_count += 1
            msg = f"  {GREEN('✓')} Step {i}. {title}"
            if detail:
                msg += DIM(f"  — {detail}")
            print(msg)
        elif not next_shown:
            next_shown = True
            print(f"  {YELLOW('▶')} Step {i}. {title}  {YELLOW('← you are here')}")
            for line in hint.splitlines():
                print(f"       {line}")
        else:
            print(f"  {DIM('·')} {DIM(f'Step {i}. {title}')}")

    print("  " + "─" * 58)
    total = len(steps)
    if done_count == total:
        print("  " + GREEN("Every step complete! The automated defense worked. 🎉"))
        print()
        print("  For your submission, screenshot your BROKER terminal showing:")
        print("    • the AI verdict line  [STATUS] ALERT")
        print("    • the  *** [AUTOMATED RESPONSE] blocked <ip> ***  banner")
        print("  Then finish the Step 8 reflection questions in the Student Guide.")
        print()
        print(DIM("  Done experimenting?  ./scripts/stop_lab.sh"))
    else:
        bar = GREEN("█" * done_count) + DIM("░" * (total - done_count))
        print(f"  Progress: {bar}  {done_count}/{total} checks")
        print(f"  Do the {YELLOW('▶')} step above, then run this check again.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
