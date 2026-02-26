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
from tools.website_tools import check_website_health
from tools.product_tools import check_product_changes
from tools.support_tools import analyze_support_sentiment

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

    # 7. Website degradation
    try:
        for row in check_website_health(24):
            if row.get("health") in ("CRITICAL", "SLOW"):
                alerts.append({
                    "campaign_id": "",
                    "channel": "",
                    "alert_type": "website_degradation",
                    "severity": "high" if row["health"] == "CRITICAL" else "medium",
                    "page_url": row.get("page_url", ""),
                    "avg_load_ms": round(row.get("avg_load", 0), 0),
                    "bounce_rate": round(row.get("bounce_rate", 0), 2),
                    "timeout_rate": round(row.get("timeout_rate", 0), 2),
                })
    except Exception:
        pass  # website-events index may not exist yet

    # 8. Product price changes
    try:
        for row in check_product_changes(7):
            if row.get("event_type") == "price_change" and abs(row.get("change_pct", 0)) > 10:
                alerts.append({
                    "campaign_id": "",
                    "channel": "",
                    "alert_type": "product_price_change",
                    "severity": "high" if abs(row.get("change_pct", 0)) > 20 else "medium",
                    "product_id": row.get("product_id", ""),
                    "product_name": row.get("product_name", ""),
                    "change_pct": round(row.get("change_pct", 0), 1),
                    "old_price": row.get("old_price"),
                    "new_price": row.get("new_price"),
                })
    except Exception:
        pass

    # 9. Support ticket surge
    try:
        for row in analyze_support_sentiment(7):
            total = row.get("total_tickets", 0)
            sentiment = row.get("avg_sentiment", 0)
            if total > 25 or sentiment < -0.6:
                alerts.append({
                    "campaign_id": "",
                    "channel": "",
                    "alert_type": "support_surge",
                    "severity": "high" if sentiment < -0.6 else "medium",
                    "category": row.get("category", ""),
                    "total_tickets": total,
                    "avg_sentiment": round(sentiment, 2),
                })
    except Exception:
        pass

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
