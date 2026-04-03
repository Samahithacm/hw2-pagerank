#!/bin/bash
if [ -f /var/log/startup_already_done ]; then
    echo "Startup already ran. Skipping."
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive

echo "Waiting for network..."
for i in $(seq 1 30); do
    if curl -s --max-time 3 http://metadata.google.internal/computeMetadata/v1/ -H "Metadata-Flavor: Google" > /dev/null 2>&1; then
        echo "Network is up."
        break
    fi
    echo "  Attempt $i: network not ready, waiting..."
    sleep 5
done

apt-get update -y
apt-get install -y python3

gsutil cp gs://bu-cs528-mahicm13/hw5-scripts/reporter.py /home/reporter.py

nohup python3 /home/reporter.py > /var/log/reporter.log 2>&1 &

touch /var/log/startup_already_done
echo "Reporter started."
