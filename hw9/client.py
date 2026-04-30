#!/usr/bin/env python3

import requests
import sys
import random

SERVER_IP = sys.argv[1]
PORT = 80   # GKE LoadBalancer exposes port 80

# Pick 200 random files from your bucket
file_ids = random.sample(range(1, 9000), 200)
files = [f"html_files/{i}.html" for i in file_ids]

ok = bad = err = 0
for f in files:
    url = f"http://{SERVER_IP}:{PORT}/{f}"
    try:
        r = requests.get(url, timeout=5)
        print(f"{r.status_code} - {f}")
        if r.status_code == 200:
            ok += 1
        else:
            bad += 1
    except Exception as e:
        print(f"ERROR - {f} - {e}")
        err += 1

print(f"\nSummary: {ok} OK | {bad} non-200 | {err} errors | total {len(files)}")
