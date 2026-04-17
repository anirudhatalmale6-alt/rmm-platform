# RMM Platform — Architecture

## Overview

A multi-tenant Remote Monitoring and Management platform built on AWS serverless infrastructure.

## System Components

```
+-------------------+         +---------------------------+
|  Windows Agent    |  HTTPS  |  AWS API Gateway          |
|  (per endpoint)   |-------->|  REST API                 |
+-------------------+         +---------------------------+
                                        |
                              +---------+---------+
                              |  AWS Lambda        |
                              |  (Python 3.12)     |
                              +---------+---------+
                                        |
                    +-------------------+-------------------+
                    |                   |                   |
              +-----+-----+     +------+------+     +------+------+
              | DynamoDB    |     | DynamoDB    |     |   S3        |
              | (8 tables)  |     | (commands)  |     | (data)      |
              +-------------+     +-------------+     +-------------+
```

## Multi-Tenant Hierarchy

```
Root MSP (platform owner)
  |
  +-- MSP A (managed service provider)
  |     +-- Customer A1
  |     |     +-- Group: Default
  |     |     +-- Group: Servers
  |     |     +-- Device: server001
  |     |     +-- Device: workstation01
  |     +-- Customer A2
  |           +-- Group: Default
  |           +-- Device: laptop01
  |
  +-- MSP B
        +-- Customer B1
              +-- Group: Default
              +-- Device: server001
```

## Data Model

### Tables

| Table | PK | SK | GSIs | Purpose |
|-------|----|----|------|---------|
| msps | msp_id | — | — | MSP accounts |
| customers | customer_id | — | msp_id | Customer accounts |
| groups | customer_id | group_id | — | Device groups |
| devices | customer_id | device_id | api_key, group_id | Registered agents |
| system-info | device_id | timestamp | — | System snapshots (90d TTL) |
| commands | device_id | command_id | customer_id+status | Pending/completed commands |
| users | user_id | — | email | Portal users |
| reg-tokens | token | — | — | Registration tokens (24h TTL) |

### Relationships

- MSP 1:N Customers
- Customer 1:N Groups
- Customer 1:N Devices
- Group 1:N Devices
- Device 1:N SystemInfo (time series)
- Device 1:N Commands

## Security Model

### Roles

| Role | Scope | Can Create |
|------|-------|------------|
| root_admin | Everything | MSPs, customers, users |
| msp_admin | Own MSP + its customers | Customers, users, tokens |
| customer_admin | Own customer only | View devices, view info |

### Agent Authentication

- Agents authenticate via `X-Api-Key` header
- API key is generated during registration (one-time token exchange)
- Each API key is tied to exactly one device and one customer
- Agents can only access their own data (enforced server-side)

### User Authentication

- Portal users authenticate via email/password
- Login returns a signed bearer token (24h expiry)
- Token contains: user_id, role, entity_id
- All admin endpoints validate the token and enforce role-based access

## API Endpoints

### Agent Endpoints (X-Api-Key auth)

| Method | Path | Purpose |
|--------|------|---------|
| POST | /agent/register | Exchange reg token for API key |
| POST | /agent/checkin | Heartbeat + fetch commands |
| POST | /agent/sysinfo | Upload system info |
| POST | /agent/command-result | Report command result |

### Admin Endpoints (Bearer token auth)

| Method | Path | Purpose |
|--------|------|---------|
| POST | /auth/login | Get bearer token |
| GET/POST | /admin/msps | List/create MSPs |
| GET/PUT/DELETE | /admin/msps/{id} | Manage MSP |
| GET/POST | /admin/customers | List/create customers |
| GET/PUT/DELETE | /admin/customers/{id} | Manage customer |
| GET/POST | /admin/customers/{id}/groups | List/create groups |
| DELETE | /admin/customers/{id}/groups/{id} | Delete group |
| GET | /admin/devices | List devices |
| GET/PUT/DELETE | /admin/devices/{id} | Manage device |
| GET/POST | /admin/commands | List/create commands |
| GET | /admin/commands/{id} | Get command detail |
| GET/POST | /admin/tokens | List/create reg tokens |
| GET/POST | /admin/users | List/create users |
| GET/PUT/DELETE | /admin/users/{id} | Manage user |

## Command Flow

```
Admin                  API Gateway        Lambda         DynamoDB        Agent
  |                       |                 |               |              |
  |-- POST /commands ---->|                 |               |              |
  |                       |-- invoke ------>|               |              |
  |                       |                 |-- put cmd --->| (pending)    |
  |<-- 201 created -------|<-- response ----|               |              |
  |                       |                 |               |              |
  |                       |                 |               |    (5 min)   |
  |                       |                 |               |              |
  |                       |<-- POST /checkin ---------------|              |
  |                       |-- invoke ------>|               |              |
  |                       |                 |-- query cmds->|              |
  |                       |                 |<- pending ----|              |
  |                       |                 |-- update sent>|              |
  |                       |<-- commands ----|               |              |
  |                       |-- response ---->|               |------------->|
  |                       |                 |               |   (execute)  |
  |                       |                 |               |              |
  |                       |<-- POST /command-result --------|              |
  |                       |-- invoke ------>|               |              |
  |                       |                 |-- update ---->| (completed)  |
```

## Scaling Considerations

- DynamoDB PAY_PER_REQUEST: auto-scales, no capacity planning needed
- Lambda: concurrent executions scale automatically (default limit 1000, raisable)
- API Gateway: handles any traffic volume
- SystemInfo TTL: 90-day auto-delete keeps costs under control
- For 1000+ devices, consider:
  - Batch writes for system info
  - SQS queue between API Gateway and Lambda for command creation
  - DynamoDB DAX cache for hot device lookups
