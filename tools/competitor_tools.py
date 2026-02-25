"""
Competitor intelligence tools.
"""

from tools.es_client import run_esql


def detect_competitor_threats(
    threshold: float = 0.35,
    date_from: str = "2026-02-15",
) -> list[dict]:
    """Find competitors with high impression share."""
    return run_esql(
        f'FROM competitor-signals | WHERE date >= "{date_from}"'
        f" AND impression_share > {threshold}"
        " | SORT impression_share DESC | LIMIT 20"
    )


def get_competitor_summary(date_from: str = "2026-02-01") -> list[dict]:
    """Aggregate competitor activity summary."""
    return run_esql(
        f'FROM competitor-signals | WHERE date >= "{date_from}"'
        " | STATS avg_share = AVG(impression_share),"
        " avg_spend = AVG(estimated_spend), avg_cpc = AVG(avg_cpc),"
        " signal_count = COUNT(*)"
        " BY competitor"
        " | SORT avg_share DESC | LIMIT 20"
    )
