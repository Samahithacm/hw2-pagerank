#!/bin/bash
set -e

PROJECT_ID="constant-idiom-485622-f3"
ZONE="us-central1-a"
REGION="us-central1"
BUCKET="bu-cs528-mahicm13"
SQL_INSTANCE="hw5-sql-instance"

echo "==> Deleting VMs..."
gcloud compute instances delete hw5-webserver --zone=${ZONE} --project=${PROJECT_ID} --quiet 2>/dev/null || true
gcloud compute instances delete hw5-reporter --zone=${ZONE} --project=${PROJECT_ID} --quiet 2>/dev/null || true

echo "==> Releasing static IP..."
gcloud compute addresses delete hw5-webserver-ip --region=${REGION} --project=${PROJECT_ID} --quiet 2>/dev/null || true

echo "==> Deleting firewall rules..."
gcloud compute firewall-rules delete allow-hw5-webserver-8080 --project=${PROJECT_ID} --quiet 2>/dev/null || true
gcloud compute firewall-rules delete allow-hw5-reporter-9090 --project=${PROJECT_ID} --quiet 2>/dev/null || true

echo "==> Removing scripts from GCS..."
gsutil -m rm -r gs://${BUCKET}/hw5-scripts/ 2>/dev/null || true

echo "==> Stopping Cloud SQL (NOT deleting)..."
gcloud sql instances patch ${SQL_INSTANCE} \
  --activation-policy=NEVER --project=${PROJECT_ID} --quiet 2>/dev/null || true

echo "==> Deleting service accounts..."
gcloud iam service-accounts delete hw5-webserver-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=${PROJECT_ID} --quiet 2>/dev/null || true
gcloud iam service-accounts delete hw5-reporter-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=${PROJECT_ID} --quiet 2>/dev/null || true

echo "Cleanup complete."
