"""Command Management — create commands and list command status."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import (
    get_auth_context, is_root, is_msp_admin, can_access_customer,
)
from shared.db import (
    commands_table, devices_table, customers_table, groups_table,
    get_item, query_by_partition, get_all_customers_for_msp_tree,
    get_customers_for_msp,
)
from boto3.dynamodb.conditions import Key


# Valid command types
COMMAND_TYPES = [
    "run_script",
    "download_and_install",
    "upload_config",
    "restart_service",
    "custom",
]


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    command_id = path_params.get("command_id")

    if method == "GET" and not command_id:
        return list_commands(auth, event)
    elif method == "GET" and command_id:
        return get_command(auth, command_id, event)
    elif method == "POST":
        return create_command(auth, event)
    else:
        return error("Method not allowed", 405)


def list_commands(auth, event):
    """List commands visible to the current user."""
    qs = event.get("queryStringParameters") or {}
    customer_id_filter = qs.get("customer_id")
    status_filter = qs.get("status")
    device_id_filter = qs.get("device_id")

    if device_id_filter:
        # List commands for a specific device
        items = query_by_partition(commands_table(), "device_id", device_id_filter)
        if status_filter:
            items = [c for c in items if c.get("status") == status_filter]
        return success({"commands": items})

    if customer_id_filter:
        customer = get_item(customers_table(), {"customer_id": customer_id_filter})
        if not customer or not can_access_customer(auth, customer):
            return error("Access denied", 403)
        # Query by customer using GSI
        kwargs = {
            "IndexName": "customer-status-index",
            "KeyConditionExpression": Key("customer_id").eq(customer_id_filter),
        }
        if status_filter:
            kwargs["KeyConditionExpression"] = (
                Key("customer_id").eq(customer_id_filter)
                & Key("status").eq(status_filter)
            )
        resp = commands_table().query(**kwargs)
        return success({"commands": resp.get("Items", [])})

    return error("customer_id or device_id query parameter is required")


def get_command(auth, command_id, event):
    """Get a single command by ID."""
    qs = event.get("queryStringParameters") or {}
    device_id = qs.get("device_id")

    if not device_id:
        return error("device_id query parameter is required")

    cmd = get_item(commands_table(), {
        "device_id": device_id, "command_id": command_id
    })
    if not cmd:
        return error("Command not found", 404)

    return success(cmd)


def create_command(auth, event):
    """Create a command targeting device(s).

    target_type: device, group, customer, msp
    target_id: the ID of the target
    """
    body = parse_body(event)

    cmd_type = body.get("type", "").strip()
    if cmd_type not in COMMAND_TYPES:
        return error(f"Invalid type. Must be one of: {', '.join(COMMAND_TYPES)}")

    target_type = body.get("target_type", "device")
    target_id = body.get("target_id", "").strip()
    payload = body.get("payload", {})
    timeout = body.get("timeout", 1800)  # 30 min default

    if not target_id:
        return error("target_id is required")

    # Resolve target to a list of device records
    devices = _resolve_target_devices(auth, target_type, target_id)
    if isinstance(devices, dict):
        # It's an error response
        return devices

    if not devices:
        return error("No devices found for the specified target")

    # Create a command record for each device
    now = int(time.time())
    batch_id = str(uuid.uuid4())
    created_commands = []

    for device in devices:
        command_id = str(uuid.uuid4())
        cmd = {
            "device_id": device["device_id"],
            "command_id": command_id,
            "batch_id": batch_id,
            "customer_id": device["customer_id"],
            "type": cmd_type,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "status": "pending",
            "created_by": auth.get("user_id", "system"),
            "created_at": now,
            "timeout": timeout,
        }
        commands_table().put_item(Item=cmd)
        created_commands.append({
            "command_id": command_id,
            "device_id": device["device_id"],
            "hostname": device.get("hostname", ""),
        })

    return success({
        "batch_id": batch_id,
        "commands_created": len(created_commands),
        "commands": created_commands,
    }, 201)


def _resolve_target_devices(auth, target_type, target_id):
    """Resolve a target (device/group/customer/msp) to a list of device records."""

    if target_type == "device":
        # Find the device
        table = devices_table()
        resp = table.scan(
            FilterExpression="device_id = :did",
            ExpressionAttributeValues={":did": target_id},
        )
        items = resp.get("Items", [])
        if not items:
            return error("Device not found", 404)
        device = items[0]
        customer = get_item(customers_table(), {"customer_id": device["customer_id"]})
        if not customer or not can_access_customer(auth, customer):
            return error("Access denied", 403)
        return items

    elif target_type == "group":
        # Get all devices in a group
        resp = devices_table().query(
            IndexName="group-index",
            KeyConditionExpression=Key("group_id").eq(target_id),
        )
        devices = resp.get("Items", [])
        if not devices:
            return error("No devices in this group", 404)
        # Verify access via the customer
        customer = get_item(customers_table(), {
            "customer_id": devices[0]["customer_id"]
        })
        if not customer or not can_access_customer(auth, customer):
            return error("Access denied", 403)
        return devices

    elif target_type == "customer":
        customer = get_item(customers_table(), {"customer_id": target_id})
        if not customer or not can_access_customer(auth, customer):
            return error("Access denied", 403)
        return query_by_partition(devices_table(), "customer_id", target_id)

    elif target_type == "msp":
        # Get all customers for this MSP, then all their devices
        if is_root(auth) or (is_msp_admin(auth) and auth["entity_id"] == target_id):
            customers = get_customers_for_msp(target_id)
            all_devices = []
            for c in customers:
                devs = query_by_partition(
                    devices_table(), "customer_id", c["customer_id"]
                )
                all_devices.extend(devs)
            return all_devices
        return error("Access denied", 403)

    return error(f"Invalid target_type: {target_type}")
