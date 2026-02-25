"""
Action log tools.
"""

from datetime import datetime, timezone

from tools.es_client import get_client, run_esql


def get_actions(
    campaign_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get action log entries, optionally filtered."""
    query = "FROM action-log"
    filters = []
    if campaign_id:
        filters.append(f'campaign_id == "{campaign_id}"')
    if status:
        filters.append(f'status == "{status}"')
    if filters:
        query += " | WHERE " + " AND ".join(filters)
    query += f" | SORT timestamp DESC | LIMIT {limit}"
    return run_esql(query)


def log_action(
    campaign_id: str,
    channel: str,
    action_type: str,
    description: str,
    parameters: dict | None = None,
) -> dict:
    """Log a new proposed action to the action-log index."""
    es = get_client()
    doc = {
        "action_id": f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "campaign_id": campaign_id,
        "channel": channel,
        "action_type": action_type,
        "status": "proposed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "parameters": parameters or {},
        "outcome": "",
    }
    es.index(index="action-log", document=doc)
    return doc
