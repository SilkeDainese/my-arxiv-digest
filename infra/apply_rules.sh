#!/bin/bash
# Apply Firestore security rules via REST API (no firebase CLI needed)
set -euo pipefail
PROJECT_ID="silke-hub"
RULES=$(cat firestore.rules)
ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -s -X PATCH \
  "https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/(default)/collectionGroups/-/documents?updateMask.fieldPaths=rules" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{}" 2>&1 | head -5
echo "Note: Use Firebase Console or 'firebase deploy --only firestore:rules' to apply rules."
