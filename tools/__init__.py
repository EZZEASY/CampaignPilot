"""
CampaignPilot tools — Python layer for ES|QL queries.
"""

from tools.es_client import get_client, run_esql
from tools.campaign_tools import get_campaign, list_campaigns, get_campaigns_by_ids
from tools.metrics_tools import (
    get_metrics_summary,
    get_metrics_timeseries,
    detect_metric_anomalies,
)
from tools.budget_tools import get_portfolio_budget_summary, detect_budget_alerts
from tools.creative_tools import detect_fatigued_creatives
from tools.audience_tools import detect_churn_risk
from tools.competitor_tools import detect_competitor_threats, get_competitor_summary
from tools.action_tools import get_actions, log_action

__all__ = [
    "get_client",
    "run_esql",
    "get_campaign",
    "list_campaigns",
    "get_campaigns_by_ids",
    "get_metrics_summary",
    "get_metrics_timeseries",
    "detect_metric_anomalies",
    "get_portfolio_budget_summary",
    "detect_budget_alerts",
    "detect_fatigued_creatives",
    "detect_churn_risk",
    "detect_competitor_threats",
    "get_competitor_summary",
    "get_actions",
    "log_action",
]
