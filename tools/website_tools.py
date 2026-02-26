"""
Website health and performance tools (v2.1).
"""

from tools.es_client import run_esql


def check_website_health(hours: int = 24) -> list[dict]:
    """Check website health — aggregate landing page performance over recent hours.

    Returns per-page stats with health status:
    - CRITICAL: avg_load > 5000ms or timeouts > 10%
    - SLOW: avg_load > 3000ms
    - HEALTHY: otherwise
    """
    results = run_esql(
        f"FROM website-events"
        f" | WHERE @timestamp >= NOW() - {hours} hours"
        f" | STATS avg_load = AVG(load_time_ms),"
        f" bounce_rate = AVG(CASE(bounce == true, 1, 0)),"
        f" conv_rate = AVG(CASE(converted == true, 1, 0)),"
        f" timeout_rate = AVG(CASE(timeout == true, 1, 0)),"
        f" total_sessions = COUNT(*)"
        f" BY page_url"
        f" | SORT avg_load DESC"
        f" | LIMIT 20"
    )

    for row in results:
        avg_load = row.get("avg_load", 0)
        timeout_rate = row.get("timeout_rate", 0)
        if avg_load > 5000 or timeout_rate > 0.10:
            row["health"] = "CRITICAL"
        elif avg_load > 3000:
            row["health"] = "SLOW"
        else:
            row["health"] = "HEALTHY"

    return results


def get_website_timeseries(page_url: str, hours: int = 72) -> list[dict]:
    """Get performance timeseries for a specific landing page."""
    return run_esql(
        f'FROM website-events'
        f' | WHERE page_url == "{page_url}" AND @timestamp >= NOW() - {hours} hours'
        f' | STATS avg_load = AVG(load_time_ms),'
        f' bounce_rate = AVG(CASE(bounce == true, 1, 0)),'
        f' conv_rate = AVG(CASE(converted == true, 1, 0)),'
        f' total_sessions = COUNT(*)'
        f' BY date'
        f' | SORT date ASC'
        f' | LIMIT 100'
    )
