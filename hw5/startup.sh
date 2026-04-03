#!/bin/bash
if [ -f /var/log/startup_already_done ]; then
    echo "Startup already ran. Skipping."
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive

# Wait for network to be available (fixes the boot-time network issue)
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
apt-get install -y python3 python3-pip curl ca-certificates
update-ca-certificates

pip3 install --break-system-packages google-cloud-storage pymysql google-auth==2.27.0

gsutil cp gs://bu-cs528-mahicm13/hw5-scripts/server.py /home/server.py

REPORTER_IP=$(curl -sf "http://metadata.google.internal/computeMetadata/v1/instance/attributes/reporter-ip" -H "Metadata-Flavor: Google")
DB_IP=$(curl -sf "http://metadata.google.internal/computeMetadata/v1/instance/attributes/db-ip" -H "Metadata-Flavor: Google")
DB_PASS=$(curl -sf "http://metadata.google.internal/computeMetadata/v1/instance/attributes/db-pass" -H "Metadata-Flavor: Google")

sed -i "s/REPORTER_IP_PLACEHOLDER/${REPORTER_IP}/" /home/server.py
sed -i "s/DB_IP_PLACEHOLDER/${DB_IP}/" /home/server.py
sed -i "s/DB_PASS_PLACEHOLDER/${DB_PASS}/" /home/server.py

# Start server with environment variable to force HTTP for metadata
nohup env GCE_METADATA_SCHEME=http python3 /home/server.py > /var/log/webserver.log 2>&1 &

touch /var/log/startup_already_done
echo "Web server started."
