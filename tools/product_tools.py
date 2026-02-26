"""
Product catalog monitoring tools (v2.1).
"""

from tools.es_client import run_esql


def check_product_changes(days: int = 7) -> list[dict]:
    """Find recent product events — price changes, out-of-stock, etc."""
    return run_esql(
        f"FROM product-catalog"
        f' | WHERE event_type IN ("price_change", "out_of_stock")'
        f" AND @timestamp >= NOW() - {days} days"
        f" | SORT @timestamp DESC"
        f" | LIMIT 50"
    )
