"""Authentication and authorization helpers."""

import os
import json
import time
import uuid
import hashlib
import hmac
import base64

# Simple JWT-like token using HMAC-SHA256
# In production, use a proper JWT library or Cognito
JWT_SECRET = os.environ.get("JWT_SECRET", "rmm-platform-secret-change-in-production")
TOKEN_EXPIRY = 86400  # 24 hours


def hash_password(password, salt=None):
    """Hash a password with a salt using SHA-256."""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, stored_hash):
    """Verify a password against a stored hash."""
    salt, _ = stored_hash.split(":")
    return hash_password(password, salt) == stored_hash


def create_token(user_id, role, entity_id):
    """Create a simple signed token."""
    payload = {
        "user_id": user_id,
        "role": role,
        "entity_id": entity_id,
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token(token):
    """Verify and decode a token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(
            JWT_SECRET.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_auth_context(event):
    """Extract auth context from the request.

    Returns dict with user_id, role, entity_id or None if unauthenticated.
    Supports both:
    - Bearer token (admin portal users)
    - X-Api-Key header (agents)
    """
    headers = event.get("headers", {}) or {}
    # Normalize header keys to lowercase
    headers = {k.lower(): v for k, v in headers.items()}

    # Check Bearer token first (admin users)
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return verify_token(token)

    # Check API key (agents)
    api_key = headers.get("x-api-key", "")
    if api_key:
        return {"type": "agent", "api_key": api_key}

    return None


def require_admin(auth_ctx):
    """Check that auth context is an admin user (not an agent)."""
    if not auth_ctx:
        return False
    return auth_ctx.get("role") in ("root_admin", "msp_admin", "customer_admin")


def is_root(auth_ctx):
    """Check if the user is a root admin."""
    return auth_ctx and auth_ctx.get("role") == "root_admin"


def is_msp_admin(auth_ctx):
    """Check if the user is an MSP admin."""
    return auth_ctx and auth_ctx.get("role") == "msp_admin"


def can_access_msp(auth_ctx, msp_id):
    """Check if the user can access a given MSP's resources."""
    if is_root(auth_ctx):
        return True
    if is_msp_admin(auth_ctx):
        return auth_ctx.get("entity_id") == msp_id
    return False


def can_access_customer(auth_ctx, customer):
    """Check if the user can access a given customer's resources."""
    if is_root(auth_ctx):
        return True
    if is_msp_admin(auth_ctx):
        return auth_ctx.get("entity_id") == customer.get("msp_id")
    if auth_ctx.get("role") == "customer_admin":
        return auth_ctx.get("entity_id") == customer.get("customer_id")
    return False
