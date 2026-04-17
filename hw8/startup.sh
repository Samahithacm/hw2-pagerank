#!/bin/bash
# HW8 VM startup script. Installs dependencies, clones the repo, and launches
# the web server on boot. Runs as root via GCE startup-script metadata.
set -e
apt-get update
apt-get install -y python3 git
cd /opt
rm -rf app
git clone https://github.com/Samahithacm/Cloud-Computing-cs528.git app
cd /opt/app/hw8
nohup python3 server.py > /var/log/webserver.log 2>&1 &