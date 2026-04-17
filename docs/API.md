# RMM Platform — API Reference

## Base URL

```
https://<api-id>.execute-api.<region>.amazonaws.com/<environment>
```

## Authentication

### Agent Endpoints
- Header: `X-Api-Key: <agent-api-key>`
- API key is obtained during device registration

### Admin Endpoints
- Header: `Authorization: Bearer <token>`
- Token obtained via POST /auth/login (valid 24 hours)

## Endpoints

---

### POST /auth/login

Get a bearer token for admin operations.

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "your-password"
}
```

**Response (200):**
```json
{
  "token": "eyJhb...",
  "user_id": "uuid",
  "email": "admin@example.com",
  "role": "root_admin",
  "entity_id": "ROOT"
}
```

---

### POST /agent/register

Exchange a registration token for a permanent API key.

**Request:**
```json
{
  "registration_token": "reg-abc123...",
  "hostname": "SERVER001",
  "os": "Windows 10.0.19045 (64bit)",
  "ip": "192.168.1.100"
}
```

**Response (201):**
```json
{
  "device_id": "uuid",
  "api_key": "rmm-abc123...",
  "customer_id": "uuid",
  "group_id": "uuid",
  "message": "Device registered successfully"
}
```

---

### POST /agent/checkin

Heartbeat + fetch pending commands.

**Response (200):**
```json
{
  "device_id": "uuid",
  "commands": [
    {
      "command_id": "uuid",
      "type": "run_script",
      "payload": {"script": "Get-Process", "shell": "powershell"}
    }
  ],
  "server_time": 1700000000
}
```

---

### POST /agent/sysinfo

Upload system information snapshot.

**Request:**
```json
{
  "hostname": "SERVER001",
  "ip": "192.168.1.100",
  "os_version": "Windows 10.0.19045 (64bit)",
  "cpu_usage": 45.2,
  "ram_total": 16.0,
  "ram_used": 8.5,
  "ram_usage": 53.1,
  "disk_total": 500.0,
  "disk_used": 250.0,
  "disk_usage": 50.0,
  "installed_software": [
    {"name": "WireGuard", "version": "0.5.3", "publisher": "WireGuard LLC"}
  ],
  "windows_updates": [
    {"id": "KB5031356", "description": "Security Update", "installed_on": "2024-01-15"}
  ]
}
```

---

### POST /agent/command-result

Report command execution result.

**Request:**
```json
{
  "command_id": "uuid",
  "status": "completed",
  "stdout": "command output...",
  "stderr": "",
  "exit_code": 0
}
```

---

### GET /admin/msps

List MSPs. Root sees all; MSP admin sees own only.

**Response:**
```json
{
  "msps": [
    {"msp_id": "uuid", "name": "Partner IT", "status": "active", "created_at": 1700000000}
  ]
}
```

---

### POST /admin/msps

Create a sub-MSP (root only).

**Request:**
```json
{
  "name": "Partner IT"
}
```

---

### GET /admin/customers?msp_id=<id>

List customers. Filterable by MSP.

---

### POST /admin/customers

Create a customer (auto-creates Default group).

**Request:**
```json
{
  "name": "Acme Corp",
  "msp_id": "uuid"
}
```

---

### GET /admin/customers/{id}/groups

List groups for a customer.

---

### POST /admin/customers/{id}/groups

Create a device group.

**Request:**
```json
{
  "name": "Servers"
}
```

---

### GET /admin/devices?customer_id=<id>&group_id=<id>

List devices. Filterable by customer and/or group.

**Response:**
```json
{
  "devices": [
    {
      "device_id": "uuid",
      "customer_id": "uuid",
      "hostname": "SERVER001",
      "ip": "192.168.1.100",
      "os": "Windows 10.0.19045",
      "status": "online",
      "last_seen": 1700000000,
      "cpu_usage": 45.2,
      "ram_usage": 53.1,
      "disk_usage": 50.0
    }
  ],
  "count": 1
}
```

---

### GET /admin/devices/{id}?customer_id=<id>

Get device detail + last 24 system info snapshots.

---

### POST /admin/commands

Create a command targeting device(s).

**Request:**
```json
{
  "target_type": "device",
  "target_id": "uuid",
  "type": "run_script",
  "payload": {
    "script": "Get-Service | Where-Object {$_.Status -eq 'Stopped'}",
    "shell": "powershell",
    "timeout": 300
  }
}
```

**Target types:**
- `device` — single device
- `group` — all devices in a group
- `customer` — all devices for a customer
- `msp` — all devices across all customers of an MSP

**Command types:**
- `run_script` — Execute script (powershell or cmd)
- `download_and_install` — Download + silent install
- `upload_config` — Place a config file
- `restart_service` — Restart a Windows service
- `custom` — Arbitrary PowerShell

**Response (201):**
```json
{
  "batch_id": "uuid",
  "commands_created": 5,
  "commands": [
    {"command_id": "uuid", "device_id": "uuid", "hostname": "SERVER001"}
  ]
}
```

---

### GET /admin/commands?customer_id=<id>&status=<status>&device_id=<id>

List commands. Filter by customer, status, or device.

---

### POST /admin/tokens

Generate a registration token for agent installation.

**Request:**
```json
{
  "customer_id": "uuid"
}
```

**Response (201):**
```json
{
  "token": "reg-abc123...",
  "customer_id": "uuid",
  "expires_at": 1700086400
}
```

---

### POST /admin/users

Create a portal user.

**Request:**
```json
{
  "email": "admin@partner.com",
  "password": "SecurePass123",
  "role": "msp_admin",
  "entity_id": "uuid",
  "name": "John Smith"
}
```

## Error Responses

All errors return:
```json
{
  "error": "Description of the error"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (missing/invalid fields) |
| 401 | Authentication required or invalid |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 405 | Method not allowed |
| 500 | Internal server error |
