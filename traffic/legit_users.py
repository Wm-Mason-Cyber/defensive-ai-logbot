#!/usr/bin/env python3
"""legit_users.py — simulated normal employee + visitor traffic.

Runs inside the lab's own Docker network and only ever contacts the lab web
container (host "web"). It produces the everyday "200 OK" background noise the
SOC broker is supposed to IGNORE, plus a handful of successful staff logins, so
students can see that the detector does not fire on normal activity.
"""
import base64
import random
import time
import urllib.request

BASE = "http://web"
PUBLIC_PAGES = ["/", "/about", "/news", "/products", "/robots.txt", "/static/style.css"]

# Real staff accounts (these match web/htpasswd) — they log in successfully.
STAFF = [
    ("alice", "CorrectHorse42!"),
    ("bob", "BlueTeam#2026"),
    ("intern", "Summer2026!"),
]


def request(path, auth=None):
    req = urllib.request.Request(BASE + path, method="GET")
    if auth:
        user, pw = auth
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            r.read()
    except Exception:
        pass  # 401/403/connection hiccups are fine; the log still records them


def main():
    print("[legit] normal employee/visitor traffic started", flush=True)
    while True:
        # Browse a few public pages at human speed.
        for _ in range(random.randint(2, 5)):
            request(random.choice(PUBLIC_PAGES))
            time.sleep(random.uniform(0.3, 1.2))

        # Occasionally a real staff member signs in correctly.
        if random.random() < 0.3:
            request("/admin/", auth=random.choice(STAFF))

        time.sleep(random.uniform(1.0, 3.0))


if __name__ == "__main__":
    main()
