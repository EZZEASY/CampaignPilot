"""
Full-spectrum anomaly scan across all indices.

Combines detection from metrics, budget, creative, audience, and competitor tools
into a unified alert list sorted by severity.
"""

from tools.metrics_tools import detect_metric_anomalies
from tools.budget_tools import detect_budget_alerts
from tools.creative_tools import detect_fatigued_creatives
from tools.audience_tools import detect_churn_risk
from tools.competitor_tools import detect_competitor_threats
from tools.campaign_tools import get_campaigns_by_ids

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def run_anomaly_scan() -> dict:
    """
    Run all anomaly detectors and return a unified alert report.

    Returns:
        {
            "total_alerts": int,
            "alerts": [...],
            "alerts_by_severity": {"high": [...], "medium": [...], "low": [...]},
        }
    """
    alerts: list[dict] = []

    # 1. CPA spikes
    for a in detect_metric_anomalies("cpa", 50):
        a["alert_type"] = "cpa_spike"
        alerts.append(a)

    # 2. CTR drops
    for a in detect_metric_anomalies("ctr", -30):
        a["alert_type"] = "ctr_drop"
        alerts.append(a)

    # 3. Budget overpacing
    for row in detect_budget_alerts(1.2):
        alerts.append({
            "campaign_id": row["campaign_id"],
            "channel": row.get("channel", ""),
            "alert_type": "budget_overpace",
            "severity": "high" if row["pace_ratio"] > 1.3 else "medium",
            "pace_ratio": round(row["pace_ratio"], 2),
            "projected_overspend": round(row.get("projected_overspend", 0), 2),
            "latest_date": row.get("date"),
        })

    # 4. Creative fatigue
    for row in detect_fatigued_creatives(0.7):
        alerts.append({
            "campaign_id": row["campaign_id"],
            "channel": row.get("channel", ""),
            "alert_type": "creative_fatigue",
            "severity": "high" if row["fatigue_score"] > 0.85 else "medium",
            "asset_id": row.get("asset_id", ""),
            "fatigue_score": round(row["fatigue_score"], 2),
            "headline": row.get("headline", ""),
        })

    # 5. Audience churn
    for row in detect_churn_risk(0.4):
        alerts.append({
            "campaign_id": row["campaign_id"],
            "channel": "",
            "alert_type": "audience_churn",
            "severity": "high" if row["avg_churn"] > 0.6 else "medium",
            "segment": row.get("segment", ""),
            "avg_churn": round(row["avg_churn"], 2),
            "avg_conv": round(row.get("avg_conv", 0), 4),
        })

    # 6. Competitor threats
    for row in detect_competitor_threats(0.35):
        alerts.append({
            "campaign_id": "",
            "channel": row.get("channel", ""),
            "alert_type": "competitor_threat",
            "severity": "high" if row["impression_share"] > 0.45 else "medium",
            "competitor": row.get("competitor", ""),
            "impression_share": round(row["impression_share"], 2),
            "estimated_spend": round(row.get("estimated_spend", 0), 2),
        })

    # Enrich with campaign names
    campaign_ids = list({a["campaign_id"] for a in alerts if a.get("campaign_id")})
    if campaign_ids:
        campaigns = get_campaigns_by_ids(campaign_ids)
        name_map = {c["campaign_id"]: c.get("campaign_name", "") for c in campaigns}
        for a in alerts:
            a["campaign_name"] = name_map.get(a.get("campaign_id", ""), "")

    # Sort by severity then alert_type
    alerts.sort(key=lambda a: (SEVERITY_ORDER.get(a.get("severity", "low"), 2), a.get("alert_type", "")))

    # Group by severity
    by_severity: dict[str, list] = {"high": [], "medium": [], "low": []}
    for a in alerts:
        sev = a.get("severity", "low")
        by_severity.setdefault(sev, []).append(a)

    return {
        "total_alerts": len(alerts),
        "alerts": alerts,
        "alerts_by_severity": by_severity,
    }


if __name__ == "__main__":
    import json
    result = run_anomaly_scan()
    print(json.dumps(result, indent=2, default=str))
