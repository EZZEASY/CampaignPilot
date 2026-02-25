"""
Shared Elasticsearch client and ES|QL helper for CampaignPilot tools.
"""

import os
import sys

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from elasticsearch import Elasticsearch

_client: Elasticsearch | None = None


def get_client() -> Elasticsearch:
    """Return a singleton Elasticsearch client."""
    global _client
    if _client is not None:
        return _client

    host = os.environ.get("ES_HOST")
    api_key = os.environ.get("ES_API_KEY")

    if not host or not api_key:
        print("ERROR: ES_HOST and ES_API_KEY must be set in .env or environment.")
        sys.exit(1)

    _client = Elasticsearch(host, api_key=api_key)
    return _client


def run_esql(query: str) -> list[dict]:
    """Execute an ES|QL query and return results as a list of dicts."""
    es = get_client()
    resp = es.esql.query(query=query, format="json")

    columns = resp.get("columns", [])
    col_names = [c["name"] for c in columns]
    rows = resp.get("values", [])

    return [dict(zip(col_names, row)) for row in rows]
