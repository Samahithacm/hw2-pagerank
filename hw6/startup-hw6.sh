#!/bin/bash
# ============================================================
# CS528 HW6 - VM Startup Script
# Installs dependencies and runs ML models
# ============================================================

exec > /var/log/hw6-startup.log 2>&1
echo "=== HW6 Startup Script Started at $(date) ==="

# Wait for network to be ready
echo "Waiting for network..."
MAX_WAIT=150
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s --max-time 5 http://metadata.google.internal/computeMetadata/v1/ -H "Metadata-Flavor: Google" > /dev/null 2>&1; then
        echo "Network is ready after $WAITED seconds."
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "ERROR: Network not ready after $MAX_WAIT seconds."
    exit 1
fi

# Get metadata values
DB_HOST=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/db-host" -H "Metadata-Flavor: Google")
DB_NAME=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/db-name" -H "Metadata-Flavor: Google")
DB_PASS=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/db-pass" -H "Metadata-Flavor: Google")
GCS_BUCKET=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/gcs-bucket" -H "Metadata-Flavor: Google")
GCP_PROJECT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/gcp-project" -H "Metadata-Flavor: Google")

echo "DB_HOST=$DB_HOST"
echo "DB_NAME=$DB_NAME"
echo "GCS_BUCKET=$GCS_BUCKET"
echo "GCP_PROJECT=$GCP_PROJECT"

# Install system packages
echo "Installing system packages..."
apt-get update -y
apt-get install -y python3-pip python3-dev default-libmysqlclient-dev

# Install Python packages
echo "Installing Python packages..."
pip3 install --break-system-packages \
    pymysql==1.1.0 \
    pandas==2.1.4 \
    numpy==1.26.2 \
    scikit-learn==1.3.2 \
    google-cloud-storage==2.13.0 \
    google-auth==2.27.0

# Set environment variable to fix google-auth SSL issue
export GCE_METADATA_SCHEME=http

# Download models.py from GCS bucket
echo "Downloading models.py from GCS..."
gsutil cp gs://$GCS_BUCKET/hw6/models.py /tmp/models.py

# Run the models
echo "Running ML models..."
export DB_HOST=$DB_HOST
export DB_USER=root
export DB_PASS=$DB_PASS
export DB_NAME=$DB_NAME
export GCS_BUCKET=$GCS_BUCKET
export GCP_PROJECT=$GCP_PROJECT
export GCE_METADATA_SCHEME=http

cd /tmp
python3 models.py 2>&1

echo "=== HW6 Startup Script Completed at $(date) ==="
