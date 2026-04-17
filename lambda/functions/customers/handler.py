"""Customer Management — CRUD for customers under MSPs."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import (
    get_auth_context, is_root, is_msp_admin, can_access_customer,
)
from shared.db import (
    customers_table, groups_table, get_item,
    get_customers_for_msp, get_all_customers_for_msp_tree,
)


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    customer_id = path_params.get("customer_id")

    if method == "GET" and not customer_id:
        return list_customers(auth, event)
    elif method == "GET" and customer_id:
        return get_customer(auth, customer_id)
    elif method == "POST":
        return create_customer(auth, event)
    elif method == "PUT" and customer_id:
        return update_customer(auth, customer_id, event)
    elif method == "DELETE" and customer_id:
        return delete_customer(auth, customer_id)
    else:
        return error("Method not allowed", 405)


def list_customers(auth, event):
    """List customers visible to the current user."""
    qs = event.get("queryStringParameters") or {}
    msp_id_filter = qs.get("msp_id")

    if is_root(auth):
        if msp_id_filter:
            items = get_customers_for_msp(msp_id_filter)
        else:
            items = get_all_customers_for_msp_tree("ROOT")
    elif is_msp_admin(auth):
        items = get_customers_for_msp(auth["entity_id"])
    elif auth.get("role") == "customer_admin":
        customer = get_item(customers_table(), {"customer_id": auth["entity_id"]})
        items = [customer] if customer else []
    else:
        items = []

    return success({"customers": items})


def get_customer(auth, customer_id):
    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)
    return success(customer)


def create_customer(auth, event):
    """Root or MSP admin can create customers."""
    body = parse_body(event)
    name = body.get("name", "").strip()
    msp_id = body.get("msp_id", "").strip()

    if not name:
        return error("name is required")
    if not msp_id:
        return error("msp_id is required")

    # Verify the caller can create under this MSP
    if is_root(auth):
        pass  # root can create under any MSP
    elif is_msp_admin(auth):
        if auth["entity_id"] != msp_id:
            return error("Cannot create customer under another MSP", 403)
    else:
        return error("Insufficient permissions", 403)

    customer_id = str(uuid.uuid4())
    now = int(time.time())

    customer = {
        "customer_id": customer_id,
        "msp_id": msp_id,
        "name": name,
        "status": "active",
        "created_at": now,
        "settings": body.get("settings", {}),
    }
    customers_table().put_item(Item=customer)

    # Auto-create Default group
    default_group = {
        "customer_id": customer_id,
        "group_id": str(uuid.uuid4()),
        "name": "Default",
        "created_at": now,
    }
    groups_table().put_item(Item=default_group)

    customer["default_group_id"] = default_group["group_id"]
    return success(customer, 201)


def update_customer(auth, customer_id, event):
    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)

    body = parse_body(event)
    update_expr = []
    expr_values = {}
    expr_names = {}

    if "name" in body:
        update_expr.append("#n = :name")
        expr_names["#n"] = "name"
        expr_values[":name"] = body["name"]
    if "status" in body:
        update_expr.append("#s = :status")
        expr_names["#s"] = "status"
        expr_values[":status"] = body["status"]
    if "settings" in body:
        update_expr.append("settings = :settings")
        expr_values[":settings"] = body["settings"]

    if not update_expr:
        return error("No fields to update")

    customers_table().update_item(
        Key={"customer_id": customer_id},
        UpdateExpression="SET " + ", ".join(update_expr),
        ExpressionAttributeNames=expr_names if expr_names else None,
        ExpressionAttributeValues=expr_values,
    )

    updated = get_item(customers_table(), {"customer_id": customer_id})
    return success(updated)


def delete_customer(auth, customer_id):
    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)

    customers_table().delete_item(Key={"customer_id": customer_id})
    return success({"message": f"Customer {customer_id} deleted"})
