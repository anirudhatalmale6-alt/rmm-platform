"""Group Management — CRUD for device groups within a customer."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import get_auth_context, can_access_customer
from shared.db import (
    customers_table, groups_table, get_item, query_by_partition,
)


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id")
    group_id = path_params.get("group_id")

    if not customer_id:
        return error("customer_id is required in path")

    # Verify access to this customer
    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)

    if method == "GET":
        return list_groups(customer_id)
    elif method == "POST":
        return create_group(customer_id, event)
    elif method == "DELETE" and group_id:
        return delete_group(customer_id, group_id)
    else:
        return error("Method not allowed", 405)


def list_groups(customer_id):
    groups = query_by_partition(groups_table(), "customer_id", customer_id)
    return success({"groups": groups})


def create_group(customer_id, event):
    body = parse_body(event)
    name = body.get("name", "").strip()
    if not name:
        return error("name is required")

    # Check for duplicate name within customer
    existing = query_by_partition(groups_table(), "customer_id", customer_id)
    if any(g["name"] == name for g in existing):
        return error(f"Group '{name}' already exists for this customer")

    group = {
        "customer_id": customer_id,
        "group_id": str(uuid.uuid4()),
        "name": name,
        "created_at": int(time.time()),
    }
    groups_table().put_item(Item=group)
    return success(group, 201)


def delete_group(customer_id, group_id):
    group = get_item(groups_table(), {"customer_id": customer_id, "group_id": group_id})
    if not group:
        return error("Group not found", 404)
    if group.get("name") == "Default":
        return error("Cannot delete the Default group", 400)

    groups_table().delete_item(Key={"customer_id": customer_id, "group_id": group_id})
    return success({"message": f"Group {group_id} deleted"})
