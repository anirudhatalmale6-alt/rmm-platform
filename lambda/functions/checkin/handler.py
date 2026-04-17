"""Agent Check-in — heartbeat + fetch pending commands."""

import time
from shared.response import success, error
from shared.auth import get_auth_context
from shared.db import devices_table, commands_table, query_by_partition
from boto3.dynamodb.conditions import Key, Attr


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") != "agent":
        return error("Invalid API key", 401)

    api_key = auth["api_key"]

    # Look up device by API key
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

    # Update last_seen and status
    table.update_item(
        Key={"customer_id": customer_id, "device_id": device_id},
        UpdateExpression="SET last_seen = :ts, #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":ts": int(time.time()),
            ":status": "online",
        },
    )

    # Fetch pending commands for this device
    cmd_table = commands_table()
    resp = cmd_table.query(
        KeyConditionExpression=Key("device_id").eq(device_id),
        FilterExpression=Attr("status").eq("pending"),
    )
    pending_commands = resp.get("Items", [])

    # Mark them as sent
    for cmd in pending_commands:
        cmd_table.update_item(
            Key={"device_id": device_id, "command_id": cmd["command_id"]},
            UpdateExpression="SET #s = :status, sent_at = :ts",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "sent",
                ":ts": int(time.time()),
            },
        )

    return success({
        "device_id": device_id,
        "commands": pending_commands,
        "server_time": int(time.time()),
    })
