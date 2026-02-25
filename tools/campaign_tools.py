"""
Campaign metadata tools.
"""

from tools.es_client import run_esql


def get_campaign(campaign_id: str) -> dict | None:
    """Get a single campaign by ID."""
    rows = run_esql(
        f'FROM campaigns | WHERE campaign_id == "{campaign_id}" | LIMIT 1'
    )
    return rows[0] if rows else None


def list_campaigns(channel: str | None = None, status: str = "active") -> list[dict]:
    """List campaigns, optionally filtered by channel and status."""
    query = "FROM campaigns"
    filters = []
    if status:
        filters.append(f'status == "{status}"')
    if channel:
        filters.append(f'channel == "{channel}"')
    if filters:
        query += " | WHERE " + " AND ".join(filters)
    query += " | SORT campaign_id ASC | LIMIT 100"
    return run_esql(query)


def get_campaigns_by_ids(campaign_ids: list[str]) -> list[dict]:
    """Get multiple campaigns by their IDs."""
    if not campaign_ids:
        return []
    id_list = ", ".join(f'"{cid}"' for cid in campaign_ids)
    return run_esql(
        f"FROM campaigns | WHERE campaign_id IN ({id_list}) | LIMIT 100"
    )
