#!/usr/bin/env bash
# =============================================================================
# create-root-admin.sh — Initialize the root MSP and create the first admin
# =============================================================================
# Usage:  ./create-root-admin.sh <api-url> <email> <password>
# Example: ./create-root-admin.sh https://abc123.execute-api.ap-southeast-2.amazonaws.com/prod admin@acme.com SecureP@ss1
#
# This script:
#   1. Creates the ROOT MSP record in DynamoDB (idempotent)
#   2. Creates the first root admin user
#   3. Returns a bearer token for immediate use
#
# Run this ONCE after initial deployment.
# =============================================================================

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <api-url> <email> <password>"
  echo "Example: $0 https://abc123.execute-api.ap-southeast-2.amazonaws.com/prod admin@acme.com MyP@ssword1"
  exit 1
fi

API_URL="$1"
EMAIL="$2"
PASSWORD="$3"

AWS_REGION="${AWS_REGION:-ap-southeast-2}"
ENVIRONMENT="${ENVIRONMENT:-prod}"
PROJECT_PREFIX="${PROJECT_PREFIX:-rmm}"

log()  { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }

# ---------------------------------------------------------------------------
# STEP 1: Create ROOT MSP directly in DynamoDB
# ---------------------------------------------------------------------------
# We write directly to DynamoDB because the API requires authentication,
# and we don't have any users yet (chicken-and-egg problem).
# ---------------------------------------------------------------------------

MSPS_TABLE="${PROJECT_PREFIX}-${ENVIRONMENT}-msps"
USERS_TABLE="${PROJECT_PREFIX}-${ENVIRONMENT}-users"

log "Creating ROOT MSP record..."

aws dynamodb put-item \
  --table-name "$MSPS_TABLE" \
  --item '{
    "msp_id": {"S": "ROOT"},
    "name": {"S": "Root MSP"},
    "parent_msp_id": {"S": "NONE"},
    "status": {"S": "active"},
    "created_at": {"N": "'$(date +%s)'"},
    "settings": {"M": {}}
  }' \
  --condition-expression "attribute_not_exists(msp_id)" \
  --region "$AWS_REGION" 2>/dev/null || log "ROOT MSP already exists — skipping."

# ---------------------------------------------------------------------------
# STEP 2: Create root admin user directly in DynamoDB
# ---------------------------------------------------------------------------

log "Creating root admin user: $EMAIL"

USER_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
SALT=$(python3 -c "import uuid; print(uuid.uuid4().hex)")
PASSWORD_HASH=$(python3 -c "
import hashlib
salt = '$SALT'
password = '$PASSWORD'
hashed = hashlib.sha256((salt + password).encode()).hexdigest()
print(f'{salt}:{hashed}')
")

aws dynamodb put-item \
  --table-name "$USERS_TABLE" \
  --item '{
    "user_id": {"S": "'"$USER_ID"'"},
    "email": {"S": "'"$EMAIL"'"},
    "password_hash": {"S": "'"$PASSWORD_HASH"'"},
    "role": {"S": "root_admin"},
    "entity_id": {"S": "ROOT"},
    "name": {"S": "Root Admin"},
    "status": {"S": "active"},
    "created_at": {"N": "'$(date +%s)'"}
  }' \
  --region "$AWS_REGION"

log "Root admin created."

# ---------------------------------------------------------------------------
# STEP 3: Login to get a bearer token
# ---------------------------------------------------------------------------

log "Logging in to get bearer token..."

LOGIN_RESPONSE=$(curl -s -X POST "${API_URL}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "'"$EMAIL"'",
    "password": "'"$PASSWORD"'"
  }')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

echo ""
echo "=============================================="
echo "  ROOT ADMIN CREATED"
echo "=============================================="
echo ""
echo "  API URL:   $API_URL"
echo "  Email:     $EMAIL"
echo "  User ID:   $USER_ID"
echo "  Role:      root_admin"
echo ""
if [ -n "$TOKEN" ]; then
  echo "  Bearer Token (valid 24h):"
  echo "  $TOKEN"
  echo ""
  echo "  Test with:"
  echo "  curl -H \"Authorization: Bearer $TOKEN\" ${API_URL}/admin/msps"
fi
echo ""
echo "  NEXT STEPS:"
echo "    1. Create an MSP:"
echo "       ./create-msp.sh $API_URL \"<msp-name>\" $TOKEN"
echo ""
echo "=============================================="
