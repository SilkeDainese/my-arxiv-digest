#!/bin/bash
# Create Cloud Scheduler jobs for arxiv-digest-weekly.
# Monday morning run + Saturday prep run.
set -euo pipefail

SA="arxiv-digest-sa@silke-hub.iam.gserviceaccount.com"
MAILER_URL="https://send-digest-sptuemlvjq-ew.a.run.app"
LOC="europe-west1"

gcloud scheduler jobs create http weekly-mailer-job \
    --location="${LOC}" \
    --schedule="0 6 * * 1" \
    --uri="${MAILER_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SA}" \
    --time-zone="UTC" \
    --description="Monday 07:00 CET: arxiv weekly run" \
    --quiet 2>&1 || \
gcloud scheduler jobs update http weekly-mailer-job \
    --location="${LOC}" \
    --schedule="0 6 * * 1" \
    --uri="${MAILER_URL}" \
    --http-method=POST \
    --oidc-service-account-email="${SA}" \
    --time-zone="UTC" --quiet 2>&1

echo "Scheduler jobs configured."
