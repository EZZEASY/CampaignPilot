#!/usr/bin/env python3
"""
Elasticsearch setup script for CampaignPilot.
Creates indices from mapping files and bulk-writes NDJSON data.

Usage:
    python data/setup_elasticsearch.py              # Create indices + write data
    python data/setup_elasticsearch.py --reset      # Delete existing indices first
    python data/setup_elasticsearch.py --verify     # Check connection + index status only
    python data/setup_elasticsearch.py --no-semantic # Downgrade semantic_text to text
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from elasticsearch import Elasticsearch, helpers

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAPPINGS_DIR = os.path.join(PROJECT_ROOT, "mappings")
DATA_DIR = os.path.join(PROJECT_ROOT, "data_output")

# Index name → mapping file, data file
INDICES = {
    "campaigns":          ("campaigns.json",          "campaigns.ndjson"),
    "channel-metrics":    ("channel-metrics.json",    "channel-metrics.ndjson"),
    "creative-assets":    ("creative-assets.json",    "creative-assets.ndjson"),
    "audience-segments":  ("audience-segments.json",  "audience-segments.ndjson"),
    "competitor-signals": ("competitor-signals.json",  "competitor-signals.ndjson"),
    "budget-ledger":      ("budget-ledger.json",      "budget-ledger.ndjson"),
    "action-log":         ("action-log.json",         "action-log.ndjson"),
    "creative-metrics":   ("creative-metrics.json",   "creative-metrics.ndjson"),
    "website-events":     ("website-events.json",     "website-events.ndjson"),
    "product-catalog":    ("product-catalog.json",    "product-catalog.ndjson"),
    "support-tickets":    ("support-tickets.json",    "support-tickets.ndjson"),
}


def get_es_client() -> Elasticsearch:
    """Create ES client from environment variables."""
    host = os.environ.get("ES_HOST")
    api_key = os.environ.get("ES_API_KEY")

    if not host or not api_key:
        print("ERROR: ES_HOST and ES_API_KEY must be set in .env or environment.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    return Elasticsearch(host, api_key=api_key)


def _process_semantic_fields(properties: dict, inference_id: str | None, no_semantic: bool):
    """Recursively process semantic_text fields in mapping properties."""
    for field_name, field_def in list(properties.items()):
        if field_def.get("type") == "semantic_text":
            if no_semantic or not inference_id:
                properties[field_name] = {"type": "text"}
            else:
                field_def["inference_id"] = inference_id
        # Recurse into nested object properties
        nested = field_def.get("properties")
        if nested:
            _process_semantic_fields(nested, inference_id, no_semantic)


def load_mapping(mapping_file: str, inference_id: str | None, no_semantic: bool) -> dict:
    """Load a mapping JSON file, handling semantic_text fields (including nested)."""
    path = os.path.join(MAPPINGS_DIR, mapping_file)
    with open(path) as f:
        mapping = json.load(f)

    properties = mapping.get("mappings", {}).get("properties", {})
    _process_semantic_fields(properties, inference_id, no_semantic)

    return mapping


def load_ndjson(data_file: str) -> list[dict]:
    """Load an NDJSON file into a list of dicts."""
    path = os.path.join(DATA_DIR, data_file)
    if not os.path.exists(path):
        print(f"  WARNING: {data_file} not found. Run generate_all.py first.")
        return []
    docs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_verify(es: Elasticsearch):
    """Verify connection and print index status."""
    print("Verifying Elasticsearch connection...")
    info = es.info()
    print(f"  Cluster: {info.get('cluster_name', 'N/A')}")
    print(f"  Version: {info.get('version', {}).get('number', 'N/A')}")
    print()

    print("Index status:")
    for index_name in INDICES:
        if es.indices.exists(index=index_name):
            count = es.count(index=index_name)["count"]
            print(f"  {index_name}: {count} docs")
        else:
            print(f"  {index_name}: NOT FOUND")
    print()


def cmd_reset(es: Elasticsearch):
    """Delete all project indices."""
    print("Deleting existing indices...")
    for index_name in INDICES:
        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
            print(f"  Deleted: {index_name}")
        else:
            print(f"  Skipped (not found): {index_name}")
    print()


def cmd_setup(es: Elasticsearch, inference_id: str | None, no_semantic: bool):
    """Create indices and bulk-write data."""
    print("Setting up indices and writing data...")
    print()

    for index_name, (mapping_file, data_file) in INDICES.items():
        print(f"--- {index_name} ---")

        # Create index if needed
        if es.indices.exists(index=index_name):
            print(f"  Index already exists, skipping creation.")
        else:
            mapping = load_mapping(mapping_file, inference_id, no_semantic)
            es.indices.create(index=index_name, mappings=mapping["mappings"])
            print(f"  Index created.")

        # Load and write data
        docs = load_ndjson(data_file)
        if not docs:
            print(f"  No data to write.")
            continue

        # Prepare bulk actions
        actions = [
            {"_index": index_name, "_source": doc}
            for doc in docs
        ]

        success, errors = helpers.bulk(es, actions, raise_on_error=False)
        print(f"  Bulk write: {success} succeeded, {len(errors) if isinstance(errors, list) else 0} errors")

        if errors and isinstance(errors, list):
            for err in errors[:5]:
                print(f"    Error: {err}")

        print()

    # Wait for refresh (Serverless min interval is 5s)
    print("Waiting for index refresh...")
    time.sleep(6)

    # Verify counts
    print("Verification:")
    for index_name in INDICES:
        if es.indices.exists(index=index_name):
            count = es.count(index=index_name)["count"]
            print(f"  {index_name}: {count} docs")
    print()
    print("Setup complete!")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CampaignPilot Elasticsearch setup")
    parser.add_argument("--reset", action="store_true", help="Delete existing indices before setup")
    parser.add_argument("--verify", action="store_true", help="Only verify connection and index status")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Downgrade all semantic_text fields to text")
    args = parser.parse_args()

    es = get_es_client()
    inference_id = os.environ.get("ES_INFERENCE_ID", "").strip() or None

    if args.verify:
        cmd_verify(es)
        return

    if args.reset:
        cmd_reset(es)

    if not inference_id and not args.no_semantic:
        print("NOTE: ES_INFERENCE_ID not set. semantic_text fields will be downgraded to text.")
        print("      Set ES_INFERENCE_ID in .env or use --no-semantic to suppress this message.")
        print()

    cmd_setup(es, inference_id, args.no_semantic)


if __name__ == "__main__":
    main()
