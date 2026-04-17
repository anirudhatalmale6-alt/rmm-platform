#!/usr/bin/env bash
# =============================================================================
# create-user.sh — Create a portal user (MSP admin or customer admin)
# =============================================================================
# Usage:  ./create-user.sh <api-url> <email> <password> <role> <entity-id> <bearer-token>
#
# Roles:
#   root_admin    — sees everything (entity_id = ROOT)
#   msp_admin     — sees one MSP and its customers (entity_id = msp_id)
#   customer_admin — sees one customer only (entity_id = customer_id)
# =============================================================================

set -euo pipefail

if [ $# -ne 6 ]; then
  echo "Usage: $0 <api-url> <email> <password> <role> <entity-id> <bearer-token>"
  echo ""
  echo "Roles: root_admin, msp_admin, customer_admin"
  echo ""
  echo "Examples:"
  echo "  $0 https://api.../prod admin@msp.com Pass123 msp_admin <msp-id> <token>"
  echo "  $0 https://api.../prod user@client.com Pass123 customer_admin <customer-id> <token>"
  exit 1
fi

API_URL="$1"
EMAIL="$2"
PASSWORD="$3"
ROLE="$4"
ENTITY_ID="$5"
TOKEN="$6"

log() { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }

log "Creating user: $EMAIL (role: $ROLE)"

RESPONSE=$(curl -s -X POST "${API_URL}/admin/users" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "email": "'"$EMAIL"'",
    "password": "'"$PASSWORD"'",
    "role": "'"$ROLE"'",
    "entity_id": "'"$ENTITY_ID"'",
    "name": "'"$EMAIL"'"
  }')

USER_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('user_id',''))" 2>/dev/null || echo "")

if [ -z "$USER_ID" ]; then
  echo "[ERROR] Failed to create user:"
  echo "$RESPONSE"
  exit 1
fi

echo ""
echo "=============================================="
echo "  USER CREATED"
echo "=============================================="
echo ""
echo "  Email:     $EMAIL"
echo "  User ID:   $USER_ID"
echo "  Role:      $ROLE"
echo "  Entity ID: $ENTITY_ID"
echo ""
echo "  Login:"
echo "    curl -X POST ${API_URL}/auth/login \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"email\": \"$EMAIL\", \"password\": \"<password>\"}'"
echo ""
echo "=============================================="
