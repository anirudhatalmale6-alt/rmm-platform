#!/usr/bin/env bash
# =============================================================================
# create-customer.sh — Create a customer under an MSP
# =============================================================================
# Usage:  ./create-customer.sh <api-url> <customer-name> <msp-id> <bearer-token>
# Example: ./create-customer.sh https://abc123.../prod "Acme Corp" abc-123 eyJhb...
#
# Automatically creates the Default device group for the customer.
# =============================================================================

set -euo pipefail

if [ $# -ne 4 ]; then
  echo "Usage: $0 <api-url> <customer-name> <msp-id> <bearer-token>"
  exit 1
fi

API_URL="$1"
CUSTOMER_NAME="$2"
MSP_ID="$3"
TOKEN="$4"

log() { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }

log "Creating customer: $CUSTOMER_NAME (under MSP: $MSP_ID)"

RESPONSE=$(curl -s -X POST "${API_URL}/admin/customers" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "'"$CUSTOMER_NAME"'",
    "msp_id": "'"$MSP_ID"'"
  }')

CUSTOMER_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('customer_id',''))" 2>/dev/null || echo "")

if [ -z "$CUSTOMER_ID" ]; then
  echo "[ERROR] Failed to create customer:"
  echo "$RESPONSE"
  exit 1
fi

DEFAULT_GROUP_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('default_group_id',''))" 2>/dev/null || echo "")

echo ""
echo "=============================================="
echo "  CUSTOMER CREATED"
echo "=============================================="
echo ""
echo "  Name:             $CUSTOMER_NAME"
echo "  Customer ID:      $CUSTOMER_ID"
echo "  MSP ID:           $MSP_ID"
echo "  Default Group ID: $DEFAULT_GROUP_ID"
echo ""
echo "  NEXT STEPS:"
echo "    1. Generate a registration token for agent installation:"
echo "       ./create-reg-token.sh $API_URL $CUSTOMER_ID $TOKEN"
echo ""
echo "    2. Create additional device groups (optional):"
echo "       curl -X POST ${API_URL}/admin/customers/${CUSTOMER_ID}/groups \\"
echo "         -H 'Authorization: Bearer $TOKEN' \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -d '{\"name\": \"Servers\"}'"
echo ""
echo "=============================================="
