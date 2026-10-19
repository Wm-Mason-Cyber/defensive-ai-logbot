#!/usr/bin/env python3
"""batch_logs.py — the heart of the SOC broker, with the AI taken out.

The live log grows far too fast to hand to an AI all at once. So the broker
cuts it into small time-windows ("batches") and only looks at one batch at a
time. This script does exactly that and SAVES each batch to a file so you can
open it and see what a batch looks like.

    python3 broker/batch_logs.py            # 3 batches of 5 seconds each
    python3 broker/batch_logs.py --window 10

It writes (and then stops):
    batches/batch_1.jsonl   every log line from window 1
    batches/batch_2.jsonl   every log line from window 2
    batches/batch_3.jsonl   every log line from window 3

and prints, for each batch, what the broker's SIEVE would keep and the tiny
SUMMARY the broker would send to the AI. Nothing is sent to an AI here.

It uses the very same functions as broker/soc_broker.py (follow, the sieve,
compress), so what you see here is what the real broker does.
"""
import argparse
import collections
import json
import os
import time

from soc_broker import compress, follow, is_failed_login

MAX_BATCHES = 3


def main():
    p = argparse.ArgumentParser(description="Cut the live log into batch files")
    p.add_argument("--log", default="./logs/access.json")
    p.add_argument("--out", default="./batches")
    p.add_argument("--window", type=float, default=5.0,
                   help="seconds of log per batch (the broker uses 5)")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print(f"Cutting {args.log} into {MAX_BATCHES} batches of {args.window:g}s each...\n",
          flush=True)

    # ── The heart: collect lines until the window closes, then handle the batch.
    batch_no = 1
    lines = []
    window_start = time.time()
    for line in follow(args.log):
        if line:
            lines.append(line)
        if time.time() - window_start < args.window:
            continue  # window still open — keep collecting

        # Window closed. Save the whole batch exactly as it came from the log.
        path = os.path.join(args.out, f"batch_{batch_no}.jsonl")
        with open(path, "w") as f:
            f.writelines(lines)

        # Run the broker's SIEVE: keep only failed logins, grouped per IP.
        failed = collections.defaultdict(list)
        for raw in lines:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if is_failed_login(event):
                failed[event["src_ip"]].append(event)
        kept = sum(len(v) for v in failed.values())

        print(f"── batch {batch_no}  →  {path}", flush=True)
        print(f"   {len(lines)} log lines in this window; the sieve keeps {kept} "
              f"failed logins and drops {len(lines) - kept}.", flush=True)
        for ip, events in failed.items():
            print(f"   summary the AI would get for {ip}:", flush=True)
            print("     " + json.dumps(compress(ip, events)), flush=True)
        if not failed:
            print("   nothing suspicious — the AI would not be asked anything.",
                  flush=True)
        print(flush=True)

        if batch_no == MAX_BATCHES:
            break
        batch_no += 1
        lines = []
        window_start = time.time()

    print(f"Done. Compare sizes with:  wc -l {args.log} {args.out}/batch_*.jsonl")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
