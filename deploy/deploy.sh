#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy the RMM Platform to AWS
# =============================================================================
# Usage:  ./deploy.sh [environment]
# Example: ./deploy.sh prod
#          ./deploy.sh dev
#
# Prerequisites:
#   - AWS CLI v2
#   - AWS SAM CLI (install: pip install aws-sam-cli)
#   - Sufficient IAM permissions (CloudFormation, Lambda, API Gateway,
#     DynamoDB, S3, IAM)
#
# What it does:
#   1. Packages Lambda code into a ZIP
#   2. Uploads to an S3 deployment bucket
#   3. Deploys CloudFormation stack (creates/updates all resources)
#   4. Outputs the API Gateway URL
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-prod}"
PROJECT_PREFIX="rmm"
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
STACK_NAME="${PROJECT_PREFIX}-${ENVIRONMENT}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log()  { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }
warn() { echo "[WARN]  $(date '+%H:%M:%S') — $*"; }

# ---------------------------------------------------------------------------
# PRE-FLIGHT
# ---------------------------------------------------------------------------

log "Deploying RMM Platform"
log "Environment: $ENVIRONMENT"
log "Region:      $AWS_REGION"
log "Stack:       $STACK_NAME"
echo ""

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log "AWS Account: $ACCOUNT_ID"

# Check for SAM CLI
if ! command -v sam &>/dev/null; then
  log "SAM CLI not found. Installing..."
  pip install aws-sam-cli --quiet
fi

# ---------------------------------------------------------------------------
# CREATE DEPLOYMENT BUCKET (if needed)
# ---------------------------------------------------------------------------

DEPLOY_BUCKET="${PROJECT_PREFIX}-${ENVIRONMENT}-deploy-${ACCOUNT_ID}"

if ! aws s3api head-bucket --bucket "$DEPLOY_BUCKET" 2>/dev/null; then
  log "Creating deployment bucket: $DEPLOY_BUCKET"
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$DEPLOY_BUCKET" --region "$AWS_REGION"
  else
    aws s3api create-bucket \
      --bucket "$DEPLOY_BUCKET" \
      --region "$AWS_REGION" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION"
  fi
fi

# ---------------------------------------------------------------------------
# BUILD AND DEPLOY
# ---------------------------------------------------------------------------

cd "$PROJECT_DIR"

log "Building SAM application..."
sam build \
  --template-file cloudformation.yaml \
  --region "$AWS_REGION"

log "Deploying SAM application..."
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "$STACK_NAME" \
  --s3-bucket "$DEPLOY_BUCKET" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$AWS_REGION" \
  --parameter-overrides \
    "Environment=$ENVIRONMENT" \
    "ProjectPrefix=$PROJECT_PREFIX" \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

echo ""
log "Deployment complete!"
echo ""

API_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text \
  --region "$AWS_REGION")

echo "=============================================="
echo "  RMM PLATFORM DEPLOYED"
echo "=============================================="
echo ""
echo "  API URL:     $API_URL"
echo "  Environment: $ENVIRONMENT"
echo "  Region:      $AWS_REGION"
echo "  Stack:       $STACK_NAME"
echo ""
echo "  NEXT STEPS:"
echo "    1. Create root MSP and admin user:"
echo "       ./create-root-admin.sh $API_URL <email> <password>"
echo ""
echo "    2. Create sub-MSPs:"
echo "       ./create-msp.sh $API_URL <msp-name>"
echo ""
echo "=============================================="
