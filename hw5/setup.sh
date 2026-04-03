#!/bin/bash
set -e

PROJECT_ID="constant-idiom-485622-f3"
REGION="us-central1"
ZONE="us-central1-a"
BUCKET="bu-cs528-mahicm13"
SQL_INSTANCE="hw5-sql-instance"
DB_NAME="hw5db"
DB_PASS="cs528hw5pass"

echo "==> Enabling APIs..."
gcloud services enable compute.googleapis.com sqladmin.googleapis.com \
  sql-component.googleapis.com cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com storage.googleapis.com \
  servicenetworking.googleapis.com --project=${PROJECT_ID}

# ---- Cloud SQL ----
echo "==> Setting up Cloud SQL..."
INSTANCE_EXISTS=$(gcloud sql instances list --project=${PROJECT_ID} \
  --filter="name=${SQL_INSTANCE}" --format="value(name)" 2>/dev/null || true)

if [ -n "$INSTANCE_EXISTS" ]; then
    echo "Instance exists. Starting..."
    gcloud sql instances patch ${SQL_INSTANCE} \
      --activation-policy=ALWAYS --project=${PROJECT_ID} --quiet
    echo "Waiting for RUNNABLE state..."
    while true; do
        STATE=$(gcloud sql instances describe ${SQL_INSTANCE} \
          --project=${PROJECT_ID} --format="get(state)")
        [ "$STATE" = "RUNNABLE" ] && break
        echo "  Current state: ${STATE}. Waiting..."
        sleep 10
    done
else
    echo "Creating Cloud SQL instance (5-10 min)..."
    gcloud compute addresses create google-managed-services-default \
      --global --purpose=VPC_PEERING --prefix-length=16 \
      --network=default --project=${PROJECT_ID} 2>/dev/null || true
    gcloud services vpc-peerings connect \
      --service=servicenetworking.googleapis.com \
      --ranges=google-managed-services-default \
      --network=default --project=${PROJECT_ID} 2>/dev/null || true

    gcloud sql instances create ${SQL_INSTANCE} \
      --database-version=MYSQL_8_0 --tier=db-f1-micro \
      --region=${REGION} --root-password=${DB_PASS} \
      --storage-size=10GB --storage-type=HDD \
      --network=default --no-assign-ip \
      --project=${PROJECT_ID} --quiet

    gcloud sql databases create ${DB_NAME} \
      --instance=${SQL_INSTANCE} --project=${PROJECT_ID} --quiet
fi

DB_IP=$(gcloud sql instances describe ${SQL_INSTANCE} \
  --project=${PROJECT_ID} --format="get(ipAddresses[0].ipAddress)")
echo "DB Private IP: ${DB_IP}"

# ---- Service Accounts ----
echo "==> Creating service accounts..."
gcloud iam service-accounts create hw5-webserver-sa \
  --display-name="HW5 Web Server SA" --project=${PROJECT_ID} 2>/dev/null || true
gcloud iam service-accounts create hw5-reporter-sa \
  --display-name="HW5 Reporter SA" --project=${PROJECT_ID} 2>/dev/null || true

for ROLE in roles/storage.objectViewer roles/logging.logWriter roles/cloudsql.client; do
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
      --member="serviceAccount:hw5-webserver-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
      --role="${ROLE}" --quiet 2>/dev/null || true
done
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:hw5-reporter-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter" --quiet 2>/dev/null || true

# ---- Upload scripts to GCS ----
echo "==> Uploading scripts to GCS..."
gsutil cp server.py gs://${BUCKET}/hw5-scripts/server.py
gsutil cp reporter.py gs://${BUCKET}/hw5-scripts/reporter.py

# ---- Static IP ----
echo "==> Reserving static IP..."
gcloud compute addresses create hw5-webserver-ip \
  --region=${REGION} --project=${PROJECT_ID} 2>/dev/null || true
STATIC_IP=$(gcloud compute addresses describe hw5-webserver-ip \
  --region=${REGION} --project=${PROJECT_ID} --format="get(address)")
echo "Static IP: ${STATIC_IP}"

# ---- Firewall ----
echo "==> Creating firewall rules..."
gcloud compute firewall-rules create allow-hw5-webserver-8080 \
  --allow=tcp:8080 --target-tags=hw5-web-server \
  --source-ranges=0.0.0.0/0 --project=${PROJECT_ID} 2>/dev/null || true
gcloud compute firewall-rules create allow-hw5-reporter-9090 \
  --allow=tcp:9090 --target-tags=hw5-reporter-server \
  --source-tags=hw5-web-server --project=${PROJECT_ID} 2>/dev/null || true

# ---- Reporter VM ----
echo "==> Creating Reporter VM..."
gcloud compute instances create hw5-reporter \
  --zone=${ZONE} --machine-type=e2-micro \
  --service-account=hw5-reporter-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --scopes=https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/devstorage.read_only \
  --metadata-from-file=startup-script=startup-reporter.sh \
  --tags=hw5-reporter-server --project=${PROJECT_ID} 2>/dev/null || true

echo "Waiting for reporter to boot..."
sleep 20
REPORTER_IP=$(gcloud compute instances describe hw5-reporter \
  --zone=${ZONE} --project=${PROJECT_ID} \
  --format="get(networkInterfaces[0].networkIP)")
echo "Reporter internal IP: ${REPORTER_IP}"

# ---- Web Server VM ----
echo "==> Creating Web Server VM..."
gcloud compute instances create hw5-webserver \
  --zone=${ZONE} --machine-type=e2-medium \
  --service-account=hw5-webserver-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --address=${STATIC_IP} \
  --metadata=reporter-ip=${REPORTER_IP},db-ip=${DB_IP},db-pass=${DB_PASS} \
  --metadata-from-file=startup-script=startup.sh \
  --tags=hw5-web-server --project=${PROJECT_ID} 2>/dev/null || true

# ---- Schema setup from webserver VM ----
echo "Waiting for webserver to boot and install packages..."
sleep 60
echo "==> Running schema setup from webserver VM..."
gcloud compute ssh hw5-webserver --zone=${ZONE} --project=${PROJECT_ID} --quiet --command="
    pip3 install pymysql --break-system-packages 2>/dev/null
    python3 -c \"
import pymysql
conn = pymysql.connect(host='${DB_IP}', user='root', password='${DB_PASS}', database='${DB_NAME}')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS requests (
    id INT AUTO_INCREMENT PRIMARY KEY, country VARCHAR(100), client_ip VARCHAR(45),
    gender VARCHAR(10), age VARCHAR(10), income VARCHAR(20), is_banned BOOLEAN,
    time_of_day VARCHAR(20), requested_file VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS failed_requests (
    id INT AUTO_INCREMENT PRIMARY KEY, time_of_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    requested_file VARCHAR(255), error_code INT)''')
conn.commit()
print('Schema verified.')
\"
" 2>/dev/null || echo "Schema setup skipped (may already exist)"

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Web server IP: ${STATIC_IP}"
echo "  DB Private IP: ${DB_IP}"
echo "============================================"
