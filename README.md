# RMM Platform

Multi-tenant Remote Monitoring and Management platform built on AWS serverless infrastructure.

## Features

- Multi-tenant: Root MSP > Sub-MSPs > Customers > Groups > Devices
- Windows agent runs as a service, reports system info, executes commands
- Serverless backend: Lambda + API Gateway + DynamoDB
- Role-based access control (Root, MSP Admin, Customer Admin)
- Command targeting: single device, group, customer, or MSP-wide
- Script execution, software deployment, config management
- 90-day system info retention with auto-cleanup

## Quick Start

```bash
# 1. Deploy infrastructure
cd deploy/
./deploy.sh prod

# 2. Create root admin
./create-root-admin.sh <api-url> admin@yourdomain.com YourPassword

# 3. Create an MSP
./create-msp.sh <api-url> "Your MSP" <token>

# 4. Create a customer
./create-customer.sh <api-url> "Customer Name" <msp-id> <token>

# 5. Generate registration token
./create-reg-token.sh <api-url> <customer-id> <token>

# 6. Install agent on Windows (as Administrator)
install.bat <api-url> <registration-token>
```

## Project Structure

```
rmm-platform/
  cloudformation.yaml          — AWS infrastructure (SAM template)
  deploy/
    deploy.sh                  — Deploy/update infrastructure
    create-root-admin.sh       — Initialize platform
    create-msp.sh              — Create sub-MSP
    create-customer.sh         — Create customer
    create-user.sh             — Create portal user
    create-reg-token.sh        — Generate agent registration token
  lambda/
    shared/                    — Shared utilities (auth, db, response)
    functions/                 — Lambda function handlers
      register/                — Agent registration
      checkin/                 — Agent heartbeat + command fetch
      sysinfo/                 — System info upload
      command_result/          — Command result reporting
      msps/                    — MSP CRUD
      customers/               — Customer CRUD
      groups/                  — Group CRUD
      devices/                 — Device management
      commands/                — Command creation and listing
      tokens/                  — Registration token management
      users/                   — User CRUD + login
  agent/
    agent.py                   — Main agent code
    service.py                 — Windows service wrapper
    system_info.py             — System data collection
    command_executor.py        — Command execution engine
    config.py                  — Configuration management
    install.bat                — Windows installer script
    requirements.txt           — Python dependencies
  docs/
    ARCHITECTURE.md            — System architecture
    DEPLOYMENT.md              — Deployment guide
    API.md                     — API reference
    AGENT.md                   — Agent installation and usage
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design, data model, security
- [Deployment](docs/DEPLOYMENT.md) — Step-by-step deployment guide
- [API Reference](docs/API.md) — All endpoints with examples
- [Agent Guide](docs/AGENT.md) — Installation, configuration, command types
