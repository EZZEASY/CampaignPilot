"""
Budget tracking tools.
"""

from tools.es_client import run_esql


def get_portfolio_budget_summary(date: str = "2026-02-25") -> list[dict]:
    """Get budget summary across all campaigns for a given date."""
    return run_esql(
        f'FROM budget-ledger | WHERE date == "{date}"'
        " | STATS total_spend = SUM(actual_spend), total_budget = SUM(daily_budget),"
        " avg_pace = AVG(pace_ratio), total_remaining = SUM(remaining_budget)"
        " BY channel"
        " | SORT total_spend DESC | LIMIT 20"
    )


def detect_budget_alerts(threshold: float = 1.2, date: str = "2026-02-25") -> list[dict]:
    """Find campaigns overpacing their budget (pace_ratio > threshold)."""
    return run_esql(
        f'FROM budget-ledger | WHERE date == "{date}" AND pace_ratio > {threshold}'
        " | SORT pace_ratio DESC | LIMIT 20"
    )
