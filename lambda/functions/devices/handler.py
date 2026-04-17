"""Device Management — list, get, update, delete devices."""

import time
from shared.response import success, error, parse_body
from shared.auth import (
    get_auth_context, is_root, is_msp_admin, can_access_customer,
)
from shared.db import (
    devices_table, customers_table, system_info_table,
    get_item, query_by_partition, get_all_customers_for_msp_tree,
    get_customers_for_msp,
)
from boto3.dynamodb.conditions import Key


# Device is offline if no check-in for 10 minutes
OFFLINE_THRESHOLD = 600
# Device is stale if no check-in for 24 hours
STALE_THRESHOLD = 86400


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    device_id = path_params.get("device_id")

    if method == "GET" and not device_id:
        return list_devices(auth, event)
    elif method == "GET" and device_id:
        return get_device(auth, device_id, event)
    elif method == "PUT" and device_id:
        return update_device(auth, device_id, event)
    elif method == "DELETE" and device_id:
        return delete_device(auth, device_id)
    else:
        return error("Method not allowed", 405)


def _calculate_status(device):
    """Calculate real-time device status based on last_seen."""
    last_seen = device.get("last_seen", 0)
    age = int(time.time()) - last_seen
    if age < OFFLINE_THRESHOLD:
        return "online"
    elif age < STALE_THRESHOLD:
        return "offline"
    else:
        return "stale"


def list_devices(auth, event):
    """List devices visible to the current user."""
    qs = event.get("queryStringParameters") or {}
    customer_id_filter = qs.get("customer_id")
    group_id_filter = qs.get("group_id")

    # Determine which customers the user can see
    if customer_id_filter:
        customer = get_item(customers_table(), {"customer_id": customer_id_filter})
        if not customer or not can_access_customer(auth, customer):
            return error("Access denied", 403)
        customer_ids = [customer_id_filter]
    elif is_root(auth):
        customers = get_all_customers_for_msp_tree("ROOT")
        customer_ids = [c["customer_id"] for c in customers]
    elif is_msp_admin(auth):
        customers = get_customers_for_msp(auth["entity_id"])
        customer_ids = [c["customer_id"] for c in customers]
    elif auth.get("role") == "customer_admin":
        customer_ids = [auth["entity_id"]]
    else:
        customer_ids = []

    # Fetch devices for all visible customers
    all_devices = []
    for cid in customer_ids:
        devices = query_by_partition(devices_table(), "customer_id", cid)
        for d in devices:
            d["status"] = _calculate_status(d)
            # Filter by group if requested
            if group_id_filter and d.get("group_id") != group_id_filter:
                continue
            # Don't expose API key in listings
            d.pop("api_key", None)
            all_devices.append(d)

    return success({"devices": all_devices, "count": len(all_devices)})


def get_device(auth, device_id, event):
    """Get device detail + recent system info history."""
    qs = event.get("queryStringParameters") or {}
    customer_id = qs.get("customer_id")

    # Need customer_id to look up device (it's the partition key)
    if not customer_id:
        # Try to find device by scanning — less efficient but works
        table = devices_table()
        resp = table.scan(
            FilterExpression="device_id = :did",
            ExpressionAttributeValues={":did": device_id},
        )
        items = resp.get("Items", [])
        if not items:
            return error("Device not found", 404)
        device = items[0]
        customer_id = device["customer_id"]
    else:
        device = get_item(devices_table(), {
            "customer_id": customer_id, "device_id": device_id
        })
        if not device:
            return error("Device not found", 404)

    # Check access
    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer or not can_access_customer(auth, customer):
        return error("Access denied", 403)

    device["status"] = _calculate_status(device)
    device.pop("api_key", None)

    # Fetch recent system info (last 24 entries = ~6 hours at 15-min intervals)
    history = system_info_table().query(
        KeyConditionExpression=Key("device_id").eq(device_id),
        ScanIndexForward=False,
        Limit=24,
    ).get("Items", [])

    return success({"device": device, "system_info_history": history})


def update_device(auth, device_id, event):
    """Update device (e.g., move to different group)."""
    body = parse_body(event)
    customer_id = body.get("customer_id")
    if not customer_id:
        return error("customer_id is required in body")

    device = get_item(devices_table(), {
        "customer_id": customer_id, "device_id": device_id
    })
    if not device:
        return error("Device not found", 404)

    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer or not can_access_customer(auth, customer):
        return error("Access denied", 403)

    update_expr = []
    expr_values = {}

    if "group_id" in body:
        update_expr.append("group_id = :gid")
        expr_values[":gid"] = body["group_id"]
    if "hostname" in body:
        update_expr.append("hostname = :h")
        expr_values[":h"] = body["hostname"]

    if not update_expr:
        return error("No fields to update")

    devices_table().update_item(
        Key={"customer_id": customer_id, "device_id": device_id},
        UpdateExpression="SET " + ", ".join(update_expr),
        ExpressionAttributeValues=expr_values,
    )

    updated = get_item(devices_table(), {
        "customer_id": customer_id, "device_id": device_id
    })
    updated.pop("api_key", None)
    return success(updated)


def delete_device(auth, device_id):
    """Delete a device."""
    # Find the device first
    table = devices_table()
    resp = table.scan(
        FilterExpression="device_id = :did",
        ExpressionAttributeValues={":did": device_id},
    )
    items = resp.get("Items", [])
    if not items:
        return error("Device not found", 404)

    device = items[0]
    customer_id = device["customer_id"]

    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer or not can_access_customer(auth, customer):
        return error("Access denied", 403)

    table.delete_item(Key={"customer_id": customer_id, "device_id": device_id})
    return success({"message": f"Device {device_id} deleted"})
