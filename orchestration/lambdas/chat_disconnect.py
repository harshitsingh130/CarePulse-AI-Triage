"""WebSocket $disconnect handler.

Cleans up connection record. Self-contained.
"""

import os
import boto3

CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "triage-connections")
dynamodb = boto3.resource("dynamodb")
connections_table = dynamodb.Table(CONNECTIONS_TABLE)


def handler(event, context):
    """Handle WebSocket $disconnect event."""
    connection_id = event["requestContext"]["connectionId"]
    print(f"WebSocket disconnect: {connection_id}")

    connections_table.delete_item(Key={"connectionId": connection_id})
    return {"statusCode": 200, "body": "Disconnected"}
