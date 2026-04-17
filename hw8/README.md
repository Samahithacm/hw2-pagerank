# HW8 — Load Balancing with Failover on GCP

This directory contains the code for CS528 Homework 8: deploying a zone-aware
Python web server on two GCE VMs in different zones, placed behind a regional
external passthrough Network Load Balancer, and measuring failover and recovery
times.

## Files

- `server.py` — Plain Python HTTP server (port 8080). At startup it queries the
  GCP metadata server for the VM's zone and attaches it to every response via
  the `X-Zone` header. Response body: `Hello from zone <zone>`.
- `client.py` — Sends one HTTP GET per second to a given LB IP, prints the
  `X-Zone` header from each response, and prints a summary of per-zone counts
  and errors on Ctrl-C.
- `startup.sh` — (Optional) The startup script used when creating the VMs.
  It installs Python 3 and git, clones this repo, and launches `server.py`.

## Running the client locally

```bash
python3 client.py <LB_IP>
```

## Architecture

- 2 × e2-small VMs running Debian 12 (`hw8-vm-a` in us-central1-a, `hw8-vm-b`
  in us-central1-b)
- Regional external passthrough Network LB on TCP port 8080
- HTTP health check: port 8080, path `/`, interval 5 s, timeout 3 s,
  thresholds 2/2

## Results

- Failover detection: ~8 seconds
- Recovery detection: ~10–15 seconds
- 2334 requests over the full experiment, 19 errors (0.8%)