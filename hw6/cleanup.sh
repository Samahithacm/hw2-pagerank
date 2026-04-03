#!/bin/bash
# ============================================================
# CS528 HW6 - Cleanup Script
# Deletes VM and stops Cloud SQL to save credits
# ============================================================

PROJECT="constant-idiom-485622-f3"
ZONE="us-east1-b"
INSTANCE_NAME="hw6-sql-instance"
VM_NAME="hw6-ml-vm"

echo "CS528 HW6 - Cleanup"
echo "==================="

echo "Deleting VM $VM_NAME..."
gcloud compute instances delete $VM_NAME \
    --zone=$ZONE \
    --project=$PROJECT \
    --quiet 2>/dev/null && echo "  VM deleted." || echo "  VM already deleted or not found."

echo "Stopping Cloud SQL instance $INSTANCE_NAME..."
gcloud sql instances patch $INSTANCE_NAME \
    --activation-policy=NEVER \
    --project=$PROJECT \
    --quiet 2>/dev/null && echo "  Cloud SQL stopped." || echo "  Cloud SQL already stopped or not found."

echo ""
echo "Cleanup complete! Resources freed to save credits."
