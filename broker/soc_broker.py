#!/usr/bin/env python3
"""soc_broker.py — the Defensive AI SOC broker.

This is the script students run on their HOST machine (inside WSL). It is the
"brain" that sits between a high-speed web server and a slow, probabilistic AI
model. It does four things, in order:

  1. TAIL    follow the nginx JSON access log line by line as it grows.
  2. SIEVE   throw away the firehose of normal 200s; keep only 401s (failed
             logins) and group them into short time windows per source IP.
  3. REASON  when a window looks suspicious, send a small, compressed summary
             (NOT the raw logs) to a local LLM via Ollama and ask: attack or
             not? The model must answer in a strict, parseable format.
  4. RESPOND if the model says ALERT, write a firewall rule that blocks the IP
             and drop an incident record in ./alerts/. The nginx firewall-watch
             loop picks the rule up and enforces it.

Design choices worth understanding (they are the lab's real lesson):
  * A cheap, deterministic Python filter handles 99.9% of events. The expensive
    AI is only consulted for the tiny fraction that a rule flags. This is how
    real SOCs keep LLM cost and latency under control.
  * A deterministic threshold (DECIDE_THRESHOLD) also exists so the pipeline
    still defends itself if the model is slow or gives a junk answer. The AI
    adds explanation and nuance; it is not the only thing standing guard.
"""
import argparse
import collections
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import ollama
except ImportError:
    ollama = None  # handled in run_ai(); --no-ai still works without the package


# ── Configuration (overridable by CLI flags) ────────────────────────────────

DEFAULTS = {
    "log": "./logs/access.json",
    "blocklist": "./firewall/blocklist.conf",
    "alerts": "./alerts",
    "model": "llama3.2:3b",
    "window": 5.0,          # seconds; how often we evaluate the batch
    "suspect_threshold": 5, # >= this many 401s from one IP in a window -> ask AI
    "decide_threshold": 15, # >= this many -> block even if AI is unavailable
}

ALERT_RE_STATUS = re.compile(r"\[STATUS\]\s*(ALERT|SAFE)", re.I)
ALERT_RE_IP = re.compile(r"\[ATTACKER_IP\]\s*([0-9A-Fa-f:.]+)")
ALERT_RE_WHY = re.compile(r"\[EXPLANATION\]\s*(.+)")


# ── 1. TAIL ──────────────────────────────────────────────────────────────────

def follow(path):
    """Yield new JSON log lines as they are written, like `tail -F`.

    Waits for the file to appear, seeks to the end so we only see new traffic,
    and transparently re-opens the file if logrotate replaces it.
    """
    while not os.path.exists(path):
        print(f"[broker] waiting for log file {path} ...", flush=True)
        time.sleep(1)

    f = open(path, "r")
    f.seek(0, os.SEEK_END)
    inode = os.fstat(f.fileno()).st_ino

    while True:
        line = f.readline()
        if line:
            yield line
            continue
        # No new data. Check whether the file was rotated out from under us.
        try:
            if os.stat(path).st_ino != inode:
                f.close()
                f = open(path, "r")
                inode = os.fstat(f.fileno()).st_ino
                continue
        except FileNotFoundError:
            pass
        yield None  # idle tick, lets the caller flush its window on time


# ── 2. SIEVE ───────────────────────────────────────────────────────────────

def is_failed_login(event):
    """Keep only the signal: failed auth (401) against the admin console."""
    return event.get("status") == 401 and event.get("uri", "").startswith("/admin")


def compress(ip, events):
    """Turn a pile of raw log lines into a tiny summary for the model.

    We send counts and a couple of samples — never the full firehose. A real
    SOC does the same thing so the LLM prompt stays small and cheap.
    """
    users = collections.Counter(e.get("user") or "-" for e in events)
    uris = collections.Counter(e.get("uri") for e in events)
    span = 0.0
    try:
        t0 = datetime.fromisoformat(events[0]["ts"])
        t1 = datetime.fromisoformat(events[-1]["ts"])
        span = abs((t1 - t0).total_seconds())
    except Exception:
        pass
    return {
        "source_ip": ip,
        "failed_logins": len(events),
        "window_seconds": round(span, 1),
        "distinct_usernames_tried": len(users),
        "top_usernames": [u for u, _ in users.most_common(5)],
        "paths": [u for u, _ in uris.most_common(3)],
        "user_agent": events[-1].get("ua", ""),
    }


# ── 3. REASON ────────────────────────────────────────────────────────────────

PROMPT = """You are a security analyst assistant inside an automated SOC.
You are given a COMPRESSED SUMMARY of failed-login (HTTP 401) activity from a
single source IP against a web admin console. Decide whether this is an
automated credential brute-force / password-guessing attack.

Summary:
{summary}

Reply using EXACTLY this format, nothing else:
[STATUS] ALERT or SAFE
[ATTACKER_IP] the source IP from the summary
[EXPLANATION] one short sentence of technical reasoning
"""


def run_ai(model, summary):
    """Ask the local model about one summary. Returns (status, ip, why) or None."""
    if ollama is None:
        print("[broker] ollama python package not installed; skipping AI "
              "(deterministic threshold still active).", flush=True)
        return None
    prompt = PROMPT.format(summary=json.dumps(summary, indent=2))
    try:
        t0 = time.time()
        res = ollama.generate(
            model=model,
            prompt=prompt,
            options={"temperature": 0},  # we want consistent, not creative, output
        )
        dt = time.time() - t0
        text = res.get("response", "").strip()
        print(f"\n[broker] AI analysed IP {summary['source_ip']} in {dt:.1f}s:",
              flush=True)
        print("    " + text.replace("\n", "\n    "), flush=True)
        status = (ALERT_RE_STATUS.search(text) or [None, "SAFE"])[1].upper()
        ip_m = ALERT_RE_IP.search(text)
        why_m = ALERT_RE_WHY.search(text)
        ip = ip_m.group(1) if ip_m else summary["source_ip"]
        why = why_m.group(1).strip() if why_m else "(no explanation parsed)"
        return status, ip, why
    except Exception as e:
        print(f"[broker] AI call failed ({e}); falling back to threshold.",
              flush=True)
        return None


# ── 4. RESPOND ───────────────────────────────────────────────────────────────

def already_blocked(blocklist_path, ip):
    try:
        with open(blocklist_path) as f:
            return any(ip in line and "deny" in line for line in f)
    except FileNotFoundError:
        return False


def block(cfg, ip, reason, summary):
    """Write a firewall rule + an incident record. Idempotent per IP."""
    if already_blocked(cfg["blocklist"], ip):
        print(f"[broker] {ip} already blocked; no action.", flush=True)
        return

    os.makedirs(os.path.dirname(cfg["blocklist"]) or ".", exist_ok=True)
    with open(cfg["blocklist"], "a") as f:
        f.write(f"deny {ip};  # {datetime.now(timezone.utc).isoformat()} {reason}\n")

    os.makedirs(cfg["alerts"], exist_ok=True)
    stamp = int(time.time())
    incident = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "blocked_ip": ip,
        "reason": reason,
        "evidence": summary,
    }
    path = os.path.join(cfg["alerts"], f"incident_{stamp}_{ip.replace(':', '_')}.json")
    with open(path, "w") as f:
        json.dump(incident, f, indent=2)

    print(f"\n*** [AUTOMATED RESPONSE] blocked {ip} ***", flush=True)
    print(f"    reason: {reason}", flush=True)
    print(f"    firewall rule appended to {cfg['blocklist']}", flush=True)
    print(f"    incident written to {path}\n", flush=True)


# ── Main loop ────────────────────────────────────────────────────────────────

def evaluate(cfg, use_ai, batch):
    """Decide on each suspicious IP in the just-closed window."""
    for ip, events in batch.items():
        if len(events) < cfg["suspect_threshold"]:
            continue  # below the "interesting" bar — stay cheap, say nothing
        summary = compress(ip, events)
        print(f"[broker] window closed: {summary['failed_logins']} failed logins "
              f"from {ip} ({summary['distinct_usernames_tried']} usernames).",
              flush=True)

        verdict = run_ai(cfg["model"], summary) if use_ai else None

        if verdict and verdict[0] == "ALERT":
            block(cfg, verdict[1], f"AI: {verdict[2]}", summary)
        elif verdict and verdict[0] == "SAFE":
            print(f"[broker] AI judged {ip} SAFE; no block.", flush=True)
        elif len(events) >= cfg["decide_threshold"]:
            # AI unavailable or unparseable, but the volume is damning.
            block(cfg, f"deterministic threshold "
                       f"({len(events)} failed logins)", ip, summary)


def main():
    p = argparse.ArgumentParser(description="Defensive AI SOC broker")
    p.add_argument("--log", default=DEFAULTS["log"])
    p.add_argument("--blocklist", default=DEFAULTS["blocklist"])
    p.add_argument("--alerts", default=DEFAULTS["alerts"])
    p.add_argument("--model", default=DEFAULTS["model"])
    p.add_argument("--window", type=float, default=DEFAULTS["window"])
    p.add_argument("--suspect-threshold", type=int, default=DEFAULTS["suspect_threshold"])
    p.add_argument("--decide-threshold", type=int, default=DEFAULTS["decide_threshold"])
    p.add_argument("--no-ai", action="store_true",
                   help="skip the LLM; use the deterministic threshold only")
    args = p.parse_args()

    cfg = {
        "log": args.log, "blocklist": args.blocklist, "alerts": args.alerts,
        "model": args.model, "window": args.window,
        "suspect_threshold": args.suspect_threshold,
        "decide_threshold": args.decide_threshold,
    }
    use_ai = not args.no_ai

    print("=" * 64, flush=True)
    print(" Defensive AI SOC Broker", flush=True)
    print(f"   log file:   {cfg['log']}", flush=True)
    print(f"   model:      {'(disabled)' if args.no_ai else cfg['model']}", flush=True)
    print(f"   window:     {cfg['window']}s   "
          f"suspect>={cfg['suspect_threshold']}  block>={cfg['decide_threshold']}",
          flush=True)
    print("=" * 64, flush=True)

    batch = collections.defaultdict(list)
    last_flush = time.time()
    kept = dropped = 0

    for line in follow(cfg["log"]):
        if line:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if is_failed_login(event):
                batch[event["src_ip"]].append(event)
                kept += 1
            else:
                dropped += 1  # the 200-OK firehose the AI never has to see

        if time.time() - last_flush >= cfg["window"]:
            if batch:
                evaluate(cfg, use_ai, batch)
                batch = collections.defaultdict(list)
            if dropped or kept:
                print(f"[broker] sieve: kept {kept} failed-login events, "
                      f"dropped {dropped} normal events this period.", flush=True)
                kept = dropped = 0
            last_flush = time.time()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[broker] stopped.", flush=True)
        sys.exit(0)
