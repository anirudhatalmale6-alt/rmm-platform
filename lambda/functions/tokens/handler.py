"""Registration Token Management — generate tokens for agent registration."""

import uuid
import time
from shared.response import success, error, parse_body
from shared.auth import get_auth_context, can_access_customer
from shared.db import reg_tokens_table, customers_table, get_item


# Token valid for 24 hours
TOKEN_TTL = 86400


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") == "agent":
        return error("Authentication required", 401)

    method = event.get("httpMethod", "GET")

    if method == "POST":
        return create_token(auth, event)
    elif method == "GET":
        return list_tokens(auth, event)
    else:
        return error("Method not allowed", 405)


def create_token(auth, event):
    """Generate a registration token for a customer."""
    body = parse_body(event)
    customer_id = body.get("customer_id", "").strip()

    if not customer_id:
        return error("customer_id is required")

    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)

    now = int(time.time())
    token = f"reg-{uuid.uuid4().hex}"

    token_item = {
        "token": token,
        "customer_id": customer_id,
        "created_by": auth.get("user_id", "system"),
        "created_at": now,
        "ttl": now + TOKEN_TTL,
        "used": False,
    }
    reg_tokens_table().put_item(Item=token_item)

    return success({
        "token": token,
        "customer_id": customer_id,
        "expires_at": now + TOKEN_TTL,
        "message": "Use this token during agent installation to register the device.",
    }, 201)


def list_tokens(auth, event):
    """List active (unused, non-expired) tokens."""
    qs = event.get("queryStringParameters") or {}
    customer_id = qs.get("customer_id")

    if not customer_id:
        return error("customer_id query parameter is required")

    customer = get_item(customers_table(), {"customer_id": customer_id})
    if not customer:
        return error("Customer not found", 404)
    if not can_access_customer(auth, customer):
        return error("Access denied", 403)

    now = int(time.time())
    table = reg_tokens_table()
    resp = table.scan(
        FilterExpression="customer_id = :cid AND used = :u AND #t > :now",
        ExpressionAttributeNames={"#t": "ttl"},
        ExpressionAttributeValues={
            ":cid": customer_id,
            ":u": False,
            ":now": now,
        },
    )

    return success({"tokens": resp.get("Items", [])})
