#!/usr/bin/env python3
import urllib.request
import time
import sys
from collections import Counter

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 client.py <LB_IP>")
        sys.exit(1)

    lb_ip = sys.argv[1]
    url = f"http://{lb_ip}:8080/"
    counts = Counter()
    errors = 0
    total = 0

    print(f"Pinging {url} once per second. Ctrl-C to stop.\n")
    try:
        while True:
            total += 1
            t = time.strftime("%H:%M:%S")
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    zone = resp.headers.get("X-Zone", "missing")
                    body = resp.read().decode().strip()
                    counts[zone] += 1
                    print(f"[{t}] #{total:04d} status={resp.status} zone={zone} body={body!r}")
            except Exception as e:
                errors += 1
                counts["ERROR"] += 1
                print(f"[{t}] #{total:04d} ERROR: {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n--- Summary ---")
        print(f"Total requests: {total}")
        print(f"Errors:         {errors}")
        for zone, n in counts.most_common():
            pct = 100.0 * n / total if total else 0
            print(f"  {zone}: {n} ({pct:.1f}%)")

if __name__ == "__main__":
    main()