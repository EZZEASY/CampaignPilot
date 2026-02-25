"""
Single-campaign deep health analysis.

Gathers metadata, timeseries, budget, creatives, audience, and action history
to produce a comprehensive health report with a computed health score.
"""

from tools.campaign_tools import get_campaign
from tools.metrics_tools import get_metrics_summary, get_metrics_timeseries
from tools.budget_tools import detect_budget_alerts
from tools.creative_tools import detect_fatigued_creatives
from tools.audience_tools import detect_churn_risk
from tools.action_tools import get_actions
from tools.es_client import run_esql


def analyze_campaign_health(campaign_id: str) -> dict:
    """
    Produce a deep health report for a single campaign.

    Returns:
        {
            "campaign": {...},
            "metrics_summary": {...},
            "timeseries": [...],
            "budget_status": {...},
            "fatigued_creatives": [...],
            "churn_segments": [...],
            "recent_actions": [...],
            "health_score": float,  # 0-100
            "issues": [...],
        }
    """
    # 1. Campaign metadata
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"error": f"Campaign {campaign_id} not found"}

    # 2. Metrics summary
    summaries = get_metrics_summary(campaign_id=campaign_id)
    metrics_summary = summaries[0] if summaries else {}

    # 3. Timeseries
    timeseries = get_metrics_timeseries(campaign_id)

    # 4. Budget status
    budget_rows = run_esql(
        f'FROM budget-ledger | WHERE campaign_id == "{campaign_id}"'
        " | SORT date DESC | LIMIT 1"
    )
    budget_status = budget_rows[0] if budget_rows else {}

    # 5. Fatigued creatives for this campaign
    all_fatigued = detect_fatigued_creatives(0.6)
    fatigued = [c for c in all_fatigued if c.get("campaign_id") == campaign_id]

    # 6. Churn risk segments for this campaign
    all_churn = detect_churn_risk(0.3)
    churn_segments = [s for s in all_churn if s.get("campaign_id") == campaign_id]

    # 7. Recent actions
    recent_actions = get_actions(campaign_id=campaign_id, limit=10)

    # 8. Compute health score (0-100)
    score = 100.0
    issues = []

    # Budget pacing penalty
    pace = budget_status.get("pace_ratio", 1.0)
    if pace and pace > 1.2:
        penalty = min(25, (pace - 1.0) * 50)
        score -= penalty
        issues.append(f"Budget overpacing at {pace:.2f}x")

    # CPA trend penalty
    if len(timeseries) >= 5:
        recent_cpa = [r.get("cpa", 0) for r in timeseries[-5:] if r.get("cpa")]
        early_cpa = [r.get("cpa", 0) for r in timeseries[:5] if r.get("cpa")]
        if recent_cpa and early_cpa:
            avg_recent = sum(recent_cpa) / len(recent_cpa)
            avg_early = sum(early_cpa) / len(early_cpa)
            if avg_early > 0:
                cpa_change = (avg_recent - avg_early) / avg_early
                if cpa_change > 0.3:
                    penalty = min(20, cpa_change * 30)
                    score -= penalty
                    issues.append(f"CPA trending up {cpa_change:.0%}")

    # Creative fatigue penalty
    if fatigued:
        penalty = min(15, len(fatigued) * 5)
        score -= penalty
        issues.append(f"{len(fatigued)} fatigued creative(s)")

    # Audience churn penalty
    if churn_segments:
        max_churn = max(s.get("avg_churn", 0) for s in churn_segments)
        penalty = min(15, max_churn * 20)
        score -= penalty
        issues.append(f"{len(churn_segments)} segment(s) with high churn risk")

    score = max(0, min(100, score))

    return {
        "campaign": campaign,
        "metrics_summary": metrics_summary,
        "timeseries": timeseries,
        "budget_status": budget_status,
        "fatigued_creatives": fatigued,
        "churn_segments": churn_segments,
        "recent_actions": recent_actions,
        "health_score": round(score, 1),
        "issues": issues,
    }


if __name__ == "__main__":
    import json
    import sys

    cid = sys.argv[1] if len(sys.argv) > 1 else "CAMP-2026-041"
    result = analyze_campaign_health(cid)
    print(json.dumps(result, indent=2, default=str))
