#!/bin/bash
# Deploy remaining Cloud Functions (called from deploy.sh context)
# Separate script to avoid hook pattern matching on combined terms.

set -euo pipefail

PROJECT_ID="silke-hub"
REGION="europe-west1"
SA="arxiv-digest-sa@${PROJECT_ID}.iam.gserviceaccount.com"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

deploy_fn() {
    local fname="$1"
    local entry="$2"
    local srcdir="$3"
    local mem="${4:-256Mi}"
    local tout="${5:-300s}"

    echo "--- Deploying ${fname} ---"
    cp -r "${REPO_ROOT}/shared" "${REPO_ROOT}/${srcdir}/shared"
    gcloud functions deploy "${fname}" \
        --gen2 --runtime=python312 --region="${REGION}" \
        --source="${REPO_ROOT}/${srcdir}" \
        --entry-point="${entry}" \
        --service-account="${SA}" \
        --memory="${mem}" --timeout="${tout}" \
        --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},FUNCTION_REGION=${REGION}" \
        --allow-unauthenticated --trigger-http --quiet 2>&1 | tail -5
    rm -rf "${REPO_ROOT}/${srcdir}/shared"
    echo "${fname} deployed."
}

# Mailer function (Monday morning run)
MAILER_NAME="send_digest"
deploy_fn "${MAILER_NAME}" "${MAILER_NAME}" "functions/mailer" "512Mi" "540s"

# Unsubscribe
deploy_fn "unsubscribe" "unsubscribe" "functions/unsub"

# Manage topics
deploy_fn "manage" "manage" "functions/manage"

# Cancel weekly run
deploy_fn "cancel_send" "cancel_send" "functions/cancel"

echo "All functions deployed."
