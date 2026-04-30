#!/bin/bash
if [ -f /var/log/startup_already_done ]; then
    echo "Startup already ran. Skipping."
    exit 0
fi

apt-get update -y
apt-get install -y python3

gsutil cp gs://bu-cs528-mahicm13/hw9-scripts/reporter.py /home/reporter.py

nohup python3 /home/reporter.py > /var/log/reporter.log 2>&1 &

touch /var/log/startup_already_done
echo "Reporter started."
