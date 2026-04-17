"""Standard API response helpers."""

import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Handle DynamoDB Decimal types in JSON serialization."""
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)


def success(body, status_code=200):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def error(message, status_code=400):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key",
        },
        "body": json.dumps({"error": message}),
    }


def parse_body(event):
    """Parse JSON body from API Gateway event."""
    body = event.get("body", "")
    if not body:
        return {}
    if isinstance(body, str):
        return json.loads(body)
    return body
