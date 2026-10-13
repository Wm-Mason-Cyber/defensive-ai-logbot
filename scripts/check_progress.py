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
answers to Q1-Q6 — those are yours to answer.
"""
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "access.json")
BLOCKLIST = os.path.join(ROOT, "firewall", "blocklist.conf")
ALERTS = os.path.join(ROOT, "alerts")

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

def step_containers():
    ps = docker_ps()
    if ps is None:
        return (False,
                "",
                "Docker isn't responding. Start Docker Desktop (enable WSL\n"
                "       integration), then run:  ./scripts/preflight.sh")
    wanted = ["lab-web", "lab-visitors", "lab-attacker"]
    up = {n: s for n, s in ps.items() if n in wanted and s.startswith("Up")}
    if len(up) == 3:
        health = "healthy" if any("healthy" in s for s in up.values()) else "running"
        return (True, f"all 3 containers running (web is {health})", "")
    missing = [n for n in wanted if n not in up]
    return (False, "",
            f"These containers aren't up yet: {', '.join(missing)}\n"
            "       Start the lab with:  ./scripts/run_lab.sh")


def step_log(events):
    if events:
        return (True, f"web server is logging ({len(events)} requests recorded)", "")
    return (False, "",
            "No requests logged yet in logs/access.json.\n"
            "       Give it a few seconds after run_lab.sh, then browse\n"
            "       http://localhost:8080 yourself to generate traffic.")


def step_normal(events):
    n = sum(1 for e in events if e.get("status") == 200)
    if n:
        return (True, f"normal visitor traffic is flowing ({n} x 200 OK)", "")
    return (False, "",
            "No normal (200) traffic seen yet. The 'visitors' container\n"
            "       should be producing it — check:  docker ps")


def step_attack(events):
    attackers = {}
    for e in events:
        if e.get("status") == 401:
            attackers[e.get("src_ip", "?")] = attackers.get(e.get("src_ip", "?"), 0) + 1
    if attackers:
        ip, n = max(attackers.items(), key=lambda kv: kv[1])
        return (True, f"attack detected in the log ({n} failed logins from {ip})", "")
    return (False, "",
            "No failed logins (401) yet. The attacker bursts periodically —\n"
            "       wait ~15s and re-run this check. Watch live with:\n"
            "       tail -f logs/access.json")


def step_broker():
    incs = incident_files()
    if incs:
        try:
            data = json.load(open(incs[-1]))
            return (True,
                    f"broker raised an incident for {data.get('blocked_ip','?')} "
                    f"({len(incs)} total)", "")
        except Exception:
            return (True, f"broker raised {len(incs)} incident(s)", "")
    return (False, "",
            "The broker hasn't flagged anything yet. In a second terminal run:\n"
            "       python3 broker/soc_broker.py\n"
            "       The FIRST AI answer takes ~30s (the model is loading) — wait for it.")


def step_firewall():
    ips = deny_rules()
    if ips:
        return (True, f"firewall rule written: blocking {', '.join(ips)}", "")
    return (False, "",
            "No firewall rule written yet. This happens automatically once the\n"
            "       broker's AI returns [STATUS] ALERT. Keep the broker running.")


def step_enforced(events):
    blocked_ips = set(deny_rules())
    if not blocked_ips:
        return (False, "",
                "Nothing is blocked yet, so there's nothing to enforce. Finish\n"
                "       the previous step first.")
    n = sum(1 for e in events
            if e.get("status") == 403 and e.get("src_ip") in blocked_ips)
    if n:
        return (True,
                f"block is ENFORCED — attacker got {n} x 403 Forbidden", "")
    return (False, "",
            "Rule is written but no 403s seen yet. nginx reloads within ~1s;\n"
            "       the attacker also backs off when blocked. Re-run this check\n"
            "       in a few seconds, or look at:  docker logs lab-web | grep firewall")


def main():
    events = read_log_events()

    steps = [
        ("Lab environment is running",        step_containers()),
        ("Web server is recording a log",     step_log(events)),
        ("Normal traffic is flowing",         step_normal(events)),
        ("Attack is hitting the admin login", step_attack(events)),
        ("Defensive AI flagged the attack",   step_broker()),
        ("Firewall rule was written",         step_firewall()),
        ("Attacker is actually blocked",      step_enforced(events)),
    ]

    print()
    print(BLUE("  Lab progress check") + DIM("   (read-only — safe to run anytime)"))
    print("  " + "─" * 58)

    done_count = 0
    next_shown = False
    for i, (title, (done, detail, hint)) in enumerate(steps, 1):
        if done:
            done_count += 1
            msg = f"  {GREEN('✓')} {i}. {title}"
            if detail:
                msg += DIM(f"  — {detail}")
            print(msg)
        elif not next_shown:
            next_shown = True
            print(f"  {YELLOW('▶')} {i}. {title}  {YELLOW('← you are here')}")
            for line in hint.splitlines():
                print(f"       {line}")
        else:
            print(f"  {DIM('·')} {DIM(f'{i}. {title}')}")

    print("  " + "─" * 58)
    total = len(steps)
    if done_count == total:
        print("  " + GREEN(f"All {total} steps complete! The automated defense worked. 🎉"))
        print()
        print("  For your submission, screenshot your BROKER terminal showing:")
        print("    • the AI verdict line  [STATUS] ALERT")
        print("    • the  *** [AUTOMATED RESPONSE] blocked <ip> ***  banner")
        print("  Then answer Q1-Q6 in the Student Guide.")
        print()
        print(DIM("  Done experimenting?  ./scripts/stop_lab.sh"))
    else:
        bar = GREEN("█" * done_count) + DIM("░" * (total - done_count))
        print(f"  Progress: {bar}  {done_count}/{total}")
        print(f"  Do the {YELLOW('▶')} step above, then run this check again.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
