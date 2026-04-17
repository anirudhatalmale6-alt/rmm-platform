# RMM Platform — Deployment Guide

## Prerequisites

- AWS Account with admin access
- AWS CLI v2 installed and configured
- AWS SAM CLI (`pip install aws-sam-cli`)
- Python 3.12+

## Step-by-Step Deployment

### 1. Deploy Infrastructure

```bash
cd deploy/
./deploy.sh prod
```

This creates:
- 8 DynamoDB tables
- 1 S3 data bucket
- Lambda functions for all endpoints
- API Gateway with all routes
- IAM roles and policies

Note the API URL from the output.

### 2. Create Root Admin

```bash
./create-root-admin.sh <api-url> admin@yourdomain.com YourSecurePassword
```

This creates:
- ROOT MSP record in DynamoDB
- First root admin user
- Returns a bearer token for immediate use

### 3. Create an MSP

```bash
./create-msp.sh <api-url> "Your MSP Name" <bearer-token>
```

### 4. Create an MSP Admin User

```bash
./create-user.sh <api-url> msp-admin@partner.com Password123 msp_admin <msp-id> <bearer-token>
```

### 5. Create a Customer

```bash
./create-customer.sh <api-url> "Customer Name" <msp-id> <bearer-token>
```

### 6. Generate Registration Token

```bash
./create-reg-token.sh <api-url> <customer-id> <bearer-token>
```

### 7. Install Agent on Windows

Copy the `agent/` folder to the target Windows machine, then run as Administrator:

```
install.bat <api-url> <registration-token>
```

## Updating the Platform

To update Lambda functions after code changes:

```bash
cd deploy/
./deploy.sh prod
```

SAM handles incremental updates — only changed functions are redeployed.

## Environments

You can run multiple environments (dev, staging, prod) side by side:

```bash
./deploy.sh dev      # Creates rmm-dev stack
./deploy.sh staging  # Creates rmm-staging stack
./deploy.sh prod     # Creates rmm-prod stack
```

Each environment gets its own DynamoDB tables, Lambda functions, and API Gateway.

## Tear Down

To remove everything:

```bash
aws cloudformation delete-stack --stack-name rmm-prod --region ap-southeast-2
```

Note: DynamoDB tables and S3 buckets may need to be emptied first if they contain data.

## Cost Estimate (100 devices)

| Service | Estimated Monthly Cost |
|---------|----------------------|
| DynamoDB (PAY_PER_REQUEST) | ~$5-10 |
| Lambda (100 devices x 12 calls/hr x 730 hrs) | ~$1-2 |
| API Gateway (same call volume) | ~$3-4 |
| S3 (data bucket) | ~$1 |
| **Total** | **~$10-17/month** |

Costs scale linearly with device count. At 1000 devices, expect ~$100-170/month.
