"""
Creative asset tools.
"""

from tools.es_client import run_esql


def detect_fatigued_creatives(threshold: float = 0.7) -> list[dict]:
    """Find creative assets with high fatigue scores."""
    return run_esql(
        f"FROM creative-assets | WHERE fatigue_score > {threshold}"
        " | SORT fatigue_score DESC | LIMIT 20"
    )
