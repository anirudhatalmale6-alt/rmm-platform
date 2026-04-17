"""Agent Command Result — reports command execution results back to the server."""

import time
from shared.response import success, error, parse_body
from shared.auth import get_auth_context
from shared.db import devices_table, commands_table
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    auth = get_auth_context(event)
    if not auth or auth.get("type") != "agent":
        return error("Invalid API key", 401)

    api_key = auth["api_key"]

    # Look up device
    resp = devices_table().query(
        IndexName="api-key-index",
        KeyConditionExpression=Key("api_key").eq(api_key),
    )
    items = resp.get("Items", [])
    if not items:
        return error("Device not found", 401)

    device = items[0]
    device_id = device["device_id"]

    body = parse_body(event)
    command_id = body.get("command_id")
    result_status = body.get("status", "completed")  # completed or failed
    stdout = body.get("stdout", "")
    stderr = body.get("stderr", "")
    exit_code = body.get("exit_code", 0)

    if not command_id:
        return error("command_id is required")

    # Verify the command belongs to this device
    cmd = commands_table().get_item(
        Key={"device_id": device_id, "command_id": command_id}
    ).get("Item")

    if not cmd:
        return error("Command not found", 404)

    # Update command status
    commands_table().update_item(
        Key={"device_id": device_id, "command_id": command_id},
        UpdateExpression=(
            "SET #s = :status, completed_at = :ts, "
            "result_stdout = :stdout, result_stderr = :stderr, "
            "exit_code = :ec"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": result_status,
            ":ts": int(time.time()),
            ":stdout": stdout,
            ":stderr": stderr,
            ":ec": exit_code,
        },
    )

    return success({"message": "Command result recorded", "command_id": command_id})
