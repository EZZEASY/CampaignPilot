"""
Creative asset and metrics tools (v2.1).
Queries creative-metrics index for fatigue detection and ad-group drill-down.
"""

from tools.es_client import run_esql


def detect_fatigued_creatives(threshold: float = 0.7) -> list[dict]:
    """Find creatives with high fatigue scores from creative-metrics timeseries."""
    return run_esql(
        f"FROM creative-metrics"
        f" | STATS avg_fatigue = AVG(fatigue_score),"
        f" avg_ctr = AVG(ctr), avg_cpa = AVG(cpa),"
        f" total_spend = SUM(spend)"
        f" BY creative_id, campaign_id, ad_group_id, channel"
        f" | WHERE avg_fatigue > {threshold}"
        f" | SORT avg_fatigue DESC"
        f" | LIMIT 20"
    )


def drill_down_ad_group(campaign_id: str, days: int = 7) -> list[dict]:
    """Drill down into ad group performance for a campaign."""
    return run_esql(
        f'FROM creative-metrics'
        f' | WHERE campaign_id == "{campaign_id}"'
        f' AND @timestamp >= NOW() - {days} days'
        f' | STATS avg_ctr = AVG(ctr), avg_cpa = AVG(cpa),'
        f' avg_fatigue = AVG(fatigue_score),'
        f' total_spend = SUM(spend), total_conv = SUM(conversions)'
        f' BY ad_group_id, channel'
        f' | SORT avg_fatigue DESC'
        f' | LIMIT 20'
    )
