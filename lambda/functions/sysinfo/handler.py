"""Agent System Info Upload — stores system snapshots."""

import time
from decimal import Decimal
from shared.response import success, error, parse_body
from shared.auth import get_auth_context
from shared.db import devices_table, system_info_table
from boto3.dynamodb.conditions import Key


# 90-day TTL for system info records
TTL_DAYS = 90


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") != "agent":
        return error("Invalid API key", 401)

    api_key = auth["api_key"]

    # Look up device
    table = devices_table()
    resp = table.query(
        IndexName="api-key-index",
        KeyConditionExpression=Key("api_key").eq(api_key),
    )
    items = resp.get("Items", [])
    if not items:
        return error("Device not found", 401)

    device = items[0]
    device_id = device["device_id"]
    customer_id = device["customer_id"]

    body = parse_body(event)
    now = int(time.time())

    # Store the system info snapshot
    info_record = {
        "device_id": device_id,
        "timestamp": str(now),
        "customer_id": customer_id,
        "hostname": body.get("hostname", ""),
        "ip": body.get("ip", ""),
        "os_version": body.get("os_version", ""),
        "cpu_usage": Decimal(str(body.get("cpu_usage", 0))),
        "ram_total": Decimal(str(body.get("ram_total", 0))),
        "ram_used": Decimal(str(body.get("ram_used", 0))),
        "ram_usage": Decimal(str(body.get("ram_usage", 0))),
        "disk_total": Decimal(str(body.get("disk_total", 0))),
        "disk_used": Decimal(str(body.get("disk_used", 0))),
        "disk_usage": Decimal(str(body.get("disk_usage", 0))),
        "installed_software": body.get("installed_software", []),
        "windows_updates": body.get("windows_updates", []),
        "collected_at": now,
        "ttl": now + (TTL_DAYS * 86400),
    }
    system_info_table().put_item(Item=info_record)

    # Update device record with latest info
    table.update_item(
        Key={"customer_id": customer_id, "device_id": device_id},
        UpdateExpression=(
            "SET last_seen = :ts, #s = :status, hostname = :h, ip = :ip, "
            "os = :os, cpu_usage = :cpu, ram_usage = :ram, disk_usage = :disk"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":ts": now,
            ":status": "online",
            ":h": body.get("hostname", ""),
            ":ip": body.get("ip", ""),
            ":os": body.get("os_version", ""),
            ":cpu": Decimal(str(body.get("cpu_usage", 0))),
            ":ram": Decimal(str(body.get("ram_usage", 0))),
            ":disk": Decimal(str(body.get("disk_usage", 0))),
        },
    )

    return success({"message": "System info recorded", "device_id": device_id})
