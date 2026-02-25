"""
Audience segment tools.
"""

from tools.es_client import run_esql


def detect_churn_risk(
    threshold: float = 0.4,
    date_from: str = "2026-02-15",
) -> list[dict]:
    """Find audience segments with high churn risk."""
    return run_esql(
        f'FROM audience-segments | WHERE date >= "{date_from}"'
        " | STATS avg_churn = AVG(churn_risk), avg_conv = AVG(conversion_rate),"
        " avg_engagement = AVG(engagement_score)"
        " BY campaign_id, segment"
        f" | WHERE avg_churn > {threshold}"
        " | SORT avg_churn DESC | LIMIT 20"
    )
