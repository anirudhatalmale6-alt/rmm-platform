"""DynamoDB helper functions."""

import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")


def _table(env_var):
    return dynamodb.Table(os.environ[env_var])


def msps_table():
    return _table("MSPS_TABLE")


def customers_table():
    return _table("CUSTOMERS_TABLE")


def groups_table():
    return _table("GROUPS_TABLE")


def devices_table():
    return _table("DEVICES_TABLE")


def system_info_table():
    return _table("SYSTEM_INFO_TABLE")


def commands_table():
    return _table("COMMANDS_TABLE")


def users_table():
    return _table("USERS_TABLE")


def reg_tokens_table():
    return _table("REG_TOKENS_TABLE")


def get_item(table, key):
    """Get a single item by primary key."""
    resp = table.get_item(Key=key)
    return resp.get("Item")


def query_by_partition(table, pk_name, pk_value, index_name=None):
    """Query all items matching a partition key."""
    kwargs = {"KeyConditionExpression": Key(pk_name).eq(pk_value)}
    if index_name:
        kwargs["IndexName"] = index_name
    items = []
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def get_customers_for_msp(msp_id):
    """Get all customers belonging to an MSP."""
    return query_by_partition(customers_table(), "msp_id", msp_id, "msp-index")


def get_all_customers_for_msp_tree(msp_id):
    """Get all customers visible to an MSP (including sub-MSP customers).

    For root: returns all customers.
    For sub-MSP: returns only their own customers.
    """
    if msp_id == "ROOT":
        # Root sees everything — scan customers table
        table = customers_table()
        items = []
        resp = table.scan()
        items.extend(resp.get("Items", []))
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        return items

    # Sub-MSP: get their own customers
    own_customers = get_customers_for_msp(msp_id)

    # Also get customers of any sub-MSPs under this MSP
    sub_msps = get_sub_msps(msp_id)
    for sub_msp in sub_msps:
        own_customers.extend(get_customers_for_msp(sub_msp["msp_id"]))

    return own_customers


def get_sub_msps(parent_msp_id):
    """Get MSPs whose parent is the given MSP ID."""
    table = msps_table()
    items = []
    resp = table.scan(
        FilterExpression="parent_msp_id = :pid",
        ExpressionAttributeValues={":pid": parent_msp_id},
    )
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(
            FilterExpression="parent_msp_id = :pid",
            ExpressionAttributeValues={":pid": parent_msp_id},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))
    return items
