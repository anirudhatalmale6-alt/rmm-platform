"""User Management + Authentication — CRUD for portal users and login."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import (
    get_auth_context, is_root, is_msp_admin,
    hash_password, verify_password, create_token,
)
from shared.db import users_table, get_item
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    user_id = path_params.get("user_id")

    if method == "GET" and not user_id:
        return list_users(auth, event)
    elif method == "GET" and user_id:
        return get_user(auth, user_id)
    elif method == "POST":
        return create_user(auth, event)
    elif method == "PUT" and user_id:
        return update_user(auth, user_id, event)
    elif method == "DELETE" and user_id:
        return delete_user(auth, user_id)
    else:
        return error("Method not allowed", 405)


def login_handler(event, context):
    """Login endpoint — returns a bearer token."""
    body = parse_body(event)
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        return error("email and password are required")

    # Look up user by email
    table = users_table()
    resp = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    items = resp.get("Items", [])
    if not items:
        return error("Invalid email or password", 401)

    user = items[0]
    if not verify_password(password, user["password_hash"]):
        return error("Invalid email or password", 401)

    if user.get("status") != "active":
        return error("Account is disabled", 403)

    # Update last login
    table.update_item(
        Key={"user_id": user["user_id"]},
        UpdateExpression="SET last_login = :ts",
        ExpressionAttributeValues={":ts": int(time.time())},
    )

    token = create_token(user["user_id"], user["role"], user["entity_id"])

    return success({
        "token": token,
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "entity_id": user["entity_id"],
    })


def list_users(auth, event):
    """List users visible to the current user."""
    qs = event.get("queryStringParameters") or {}

    table = users_table()

    if is_root(auth):
        resp = table.scan()
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
    elif is_msp_admin(auth):
        # MSP admin can see users in their MSP + their customer users
        resp = table.scan(
            FilterExpression="entity_id = :eid",
            ExpressionAttributeValues={":eid": auth["entity_id"]},
        )
        items = resp.get("Items", [])
    else:
        # Customer admin can see users in their customer
        resp = table.scan(
            FilterExpression="entity_id = :eid",
            ExpressionAttributeValues={":eid": auth["entity_id"]},
        )
        items = resp.get("Items", [])

    # Strip password hashes
    for item in items:
        item.pop("password_hash", None)

    return success({"users": items})


def get_user(auth, user_id):
    user = get_item(users_table(), {"user_id": user_id})
    if not user:
        return error("User not found", 404)

    # Access check: root can see all, others can see same entity only
    if not is_root(auth) and user.get("entity_id") != auth.get("entity_id"):
        return error("Access denied", 403)

    user.pop("password_hash", None)
    return success(user)


def create_user(auth, event):
    """Create a new portal user."""
    body = parse_body(event)
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    role = body.get("role", "")
    entity_id = body.get("entity_id", "")
    name = body.get("name", "").strip()

    if not email or not password or not role or not entity_id:
        return error("email, password, role, and entity_id are required")

    if role not in ("root_admin", "msp_admin", "customer_admin"):
        return error("role must be root_admin, msp_admin, or customer_admin")

    # Permission checks
    if role == "root_admin" and not is_root(auth):
        return error("Only root can create root admins", 403)
    if role == "msp_admin" and not is_root(auth):
        return error("Only root can create MSP admins", 403)
    if role == "customer_admin":
        if not is_root(auth) and not is_msp_admin(auth):
            return error("Insufficient permissions", 403)

    # Check email uniqueness
    table = users_table()
    resp = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
    )
    if resp.get("Items"):
        return error("Email already in use")

    user_id = str(uuid.uuid4())
    user = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "entity_id": entity_id,
        "name": name,
        "status": "active",
        "created_at": int(time.time()),
    }
    table.put_item(Item=user)

    user.pop("password_hash")
    return success(user, 201)


def update_user(auth, user_id, event):
    user = get_item(users_table(), {"user_id": user_id})
    if not user:
        return error("User not found", 404)

    if not is_root(auth) and user.get("entity_id") != auth.get("entity_id"):
        return error("Access denied", 403)

    body = parse_body(event)
    update_expr = []
    expr_values = {}
    expr_names = {}

    if "name" in body:
        update_expr.append("#n = :name")
        expr_names["#n"] = "name"
        expr_values[":name"] = body["name"]
    if "email" in body:
        update_expr.append("email = :email")
        expr_values[":email"] = body["email"].strip().lower()
    if "password" in body:
        update_expr.append("password_hash = :ph")
        expr_values[":ph"] = hash_password(body["password"])
    if "status" in body:
        update_expr.append("#s = :status")
        expr_names["#s"] = "status"
        expr_values[":status"] = body["status"]

    if not update_expr:
        return error("No fields to update")

    kwargs = {
        "Key": {"user_id": user_id},
        "UpdateExpression": "SET " + ", ".join(update_expr),
        "ExpressionAttributeValues": expr_values,
    }
    if expr_names:
        kwargs["ExpressionAttributeNames"] = expr_names

    users_table().update_item(**kwargs)

    updated = get_item(users_table(), {"user_id": user_id})
    updated.pop("password_hash", None)
    return success(updated)


def delete_user(auth, user_id):
    if not is_root(auth):
        user = get_item(users_table(), {"user_id": user_id})
        if not user:
            return error("User not found", 404)
        if user.get("entity_id") != auth.get("entity_id"):
            return error("Access denied", 403)

    users_table().delete_item(Key={"user_id": user_id})
    return success({"message": f"User {user_id} deleted"})
