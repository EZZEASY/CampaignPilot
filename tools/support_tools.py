"""
Customer support ticket analysis tools (v2.1).
"""

from tools.es_client import run_esql


def analyze_support_sentiment(days: int = 7) -> list[dict]:
    """Aggregate support ticket volume and sentiment by category."""
    return run_esql(
        f"FROM support-tickets"
        f" | WHERE @timestamp >= NOW() - {days} days"
        f" | STATS total_tickets = COUNT(*),"
        f" avg_sentiment = AVG(sentiment)"
        f" BY category"
        f" | SORT total_tickets DESC"
        f" | LIMIT 20"
    )
