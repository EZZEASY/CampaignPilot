"""
Tool definitions and dispatch for the Python fallback agent.
Maps OpenAI function-calling tool specs to CampaignPilot Python tools.
"""

import json

from tools.campaign_tools import get_campaign, list_campaigns
from tools.metrics_tools import get_metrics_summary, get_metrics_timeseries, detect_metric_anomalies
from tools.budget_tools import get_portfolio_budget_summary, detect_budget_alerts
from tools.creative_tools import detect_fatigued_creatives, drill_down_ad_group
from tools.audience_tools import detect_churn_risk
from tools.website_tools import check_website_health
from tools.product_tools import check_product_changes
from tools.support_tools import analyze_support_sentiment
from tools.competitor_tools import detect_competitor_threats, get_competitor_summary
from tools.action_tools import get_actions, log_action
from workflows.anomaly_scan import run_anomaly_scan
from workflows.campaign_health import analyze_campaign_health

# OpenAI function-calling tool definitions
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_campaign_metrics",
            "description": "Get aggregated performance metrics for a campaign or across all campaigns. Returns CPA, CTR, ROAS, spend, conversions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID (e.g. CAMP-2026-041). Omit for all campaigns."},
                    "channel": {"type": "string", "description": "Channel filter (google_ads, meta_ads, tiktok_ads, email, linkedin_ads)"},
                    "date_from": {"type": "string", "description": "Start date (yyyy-MM-dd), defaults to 2026-02-01"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_timeseries",
            "description": "Get daily performance metrics over time for a specific campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID"},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": "Run a full anomaly scan across all indices — CPA spikes, CTR drops, budget overpace, creative fatigue, audience churn, competitor threats.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_campaign",
            "description": "Deep health analysis for a single campaign — metrics, budget, creatives, audience, actions, and health score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID"},
                },
                "required": ["campaign_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_status",
            "description": "Get budget pacing status. Returns overpacing campaigns or portfolio summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "description": "Pace ratio threshold (default 1.2)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_creative_performance",
            "description": "Find fatigued creative assets that need refresh.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "description": "Fatigue score threshold 0-1 (default 0.7)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audience_segments",
            "description": "Find audience segments with high churn risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "description": "Churn risk threshold 0-1 (default 0.4)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_competitor_intel",
            "description": "Get competitor activity summary or find high impression-share threats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "description": "Impression share threshold 0-1 (default 0.35)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_action",
            "description": "Log a proposed optimization action to the action log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID"},
                    "channel": {"type": "string", "description": "Channel"},
                    "action_type": {"type": "string", "description": "Action type: budget_reallocation, creative_swap, audience_exclusion, bid_adjustment, pause_campaign, resume_campaign"},
                    "description": {"type": "string", "description": "Description of the proposed action"},
                },
                "required": ["campaign_id", "channel", "action_type", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_action_log",
            "description": "View history of agent-proposed and executed actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Filter by campaign ID"},
                    "limit": {"type": "integer", "description": "Number of actions to return (default 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_website_health",
            "description": "Check website landing page health — load times, bounce rates, CDN status, timeouts. Returns CRITICAL/SLOW/HEALTHY status per page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Lookback window in hours (default 24)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_product_changes",
            "description": "Find recent product catalog events — price changes, out-of-stock events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback window in days (default 7)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_support_sentiment",
            "description": "Aggregate customer support ticket volume and sentiment by category. Detects complaint surges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback window in days (default 7)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drill_down_ad_group",
            "description": "Drill down into ad group performance for a campaign — CTR, CPA, fatigue, spend by ad group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID"},
                    "days": {"type": "integer", "description": "Lookback window in days (default 7)"},
                },
                "required": ["campaign_id"],
            },
        },
    },
]


def dispatch_tool(name: str, arguments: dict) -> str:
    """Execute a tool call and return JSON result string."""
    try:
        if name == "query_campaign_metrics":
            result = get_metrics_summary(
                campaign_id=arguments.get("campaign_id"),
                channel=arguments.get("channel"),
                date_from=arguments.get("date_from", "2026-02-01"),
            )
        elif name == "get_campaign_timeseries":
            result = get_metrics_timeseries(arguments["campaign_id"])
        elif name == "detect_anomalies":
            result = run_anomaly_scan()
        elif name == "analyze_campaign":
            result = analyze_campaign_health(arguments["campaign_id"])
        elif name == "get_budget_status":
            threshold = arguments.get("threshold", 1.2)
            alerts = detect_budget_alerts(threshold)
            summary = get_portfolio_budget_summary()
            result = {"alerts": alerts, "portfolio_summary": summary}
        elif name == "get_creative_performance":
            result = detect_fatigued_creatives(arguments.get("threshold", 0.7))
        elif name == "get_audience_segments":
            result = detect_churn_risk(arguments.get("threshold", 0.4))
        elif name == "get_competitor_intel":
            threshold = arguments.get("threshold", 0.35)
            threats = detect_competitor_threats(threshold)
            summary = get_competitor_summary()
            result = {"threats": threats, "summary": summary}
        elif name == "log_action":
            result = log_action(
                campaign_id=arguments["campaign_id"],
                channel=arguments["channel"],
                action_type=arguments["action_type"],
                description=arguments["description"],
                parameters=arguments.get("parameters"),
            )
        elif name == "get_action_log":
            result = get_actions(
                campaign_id=arguments.get("campaign_id"),
                limit=arguments.get("limit", 20),
            )
        elif name == "check_website_health":
            result = check_website_health(arguments.get("hours", 24))
        elif name == "check_product_changes":
            result = check_product_changes(arguments.get("days", 7))
        elif name == "analyze_support_sentiment":
            result = analyze_support_sentiment(arguments.get("days", 7))
        elif name == "drill_down_ad_group":
            result = drill_down_ad_group(
                campaign_id=arguments["campaign_id"],
                days=arguments.get("days", 7),
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result, default=str)
