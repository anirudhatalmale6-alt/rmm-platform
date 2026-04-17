#!/usr/bin/env bash
# =============================================================================
# create-reg-token.sh — Generate a registration token for agent installation
# =============================================================================
# Usage:  ./create-reg-token.sh <api-url> <customer-id> <bearer-token>
#
# The token is valid for 24 hours and can be used once to register an agent.
# =============================================================================

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <api-url> <customer-id> <bearer-token>"
  exit 1
fi

API_URL="$1"
CUSTOMER_ID="$2"
TOKEN="$3"

log() { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }

log "Generating registration token for customer: $CUSTOMER_ID"

RESPONSE=$(curl -s -X POST "${API_URL}/admin/tokens" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "customer_id": "'"$CUSTOMER_ID"'"
  }')

REG_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

if [ -z "$REG_TOKEN" ]; then
  echo "[ERROR] Failed to create registration token:"
  echo "$RESPONSE"
  exit 1
fi

EXPIRES=$(echo "$RESPONSE" | python3 -c "
import sys,json,datetime
ts = json.load(sys.stdin).get('expires_at',0)
print(datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'))
" 2>/dev/null || echo "24 hours from now")

echo ""
echo "=============================================="
echo "  REGISTRATION TOKEN"
echo "=============================================="
echo ""
echo "  Token:       $REG_TOKEN"
echo "  Customer ID: $CUSTOMER_ID"
echo "  Expires:     $EXPIRES"
echo ""
echo "  Use this token when installing the agent:"
echo "    rmm-agent.exe --register --token $REG_TOKEN --api-url $API_URL"
echo ""
echo "=============================================="
