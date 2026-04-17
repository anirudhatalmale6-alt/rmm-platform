#!/usr/bin/env bash
# =============================================================================
# create-msp.sh — Create a sub-MSP account
# =============================================================================
# Usage:  ./create-msp.sh <api-url> <msp-name> <bearer-token>
# Example: ./create-msp.sh https://abc123.execute-api.../prod "Partner IT" eyJhb...
# =============================================================================

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <api-url> <msp-name> <bearer-token>"
  exit 1
fi

API_URL="$1"
MSP_NAME="$2"
TOKEN="$3"

log() { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }

log "Creating MSP: $MSP_NAME"

RESPONSE=$(curl -s -X POST "${API_URL}/admin/msps" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "'"$MSP_NAME"'"
  }')

MSP_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('msp_id',''))" 2>/dev/null || echo "")

if [ -z "$MSP_ID" ]; then
  echo "[ERROR] Failed to create MSP:"
  echo "$RESPONSE"
  exit 1
fi

echo ""
echo "=============================================="
echo "  MSP CREATED"
echo "=============================================="
echo ""
echo "  Name:    $MSP_NAME"
echo "  MSP ID:  $MSP_ID"
echo ""
echo "  NEXT STEPS:"
echo "    1. Create an MSP admin user:"
echo "       ./create-user.sh $API_URL \"admin@partner.com\" \"password\" msp_admin $MSP_ID $TOKEN"
echo ""
echo "    2. Create a customer under this MSP:"
echo "       ./create-customer.sh $API_URL \"Customer Name\" $MSP_ID $TOKEN"
echo ""
echo "=============================================="
