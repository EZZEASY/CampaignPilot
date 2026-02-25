"""
Domain constants for CampaignPilot synthetic data generation.
"""

import random
from datetime import date

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Time range
# ---------------------------------------------------------------------------
DATE_START = date(2026, 2, 1)
DATE_END = date(2026, 2, 25)

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
CHANNELS = ["google_ads", "meta_ads", "tiktok_ads", "email", "linkedin_ads"]

CHANNEL_DEFAULTS = {
    "google_ads": {
        "base_cpa": 12.0, "base_ctr": 0.035, "base_roas": 4.2,
        "base_impressions": 15000, "base_clicks": 525,
        "base_conversions": 44, "base_spend": 528.0,
    },
    "meta_ads": {
        "base_cpa": 9.5, "base_ctr": 0.028, "base_roas": 5.0,
        "base_impressions": 20000, "base_clicks": 560,
        "base_conversions": 59, "base_spend": 560.0,
    },
    "tiktok_ads": {
        "base_cpa": 7.0, "base_ctr": 0.045, "base_roas": 3.5,
        "base_impressions": 25000, "base_clicks": 1125,
        "base_conversions": 80, "base_spend": 560.0,
    },
    "email": {
        "base_cpa": 2.5, "base_ctr": 0.22, "base_roas": 12.0,
        "base_impressions": 50000, "base_clicks": 11000,
        "base_conversions": 220, "base_spend": 550.0,
    },
    "linkedin_ads": {
        "base_cpa": 35.0, "base_ctr": 0.012, "base_roas": 2.8,
        "base_impressions": 8000, "base_clicks": 96,
        "base_conversions": 14, "base_spend": 490.0,
    },
}

# ---------------------------------------------------------------------------
# Campaign themes — 10 themes × 5 channels = 50 campaigns
# ---------------------------------------------------------------------------
CAMPAIGN_THEMES = [
    {"theme": "Spring Sale",           "objective": "conversions", "vertical": "retail"},
    {"theme": "Brand Awareness Q1",    "objective": "awareness",   "vertical": "brand"},
    {"theme": "Product Launch Alpha",  "objective": "conversions", "vertical": "tech"},
    {"theme": "Retargeting Warm",      "objective": "retargeting", "vertical": "retail"},
    {"theme": "Loyalty Program",       "objective": "retention",   "vertical": "retail"},
    {"theme": "Webinar Series",        "objective": "leads",       "vertical": "b2b"},
    {"theme": "Summer Preview",        "objective": "awareness",   "vertical": "retail"},
    {"theme": "Enterprise Outreach",   "objective": "leads",       "vertical": "b2b"},
    {"theme": "Flash Deals",           "objective": "conversions", "vertical": "retail"},
    {"theme": "Content Syndication",   "objective": "awareness",   "vertical": "media"},
]

# ---------------------------------------------------------------------------
# Budget tiers (monthly)
# ---------------------------------------------------------------------------
BUDGET_TIERS = {
    "google_ads":   {"min": 10000, "max": 30000},
    "meta_ads":     {"min": 8000,  "max": 25000},
    "tiktok_ads":   {"min": 5000,  "max": 20000},
    "email":        {"min": 2000,  "max": 8000},
    "linkedin_ads": {"min": 8000,  "max": 25000},
}

# ---------------------------------------------------------------------------
# Audience segments
# ---------------------------------------------------------------------------
AUDIENCE_SEGMENTS = [
    "18-24_female", "18-24_male",
    "25-34_female", "25-34_male",
    "35-44_female", "35-44_male",
    "45-54_female", "45-54_male",
    "55+_female",   "55+_male",
]

# ---------------------------------------------------------------------------
# Creative asset templates
# ---------------------------------------------------------------------------
CREATIVE_TYPES = ["image", "video", "carousel", "text_ad"]

CREATIVE_FORMATS = {
    "google_ads":   ["text_ad", "image"],
    "meta_ads":     ["image", "video", "carousel"],
    "tiktok_ads":   ["video"],
    "email":        ["image", "text_ad"],
    "linkedin_ads": ["image", "text_ad", "carousel"],
}

# ---------------------------------------------------------------------------
# Competitor names
# ---------------------------------------------------------------------------
COMPETITORS = [
    "CompetitorAlpha", "CompetitorBeta", "CompetitorGamma",
    "CompetitorDelta", "CompetitorEpsilon",
]

# ---------------------------------------------------------------------------
# Anomaly scenarios — 6 scenarios for demo
# ---------------------------------------------------------------------------
ANOMALY_SCENARIOS = [
    {
        "id": "google_cpa_spike",
        "description": "Google Ads CPA spikes 2.3× due to auction pressure",
        "campaign_id": "CAMP-2026-041",      # Flash Deals / google_ads
        "channel": "google_ads",
        "trigger_date": "2026-02-18",
        "affected_metrics": ["cpa", "roas"],
        "severity": "high",
    },
    {
        "id": "meta_creative_fatigue",
        "description": "Meta carousel creative hits fatigue after 12 days",
        "campaign_id": "CAMP-2026-017",      # Retargeting Warm / meta_ads
        "channel": "meta_ads",
        "trigger_date": "2026-02-12",
        "affected_metrics": ["ctr", "fatigue_score"],
        "severity": "medium",
    },
    {
        "id": "email_deliverability",
        "description": "Email open rate drops 40% due to deliverability issue",
        "campaign_id": "CAMP-2026-024",      # Loyalty Program / email
        "channel": "email",
        "trigger_date": "2026-02-20",
        "affected_metrics": ["open_rate", "ctr"],
        "severity": "high",
    },
    {
        "id": "budget_overpace",
        "description": "TikTok campaign overspending — pace ratio hits 1.4×",
        "campaign_id": "CAMP-2026-018",      # Retargeting Warm / tiktok_ads
        "channel": "tiktok_ads",
        "trigger_date": "2026-02-18",
        "affected_metrics": ["pace_ratio", "projected_overspend"],
        "severity": "high",
    },
    {
        "id": "audience_churn",
        "description": "25-34 female segment churn risk rising across campaigns",
        "campaign_id": "CAMP-2026-001",      # Spring Sale / google_ads
        "channel": "google_ads",
        "trigger_date": "2026-02-17",
        "affected_metrics": ["churn_risk", "conversion_rate"],
        "severity": "medium",
        "target_segment": "25-34_female",
    },
    {
        "id": "competitor_launch",
        "description": "CompetitorAlpha launches aggressive spring campaign",
        "campaign_id": None,                  # Affects market-wide signals
        "channel": None,
        "trigger_date": "2026-02-18",
        "affected_metrics": ["impression_share", "avg_cpc"],
        "severity": "high",
        "competitor": "CompetitorAlpha",
    },
]

# ---------------------------------------------------------------------------
# Action log seed templates
# ---------------------------------------------------------------------------
ACTION_TYPES = [
    "budget_reallocation",
    "creative_swap",
    "audience_exclusion",
    "bid_adjustment",
    "pause_campaign",
    "resume_campaign",
]

ACTION_STATUSES = ["proposed", "approved", "executed", "rejected"]


def build_campaign_list():
    """
    Generate 50 campaigns: 10 themes × 5 channels.
    Each campaign gets a unique CAMP-2026-NNN id and belongs to one channel.
    """
    campaigns = []
    idx = 1
    for theme_info in CAMPAIGN_THEMES:
        for channel in CHANNELS:
            budget_range = BUDGET_TIERS[channel]
            rng = random.Random(RANDOM_SEED + idx)
            monthly_budget = round(rng.uniform(budget_range["min"], budget_range["max"]), 2)
            campaigns.append({
                "campaign_id": f"CAMP-2026-{idx:03d}",
                "campaign_name": f"{theme_info['theme']} — {channel.replace('_', ' ').title()}",
                "channel": channel,
                "objective": theme_info["objective"],
                "vertical": theme_info["vertical"],
                "status": "active",
                "start_date": str(DATE_START),
                "end_date": "2026-03-31",
                "monthly_budget": monthly_budget,
            })
            idx += 1
    return campaigns
