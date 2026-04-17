# RMM Agent — Installation and Usage Guide

## Overview

The RMM Agent is a Python-based Windows service that:
- Reports system information (hostname, IP, OS, CPU, RAM, disk, software, updates)
- Checks in every 5 minutes for pending commands
- Reports full system info every 15 minutes
- Executes commands from the server (scripts, installations, config deployment)

## Requirements

- Windows 10/11 or Windows Server 2019/2022/2025
- Python 3.9+ (with pip)
- Administrator privileges (for service installation)

## Installation

### Automated (Recommended)

1. Copy the `agent/` folder to the target machine
2. Open Command Prompt as Administrator
3. Run:

```
install.bat <api-url> <registration-token>
```

The installer handles everything: dependencies, registration, service installation.

### Manual

1. Install dependencies:

```
pip install psutil pywin32
python -m pywin32_postinstall -install
```

2. Register the agent:

```
python agent.py --register --token <reg-token> --api-url <api-url>
```

3. Install the Windows service:

```
python service.py install
python service.py start
```

## File Locations

| Path | Purpose |
|------|---------|
| C:\ProgramData\RMMAgent\config.json | Agent configuration |
| C:\ProgramData\RMMAgent\logs\agent.log | Agent log file |
| C:\ProgramData\RMMAgent\data\ | Temporary files (downloads, etc.) |

## Configuration

After registration, `config.json` contains:

```json
{
  "api_url": "https://abc123.execute-api.ap-southeast-2.amazonaws.com/prod",
  "api_key": "rmm-abc123...",
  "device_id": "uuid-...",
  "customer_id": "uuid-...",
  "checkin_interval": 300,
  "sysinfo_interval": 900
}
```

- `checkin_interval`: Seconds between check-ins (default: 300 = 5 min)
- `sysinfo_interval`: Seconds between system info reports (default: 900 = 15 min)

Changes take effect on next agent restart.

## Service Management

```
sc query RMMAgent            — Check service status
python service.py start      — Start the service
python service.py stop       — Stop the service
python service.py restart    — Restart the service
python service.py remove     — Uninstall the service
```

## Command Types

The agent can receive and execute these command types:

### run_script
Execute a script or command on the system.

```json
{
  "type": "run_script",
  "payload": {
    "script": "Get-Process | Where-Object {$_.CPU -gt 100}",
    "shell": "powershell",
    "timeout": 300
  }
}
```

### download_and_install
Download and silently install software.

```json
{
  "type": "download_and_install",
  "payload": {
    "url": "https://download.wireguard.com/windows-client/wireguard-installer.exe",
    "filename": "wireguard-installer.exe",
    "args": "/S",
    "timeout": 600
  }
}
```

### upload_config
Place a configuration file on the system.

```json
{
  "type": "upload_config",
  "payload": {
    "content": "[Interface]\nPrivateKey = ...\nAddress = 10.0.0.2/32\n\n[Peer]\nPublicKey = ...\nEndpoint = vpn.example.com:51820\nAllowedIPs = 0.0.0.0/0",
    "destination": "C:\\Program Files\\WireGuard\\wg0.conf"
  }
}
```

Or download from a URL:

```json
{
  "type": "upload_config",
  "payload": {
    "url": "https://configs.example.com/wg0.conf",
    "destination": "C:\\Program Files\\WireGuard\\wg0.conf"
  }
}
```

### restart_service
Restart a Windows service.

```json
{
  "type": "restart_service",
  "payload": {
    "service_name": "WireGuardTunnel$wg0"
  }
}
```

### custom
Run arbitrary PowerShell.

```json
{
  "type": "custom",
  "payload": {
    "script": "Install-WindowsFeature -Name Web-Server -IncludeManagementTools",
    "timeout": 600
  }
}
```

## WireGuard Deployment Example

Push WireGuard to a device in 3 commands via the API:

```bash
# 1. Download and install WireGuard
curl -X POST $API_URL/admin/commands \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "device",
    "target_id": "<device-id>",
    "type": "download_and_install",
    "payload": {
      "url": "https://download.wireguard.com/windows-client/wireguard-installer.exe",
      "filename": "wireguard-installer.exe",
      "args": "/S"
    }
  }'

# 2. Upload WireGuard config
curl -X POST $API_URL/admin/commands \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "device",
    "target_id": "<device-id>",
    "type": "upload_config",
    "payload": {
      "content": "[Interface]\nPrivateKey = ...\nAddress = 10.0.0.2/32\n\n[Peer]\nPublicKey = ...\nEndpoint = vpn.example.com:51820\nAllowedIPs = 0.0.0.0/0",
      "destination": "C:\\Program Files\\WireGuard\\Data\\Configurations\\wg0.conf.dpapi"
    }
  }'

# 3. Start the WireGuard tunnel
curl -X POST $API_URL/admin/commands \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_type": "device",
    "target_id": "<device-id>",
    "type": "custom",
    "payload": {
      "script": "& \"C:\\Program Files\\WireGuard\\wireguard.exe\" /installtunnelservice \"C:\\Program Files\\WireGuard\\Data\\Configurations\\wg0.conf.dpapi\""
    }
  }'
```

## Troubleshooting

**Agent won't start:**
- Check `C:\ProgramData\RMMAgent\logs\agent.log`
- Verify config.json has valid api_url and api_key
- Ensure Python and dependencies are installed

**Registration fails:**
- Token may be expired (valid 24 hours) — generate a new one
- Check API URL is correct (include /prod or /dev)
- Verify network connectivity to AWS

**Commands not executing:**
- Check agent log for errors
- Verify agent is checking in (last_seen in device record)
- Ensure the command payload is valid JSON

**Service crashes:**
- Check Windows Event Viewer > Application logs
- Check agent.log for stack traces
- Ensure pywin32 post-install was run: `python -m pywin32_postinstall -install`
