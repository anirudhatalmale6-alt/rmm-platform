"""MSP Management — CRUD for MSP accounts."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import get_auth_context, is_root, can_access_msp
from shared.db import msps_table, get_item, get_sub_msps


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    msp_id = path_params.get("msp_id")

    if method == "GET" and not msp_id:
        return list_msps(auth)
    elif method == "GET" and msp_id:
        return get_msp(auth, msp_id)
    elif method == "POST":
        return create_msp(auth, event)
    elif method == "PUT" and msp_id:
        return update_msp(auth, msp_id, event)
    elif method == "DELETE" and msp_id:
        return delete_msp(auth, msp_id)
    else:
        return error("Method not allowed", 405)


def list_msps(auth):
    """List MSPs visible to the current user."""
    if is_root(auth):
        # Root sees all MSPs
        table = msps_table()
        resp = table.scan()
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        return success({"msps": items})

    # MSP admin sees only their own MSP
    msp = get_item(msps_table(), {"msp_id": auth["entity_id"]})
    if not msp:
        return success({"msps": []})
    return success({"msps": [msp]})


def get_msp(auth, msp_id):
    if not can_access_msp(auth, msp_id):
        return error("Access denied", 403)

    msp = get_item(msps_table(), {"msp_id": msp_id})
    if not msp:
        return error("MSP not found", 404)
    return success(msp)


def create_msp(auth, event):
    """Only root can create MSPs."""
    if not is_root(auth):
        return error("Only root admin can create MSPs", 403)

    body = parse_body(event)
    name = body.get("name", "").strip()
    if not name:
        return error("name is required")

    msp_id = str(uuid.uuid4())
    msp = {
        "msp_id": msp_id,
        "name": name,
        "parent_msp_id": "ROOT",
        "status": "active",
        "created_at": int(time.time()),
        "settings": body.get("settings", {}),
    }
    msps_table().put_item(Item=msp)
    return success(msp, 201)


def update_msp(auth, msp_id, event):
    if not can_access_msp(auth, msp_id):
        return error("Access denied", 403)

    msp = get_item(msps_table(), {"msp_id": msp_id})
    if not msp:
        return error("MSP not found", 404)

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

    msps_table().update_item(
        Key={"msp_id": msp_id},
        UpdateExpression="SET " + ", ".join(update_expr),
        ExpressionAttributeNames=expr_names if expr_names else None,
        ExpressionAttributeValues=expr_values,
    )

    updated = get_item(msps_table(), {"msp_id": msp_id})
    return success(updated)


def delete_msp(auth, msp_id):
    if not is_root(auth):
        return error("Only root admin can delete MSPs", 403)

    msp = get_item(msps_table(), {"msp_id": msp_id})
    if not msp:
        return error("MSP not found", 404)

    if msp_id == "ROOT":
        return error("Cannot delete root MSP", 400)

    msps_table().delete_item(Key={"msp_id": msp_id})
    return success({"message": f"MSP {msp_id} deleted"})
