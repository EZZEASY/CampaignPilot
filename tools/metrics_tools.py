"""
Channel metrics tools — summaries, timeseries, and anomaly detection.
"""

from tools.es_client import run_esql


def get_metrics_summary(
    campaign_id: str | None = None,
    channel: str | None = None,
    date_from: str = "2026-02-01",
) -> list[dict]:
    """Aggregate metrics summary grouped by campaign_id and channel."""
    query = "FROM channel-metrics"
    filters = [f'date >= "{date_from}"']
    if campaign_id:
        filters.append(f'campaign_id == "{campaign_id}"')
    if channel:
        filters.append(f'channel == "{channel}"')
    query += " | WHERE " + " AND ".join(filters)
    query += (
        " | STATS avg_cpa = AVG(cpa), avg_ctr = AVG(ctr), avg_roas = AVG(roas),"
        " total_spend = SUM(spend), total_conversions = SUM(conversions),"
        " total_impressions = SUM(impressions), total_clicks = SUM(clicks)"
        " BY campaign_id, channel"
    )
    query += " | SORT total_spend DESC | LIMIT 100"
    return run_esql(query)


def get_metrics_timeseries(
    campaign_id: str,
    date_from: str = "2026-02-01",
) -> list[dict]:
    """Get daily metrics timeseries for a campaign."""
    return run_esql(
        f'FROM channel-metrics | WHERE campaign_id == "{campaign_id}"'
        f' AND date >= "{date_from}"'
        f" | SORT date ASC | LIMIT 100"
    )


def detect_metric_anomalies(
    metric: str = "cpa",
    threshold_pct: float = 50,
    date_from: str = "2026-02-01",
) -> list[dict]:
    """
    Detect campaigns where a metric deviates significantly from its average.

    For 'cpa': flags campaigns where latest CPA exceeds average by threshold_pct%.
    For 'ctr': flags campaigns where latest CTR is below average by |threshold_pct|%.
    """
    # Get per-campaign averages and latest values
    query = (
        f'FROM channel-metrics | WHERE date >= "{date_from}"'
        f" | STATS avg_val = AVG({metric}), max_date = MAX(date),"
        f" count = COUNT(*) BY campaign_id, channel"
        f" | SORT avg_val DESC | LIMIT 200"
    )
    summaries = run_esql(query)

    alerts = []
    for row in summaries:
        cid = row["campaign_id"]
        ch = row["channel"]
        avg_val = row.get("avg_val")
        if avg_val is None or avg_val == 0:
            continue

        # Get latest value
        latest = run_esql(
            f'FROM channel-metrics | WHERE campaign_id == "{cid}" AND channel == "{ch}"'
            f" | SORT date DESC | LIMIT 1"
        )
        if not latest:
            continue

        latest_val = latest[0].get(metric)
        if latest_val is None:
            continue

        pct_change = ((latest_val - avg_val) / abs(avg_val)) * 100

        # For CPA: spike is bad (positive threshold)
        # For CTR/ROAS: drop is bad (negative threshold)
        if threshold_pct > 0 and pct_change > threshold_pct:
            alerts.append({
                "campaign_id": cid,
                "channel": ch,
                "metric": metric,
                "avg_value": round(avg_val, 4),
                "latest_value": round(latest_val, 4),
                "pct_change": round(pct_change, 1),
                "latest_date": latest[0].get("date"),
                "severity": "high" if pct_change > threshold_pct * 1.5 else "medium",
            })
        elif threshold_pct < 0 and pct_change < threshold_pct:
            alerts.append({
                "campaign_id": cid,
                "channel": ch,
                "metric": metric,
                "avg_value": round(avg_val, 4),
                "latest_value": round(latest_val, 4),
                "pct_change": round(pct_change, 1),
                "latest_date": latest[0].get("date"),
                "severity": "high" if pct_change < threshold_pct * 1.5 else "medium",
            })

    alerts.sort(key=lambda a: abs(a["pct_change"]), reverse=True)
    return alerts
