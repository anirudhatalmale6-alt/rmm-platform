"""Agent Registration — exchanges a registration token for a permanent API key."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.db import (
    reg_tokens_table, devices_table, groups_table, get_item,
    query_by_partition,
)


def lambda_handler(event, context):
    body = parse_body(event)
    token = body.get("registration_token", "").strip()
    hostname = body.get("hostname", "unknown")
    os_info = body.get("os", "unknown")
    ip = body.get("ip", "unknown")

    if not token:
        return error("registration_token is required")

    # Validate the registration token
    token_item = get_item(reg_tokens_table(), {"token": token})
    if not token_item:
        return error("Invalid registration token", 401)

    if token_item.get("used"):
        return error("Registration token already used", 401)

    # Check expiry
    if token_item.get("ttl", 0) < int(time.time()):
        return error("Registration token has expired", 401)

    customer_id = token_item["customer_id"]

    # Find the Default group for this customer
    groups = query_by_partition(groups_table(), "customer_id", customer_id)
    default_group = next(
        (g for g in groups if g.get("name") == "Default"), None
    )
    if not default_group:
        return error("Customer has no Default group — data integrity issue", 500)

    # Create the device
    device_id = str(uuid.uuid4())
    api_key = f"rmm-{uuid.uuid4().hex}"

    device = {
        "customer_id": customer_id,
        "device_id": device_id,
        "api_key": api_key,
        "group_id": default_group["group_id"],
        "hostname": hostname,
        "ip": ip,
        "os": os_info,
        "status": "online",
        "last_seen": int(time.time()),
        "registered_at": int(time.time()),
    }
    devices_table().put_item(Item=device)

    # Mark token as used
    reg_tokens_table().update_item(
        Key={"token": token},
        UpdateExpression="SET used = :t",
        ExpressionAttributeValues={":t": True},
    )

    return success({
        "device_id": device_id,
        "api_key": api_key,
        "customer_id": customer_id,
        "group_id": default_group["group_id"],
        "message": "Device registered successfully",
    }, 201)
