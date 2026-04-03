#!/bin/bash
# ============================================================
# CS528 HW6 - Main Setup & Run Script
# This script:
#   1. Creates Cloud SQL instance and imports data
#   2. Uploads models.py to GCS
#   3. Creates a VM to run ML models
#   4. Waits for models to finish
#   5. Prints output from GCS bucket
#   6. Cleans up (deletes VM, stops database)
# ============================================================

set -e

PROJECT="constant-idiom-485622-f3"
REGION="us-central1"
ZONE="us-east1-b"
INSTANCE_NAME="hw6-sql-instance"
DB_NAME="hw6db"
DB_PASS="cs528hw6pass"
BUCKET="bu-cs528-mahicm13"
VM_NAME="hw6-ml-vm"
VPC_NETWORK="default"

echo "============================================================"
echo "CS528 HW6 - Setup & Run Script"
echo "============================================================"

# ============================================================
# STEP 1: Create Cloud SQL Instance
# ============================================================
echo ""
echo "[STEP 1] Creating Cloud SQL MySQL instance..."
gcloud sql instances create $INSTANCE_NAME \
    --database-version=MYSQL_8_0 \
    --tier=db-f1-micro \
    --region=$REGION \
    --network=$VPC_NETWORK \
    --no-assign-ip \
    --storage-size=10GB \
    --storage-auto-increase \
    --project=$PROJECT \
    --quiet

echo "  Setting root password..."
gcloud sql users set-password root \
    --host=% \
    --instance=$INSTANCE_NAME \
    --password=$DB_PASS \
    --project=$PROJECT \
    --quiet

# Get the private IP
DB_IP=$(gcloud sql instances describe $INSTANCE_NAME \
    --project=$PROJECT \
    --format="value(ipAddresses[0].ipAddress)")
echo "  Cloud SQL Private IP: $DB_IP"

# ============================================================
# STEP 2: Create database and import data
# ============================================================
echo ""
echo "[STEP 2] Creating database and importing professor's data..."
gcloud sql databases create $DB_NAME \
    --instance=$INSTANCE_NAME \
    --project=$PROJECT \
    --quiet

echo "  Importing data from gs://cs528-hw6-data/data.gz..."
gcloud sql import sql $INSTANCE_NAME \
    gs://cs528-hw6-data/data.gz \
    --database=$DB_NAME \
    --project=$PROJECT \
    --quiet

echo "  Database imported successfully!"

# ============================================================
# STEP 3: Upload models.py to GCS
# ============================================================
echo ""
echo "[STEP 3] Uploading models.py to GCS bucket..."
gsutil cp models.py gs://$BUCKET/hw6/models.py
echo "  Uploaded models.py to gs://$BUCKET/hw6/models.py"

# ============================================================
# STEP 4: Create VM with startup script
# ============================================================
echo ""
echo "[STEP 4] Creating ML VM..."

gcloud compute instances create $VM_NAME \
    --zone=$ZONE \
    --machine-type=e2-small \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --scopes=cloud-platform \
    --metadata=db-host=$DB_IP,db-name=$DB_NAME,db-pass=$DB_PASS,gcs-bucket=$BUCKET,gcp-project=$PROJECT \
    --metadata-from-file=startup-script=startup-hw6.sh \
    --project=$PROJECT \
    --quiet

echo "  VM $VM_NAME created in zone $ZONE."

# ============================================================
# STEP 5: Wait for ML models to finish
# ============================================================
echo ""
echo "[STEP 5] Waiting for ML models to complete..."
echo "  (Checking for output files in GCS bucket every 30 seconds)"

MAX_WAIT=900  # 15 minutes max
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if gsutil -q stat gs://$BUCKET/hw6/model_summary.json 2>/dev/null; then
        echo "  Models completed! Output files found in bucket."
        break
    fi
    echo "  Still running... ($WAITED seconds elapsed)"
    sleep 30
    WAITED=$((WAITED + 30))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "  WARNING: Timed out after $MAX_WAIT seconds. Checking VM logs..."
    gcloud compute instances get-serial-port-output $VM_NAME \
        --zone=$ZONE \
        --project=$PROJECT 2>/dev/null | tail -80
fi

# ============================================================
# STEP 6: Print output from GCS bucket
# ============================================================
echo ""
echo "============================================================"
echo "[STEP 6] OUTPUT FILES FROM GCS BUCKET"
echo "============================================================"

echo ""
echo "--- Model 1: IP to Country Results ---"
gsutil cat gs://$BUCKET/hw6/model1_ip_to_country_results.csv | head -20
echo "... (showing first 20 lines)"

echo ""
echo "--- Model 2: Income Prediction Results ---"
gsutil cat gs://$BUCKET/hw6/model2_income_prediction_results.csv | head -20
echo "... (showing first 20 lines)"

echo ""
echo "--- Model Summary ---"
gsutil cat gs://$BUCKET/hw6/model_summary.json

# ============================================================
# STEP 7: Cleanup
# ============================================================
echo ""
echo "============================================================"
echo "[STEP 7] Cleaning up resources..."
echo "============================================================"

echo "  Deleting VM $VM_NAME..."
gcloud compute instances delete $VM_NAME \
    --zone=$ZONE \
    --project=$PROJECT \
    --quiet

echo "  Stopping Cloud SQL instance $INSTANCE_NAME..."
gcloud sql instances patch $INSTANCE_NAME \
    --activation-policy=NEVER \
    --project=$PROJECT \
    --quiet

echo ""
echo "============================================================"
echo "ALL DONE! Resources cleaned up."
echo "  - VM deleted"
echo "  - Cloud SQL stopped"
echo "  - Results available at gs://$BUCKET/hw6/"
echo "============================================================"
