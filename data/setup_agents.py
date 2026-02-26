#!/usr/bin/env python3
"""
Agent Builder setup script for CampaignPilot.
Creates ES|QL tools, index search tools, and the CampaignPilot agent via Kibana API.

Usage:
    python data/setup_agents.py              # Create tools + agent
    python data/setup_agents.py --reset      # Delete existing, then recreate
    python data/setup_agents.py --verify     # Check Kibana connection + list tools/agents
    python data/setup_agents.py --chat "Are there any anomalies?"  # Quick test
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
import requests

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Append project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.prompts import SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KIBANA_URL = os.environ.get("KIBANA_URL", "").rstrip("/")
KIBANA_API_KEY = os.environ.get("KIBANA_API_KEY", "")

HEADERS = {
    "Authorization": f"ApiKey {KIBANA_API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

ESQL_TOOLS = [
    {
        "id": "cp-campaign-metrics",
        "description": "Campaign Metrics Summary — Get aggregated performance metrics (CPA, CTR, ROAS, spend, conversions) for campaigns. Filter by campaign_id and date range.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM channel-metrics | WHERE campaign_id == ?campaign_id AND date >= ?date_from'
                ' | STATS avg_cpa=AVG(cpa), avg_ctr=AVG(ctr), avg_roas=AVG(roas),'
                ' total_spend=SUM(spend), total_conversions=SUM(conversions)'
                ' BY campaign_id, channel'
            ),
            "params": {
                "campaign_id": {"type": "string", "description": "Campaign ID (e.g. CAMP-2026-041)"},
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd), defaults to 2026-02-01"},
            },
        },
    },
    {
        "id": "cp-metrics-timeseries",
        "description": "Metrics Timeseries — Get daily performance metrics over time for a campaign. Returns date, impressions, clicks, conversions, spend, cpa, ctr, roas.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM channel-metrics | WHERE campaign_id == ?campaign_id'
                ' | SORT date ASC | LIMIT 100'
            ),
            "params": {
                "campaign_id": {"type": "string", "description": "Campaign ID"},
            },
        },
    },
    {
        "id": "cp-top-campaigns",
        "description": "Top Campaigns by Metric — Rank campaigns by a metric (cpa, ctr, roas, spend, conversions). Returns top N campaigns sorted by the chosen metric.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM channel-metrics | WHERE date >= ?date_from'
                ' | STATS avg_val=AVG(?metric) BY campaign_id, channel'
                ' | SORT avg_val DESC | LIMIT ?limit'
            ),
            "params": {
                "metric": {"type": "string", "description": "Metric name: cpa, ctr, roas, spend, conversions"},
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd)"},
                "limit": {"type": "integer", "description": "Number of results (default 10)"},
            },
        },
    },
    {
        "id": "cp-budget-alerts",
        "description": "Budget Overpace Alerts — Find campaigns overpacing their budget. Returns campaigns where pace_ratio exceeds the threshold (1.0 = on pace, >1.2 = overpacing).",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM budget-ledger | WHERE date == "2026-02-25" AND pace_ratio > ?threshold'
                ' | SORT pace_ratio DESC | LIMIT 20'
            ),
            "params": {
                "threshold": {"type": "float", "description": "Pace ratio threshold (default 1.2)"},
            },
        },
    },
    {
        "id": "cp-fatigued-creatives",
        "description": "Fatigued Creatives — Find creatives with high fatigue scores from daily metrics. High fatigue indicates declining CTR and need for creative refresh.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM creative-metrics'
                ' | STATS avg_fatigue=AVG(fatigue_score), avg_ctr=AVG(ctr),'
                ' avg_cpa=AVG(cpa), total_spend=SUM(spend)'
                ' BY creative_id, campaign_id, ad_group_id, channel'
                ' | WHERE avg_fatigue > ?threshold'
                ' | SORT avg_fatigue DESC | LIMIT 20'
            ),
            "params": {
                "threshold": {"type": "float", "description": "Fatigue score threshold (0-1, default 0.7)"},
            },
        },
    },
    {
        "id": "cp-churn-risk",
        "description": "Audience Churn Risk — Find audience segments with rising churn risk. Returns segments where average churn risk exceeds threshold.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM audience-segments | WHERE date >= ?date_from'
                ' | STATS avg_churn=AVG(churn_risk), avg_conv=AVG(conversion_rate)'
                ' BY campaign_id, segment'
                ' | WHERE avg_churn > ?threshold'
                ' | SORT avg_churn DESC | LIMIT 20'
            ),
            "params": {
                "threshold": {"type": "float", "description": "Churn risk threshold (0-1, default 0.4)"},
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd)"},
            },
        },
    },
    {
        "id": "cp-competitor-threats",
        "description": "Competitor Threats — Find competitors with high impression share indicating competitive pressure. Higher impression share means more aggressive competition.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM competitor-signals | WHERE impression_share > ?threshold'
                ' | SORT impression_share DESC | LIMIT 20'
            ),
            "params": {
                "threshold": {"type": "float", "description": "Impression share threshold (0-1, default 0.35)"},
            },
        },
    },
    {
        "id": "cp-action-log",
        "description": "Action Log — View history of agent-proposed and executed actions. Shows action type, status, and outcome.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM action-log | SORT timestamp DESC | LIMIT ?limit'
            ),
            "params": {
                "limit": {"type": "integer", "description": "Number of actions to return (default 20)"},
            },
        },
    },
    {
        "id": "cp-website-health",
        "description": "Website Health — Check landing page performance (load times, CDN status, session count). Pages with avg_load > 5000ms are CRITICAL.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM website-events | WHERE date >= ?date_from'
                ' | STATS avg_load=AVG(load_time_ms),'
                ' total_sessions=COUNT(*)'
                ' BY page_url, cdn_status'
                ' | SORT avg_load DESC | LIMIT 20'
            ),
            "params": {
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd), e.g. 2026-02-18"},
            },
        },
    },
    {
        "id": "cp-product-changes",
        "description": "Product Changes — Find recent product catalog events (price changes, out-of-stock). Useful for root cause analysis of conversion drops.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM product-catalog'
                ' | WHERE event_type IN ("price_change", "out_of_stock")'
                ' AND date >= ?date_from'
                ' | SORT date DESC | LIMIT 50'
            ),
            "params": {
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd), e.g. 2026-02-10"},
            },
        },
    },
    {
        "id": "cp-support-sentiment",
        "description": "Support Sentiment — Aggregate customer support ticket volume and sentiment by category. Detects complaint surges.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM support-tickets | WHERE date >= ?date_from'
                ' | STATS total_tickets=COUNT(*), avg_sentiment=AVG(sentiment)'
                ' BY category'
                ' | SORT total_tickets DESC | LIMIT 20'
            ),
            "params": {
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd), e.g. 2026-02-18"},
            },
        },
    },
    {
        "id": "cp-creative-fatigue",
        "description": "Creative Fatigue — Find creatives with high fatigue scores from creative-metrics timeseries. Returns avg fatigue, CTR, CPA by creative.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM creative-metrics'
                ' | STATS avg_fatigue=AVG(fatigue_score), avg_ctr=AVG(ctr),'
                ' avg_cpa=AVG(cpa), total_spend=SUM(spend)'
                ' BY creative_id, campaign_id, ad_group_id, channel'
                ' | WHERE avg_fatigue > ?threshold'
                ' | SORT avg_fatigue DESC | LIMIT 20'
            ),
            "params": {
                "threshold": {"type": "float", "description": "Fatigue score threshold (0-1, default 0.7)"},
            },
        },
    },
    {
        "id": "cp-drill-down-ad-group",
        "description": "Ad Group Drill-Down — Breakdown of ad group performance for a campaign. Shows CTR, CPA, fatigue, spend per ad group.",
        "type": "esql",
        "configuration": {
            "query": (
                'FROM creative-metrics | WHERE campaign_id == ?campaign_id'
                ' AND date >= ?date_from'
                ' | STATS avg_ctr=AVG(ctr), avg_cpa=AVG(cpa),'
                ' avg_fatigue=AVG(fatigue_score),'
                ' total_spend=SUM(spend), total_conv=SUM(conversions)'
                ' BY ad_group_id, channel'
                ' | SORT avg_fatigue DESC | LIMIT 20'
            ),
            "params": {
                "campaign_id": {"type": "string", "description": "Campaign ID"},
                "date_from": {"type": "date", "description": "Start date (yyyy-MM-dd), e.g. 2026-02-18"},
            },
        },
    },
]

INDEX_SEARCH_TOOLS = [
    {
        "id": "cp-search-campaigns",
        "description": "Search Campaigns — Search campaign descriptions and names using natural language. Useful for finding campaigns by theme, objective, or description.",
        "type": "index_search",
        "configuration": {
            "pattern": "campaigns",
        },
    },
    {
        "id": "cp-search-creatives",
        "description": "Search Creatives — Search creative asset descriptions and headlines using natural language.",
        "type": "index_search",
        "configuration": {
            "pattern": "creative-assets",
        },
    },
    {
        "id": "cp-search-competitors",
        "description": "Search Competitor Signals — Search competitor signal descriptions using natural language. Find specific competitive activities or market events.",
        "type": "index_search",
        "configuration": {
            "pattern": "competitor-signals",
        },
    },
    {
        "id": "cp-search-support",
        "description": "Search Support Tickets — Search customer support ticket subjects and summaries using natural language. Find specific complaints or issues.",
        "type": "index_search",
        "configuration": {
            "pattern": "support-tickets",
        },
    },
]

ALL_TOOLS = ESQL_TOOLS + INDEX_SEARCH_TOOLS

AGENT_DEF = {
    "id": "campaign-pilot",
    "name": "CampaignPilot",
    "description": "Marketing intelligence agent that monitors campaign performance, detects anomalies, and recommends optimization actions across 50 campaigns on 5 channels.",
}

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def kibana_request(method: str, path: str, body: dict | None = None) -> dict | None:
    """Make a Kibana API request."""
    url = f"{KIBANA_URL}{path}"
    timeout = 120 if "converse" in path else 30
    resp = requests.request(method, url, headers=HEADERS, json=body, timeout=timeout)
    if resp.status_code >= 400:
        print(f"  API Error {resp.status_code}: {resp.text[:500]}")
        return None
    if resp.status_code == 204:
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


def check_kibana_connection() -> bool:
    """Verify Kibana is reachable."""
    if not KIBANA_URL or not KIBANA_API_KEY:
        print("ERROR: KIBANA_URL and KIBANA_API_KEY must be set in .env")
        return False
    try:
        resp = requests.get(
            f"{KIBANA_URL}/api/status",
            headers={"Authorization": f"ApiKey {KIBANA_API_KEY}"},
            timeout=10,
        )
        if resp.status_code == 200:
            status = resp.json().get("status", {}).get("overall", {}).get("level", "unknown")
            print(f"Kibana connection OK (status: {status})")
            return True
        print(f"Kibana returned status {resp.status_code}")
        return False
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to {KIBANA_URL}")
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create_tools():
    """Create all tools via Agent Builder API."""
    print("Creating Agent Builder tools...")
    print()

    for tool_def in ALL_TOOLS:
        tool_id = tool_def["id"]
        print(f"  Creating tool: {tool_id} ({tool_def['type']})...")
        result = kibana_request("POST", "/api/agent_builder/tools", tool_def)
        if result is not None:
            print(f"    OK")
        else:
            print(f"    FAILED (may already exist, try --reset)")
    print()


def cmd_create_agent():
    """Create the CampaignPilot agent."""
    print("Creating CampaignPilot agent...")

    tool_ids = [t["id"] for t in ALL_TOOLS] + ["platform.core.search"]

    agent_body = {
        **AGENT_DEF,
        "configuration": {
            "instructions": SYSTEM_PROMPT,
            "tools": [{"tool_ids": tool_ids}],
        },
    }

    result = kibana_request("POST", "/api/agent_builder/agents", agent_body)
    if result is not None:
        agent_id = result.get("id", "unknown")
        print(f"  Agent created: {agent_id}")
    else:
        print("  FAILED (may already exist, try --reset)")
    print()
    return result


def cmd_reset():
    """Delete existing tools and agent, then recreate."""
    print("Resetting Agent Builder resources...")
    print()

    # List and delete agents
    resp = kibana_request("GET", "/api/agent_builder/agents")
    agents = resp.get("results", []) if isinstance(resp, dict) else resp or []
    if agents:
        for agent in agents:
            name = agent.get("name", "")
            if name == "CampaignPilot":
                aid = agent.get("id", "")
                print(f"  Deleting agent: {aid}")
                kibana_request("DELETE", f"/api/agent_builder/agents/{aid}")

    # Delete tools
    for tool_def in ALL_TOOLS:
        tool_id = tool_def["id"]
        print(f"  Deleting tool: {tool_id}")
        kibana_request("DELETE", f"/api/agent_builder/tools/{tool_id}")

    print()


def cmd_verify():
    """Check Kibana connection and list existing tools/agents."""
    if not check_kibana_connection():
        return

    print()
    print("Agent Builder tools:")
    resp = kibana_request("GET", "/api/agent_builder/tools")
    tools = resp.get("results", []) if isinstance(resp, dict) else resp or []
    if tools:
        cp_tools = [t for t in tools if t.get("id", "").startswith("cp-")]
        if cp_tools:
            for t in cp_tools:
                print(f"  {t['id']}: {t.get('description', 'N/A')[:50]} ({t.get('type', 'N/A')})")
        else:
            print("  No CampaignPilot tools found.")
    else:
        print("  Could not list tools.")

    print()
    print("Agent Builder agents:")
    resp = kibana_request("GET", "/api/agent_builder/agents")
    agents = resp.get("results", []) if isinstance(resp, dict) else resp or []
    if agents:
        cp_agents = [a for a in agents if "Campaign" in a.get("name", "")]
        if cp_agents:
            for a in cp_agents:
                print(f"  {a.get('id', 'N/A')}: {a.get('name', 'N/A')}")
        else:
            print("  No CampaignPilot agents found.")
    else:
        print("  Could not list agents.")
    print()


def cmd_chat(message: str):
    """Quick test: send a message to the agent via converse API."""
    if not check_kibana_connection():
        return

    # Find the agent ID
    resp = kibana_request("GET", "/api/agent_builder/agents")
    agents = resp.get("results", []) if isinstance(resp, dict) else resp or []
    agent_id = None
    if agents:
        for a in agents:
            if a.get("name") == "CampaignPilot":
                agent_id = a.get("id")
                break

    if not agent_id:
        print("ERROR: CampaignPilot agent not found. Run setup first.")
        return

    print(f"Agent: {agent_id}")
    print(f"User: {message}")
    print()

    result = kibana_request("POST", "/api/agent_builder/converse", {
        "input": message,
        "agent_id": agent_id,
    })

    if result:
        response = result.get("response", result.get("message", str(result)))
        print(f"CampaignPilot: {response}")
    else:
        print("ERROR: No response from agent.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CampaignPilot Agent Builder setup")
    parser.add_argument("--reset", action="store_true", help="Delete existing resources and recreate")
    parser.add_argument("--verify", action="store_true", help="Check Kibana connection and list resources")
    parser.add_argument("--chat", type=str, help="Quick test: send a message to the agent")
    args = parser.parse_args()

    if args.verify:
        cmd_verify()
        return

    if args.chat:
        cmd_chat(args.chat)
        return

    if not check_kibana_connection():
        print("Cannot proceed without Kibana connection.")
        print("Set KIBANA_URL and KIBANA_API_KEY in .env")
        sys.exit(1)

    if args.reset:
        cmd_reset()

    cmd_create_tools()
    cmd_create_agent()
    print("Agent Builder setup complete!")
    print("Test with: python data/setup_agents.py --chat \"Are there any anomalies?\"")


if __name__ == "__main__":
    main()
