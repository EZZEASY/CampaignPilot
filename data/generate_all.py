#!/usr/bin/env python3
"""
Synthetic data generator for CampaignPilot v2.1.
Outputs 11 NDJSON files to data_output/.

Usage:
    python data/generate_all.py
"""

import json
import math
import os
import random
import sys
from datetime import date, timedelta, datetime

# Ensure project root is on path so we can import config
sys.path.insert(0, os.path.dirname(__file__))
from config import (
    RANDOM_SEED, DATE_START, DATE_END, CHANNELS, CHANNEL_DEFAULTS,
    CAMPAIGN_THEMES, BUDGET_TIERS, AUDIENCE_SEGMENTS, CREATIVE_FORMATS,
    COMPETITORS, ANOMALY_SCENARIOS, ACTION_TYPES, ACTION_STATUSES,
    AD_GROUPS_BY_OBJECTIVE, CREATIVES_PER_AD_GROUP, HEADLINES, CTAS,
    LANDING_PAGES, PRODUCTS, SUPPORT_CATEGORIES, SUPPORT_SUBCATEGORIES,
    PRICE_COMPLAINT_SUBJECTS, PRICE_COMPLAINT_SUMMARIES, NORMAL_TICKET_SUBJECTS,
    CROSS_SYSTEM_SCENARIOS, CREATIVE_FATIGUE_SCENARIO,
    _OBJECTIVE_KEY_MAP,
    build_campaign_list,
)

random.seed(RANDOM_SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_output")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def date_range(start: date, end: date):
    """Yield dates from start to end inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def sigmoid_ramp(day_offset: int, steepness: float = 1.0, midpoint: float = 3.0) -> float:
    """
    Smooth sigmoid transition.
    day_offset: days since trigger (0 = trigger day).
    Returns 0..1 value.
    """
    return 1.0 / (1.0 + math.exp(-steepness * (day_offset - midpoint)))


def jitter(value: float, pct: float = 0.10) -> float:
    """Add random jitter ±pct to a value."""
    return value * random.uniform(1 - pct, 1 + pct)


def write_ndjson(filename: str, docs: list[dict]):
    """Write list of dicts as NDJSON."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        for doc in docs:
            f.write(json.dumps(doc, default=str) + "\n")
    print(f"  {filename}: {len(docs)} docs")


# ---------------------------------------------------------------------------
# Anomaly lookup helpers
# ---------------------------------------------------------------------------

def get_anomaly(scenario_id: str) -> dict:
    for s in ANOMALY_SCENARIOS:
        if s["id"] == scenario_id:
            return s
    return {}


def anomaly_day_offset(trigger_date_str: str, current_date: date) -> int:
    trigger = date.fromisoformat(trigger_date_str)
    return (current_date - trigger).days


# ---------------------------------------------------------------------------
# 1. Campaigns
# ---------------------------------------------------------------------------

def generate_campaigns(campaign_list: list[dict]) -> list[dict]:
    """Generate campaign documents with descriptions."""
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED)

    docs = []
    for c in campaign_list:
        doc = {
            **c,
            "description": (
                f"{c['campaign_name']} campaign targeting {c['vertical']} vertical "
                f"with {c['objective']} objective on {c['channel'].replace('_', ' ')}. "
                f"Monthly budget ${c['monthly_budget']:,.0f}. "
                f"{fake.sentence()}"
            ),
        }
        docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# 2. Creative Assets — Campaign → Ad Group → Creative hierarchy (v2.1)
# ---------------------------------------------------------------------------

def generate_creative_assets(campaign_list: list[dict]) -> tuple[list[dict], dict]:
    """
    Generate creative assets with Campaign → Ad Group → Creative hierarchy.
    Returns (asset_docs, ad_groups_map).

    ad_groups_map structure:
        {campaign_id: {"channel": ..., "ad_groups": [{"ad_group_id": ..., "ad_group_name": ...,
         "audience_id": ..., "creatives": [{"creative_id": ..., "launch_date": ...}]}]}}
    """
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED + 100)

    docs = []
    ad_groups_map = {}
    creative_idx = 1
    ag_idx = 1

    for c in campaign_list:
        channel = c["channel"]
        formats = CREATIVE_FORMATS.get(channel, ["image"])
        objective = c["objective"]
        obj_key = _OBJECTIVE_KEY_MAP.get(objective, "conversions")
        ag_templates = AD_GROUPS_BY_OBJECTIVE.get(obj_key, AD_GROUPS_BY_OBJECTIVE["conversions"])

        campaign_ad_groups = []

        for ag_template in ag_templates:
            ad_group_id = f"AG-{ag_idx:04d}"
            ag_idx += 1

            n_creatives = random.randint(*CREATIVES_PER_AD_GROUP)
            creatives_in_ag = []

            for ci in range(n_creatives):
                creative_id = f"CRE-{creative_idx:04d}"
                creative_idx += 1

                creative_type = random.choice(formats)
                launch_date = DATE_START + timedelta(days=random.randint(0, 5))
                theme = c["campaign_name"].split(" — ")[0]
                vertical = c["vertical"]

                headline_tpl = random.choice(HEADLINES)
                headline = headline_tpl.format(
                    pct=random.randint(10, 50),
                    vertical=vertical.title(),
                    theme=theme,
                )
                cta = random.choice(CTAS)
                ab_group = "A" if ci % 2 == 0 else "B"

                doc = {
                    "creative_id": creative_id,
                    "campaign_id": c["campaign_id"],
                    "ad_group_id": ad_group_id,
                    "ad_group_name": ag_template["name"],
                    "channel": channel,
                    "audience_id": ag_template["audience_id"],
                    "type": creative_type,
                    "headline": headline,
                    "description": (
                        f"{creative_type.replace('_', ' ').title()} creative for "
                        f"{c['campaign_name']}. {fake.sentence()}"
                    ),
                    "cta": cta,
                    "visual_description": fake.sentence(),
                    "ab_group": ab_group,
                    "launch_date": str(launch_date),
                    "status": "active",
                }
                docs.append(doc)
                creatives_in_ag.append({
                    "creative_id": creative_id,
                    "launch_date": str(launch_date),
                })

            campaign_ad_groups.append({
                "ad_group_id": ad_group_id,
                "ad_group_name": ag_template["name"],
                "audience_id": ag_template["audience_id"],
                "creatives": creatives_in_ag,
            })

        ad_groups_map[c["campaign_id"]] = {
            "channel": channel,
            "ad_groups": campaign_ad_groups,
        }

    return docs, ad_groups_map


# ---------------------------------------------------------------------------
# 3. Creative Metrics — daily timeseries per creative (v2.1)
# ---------------------------------------------------------------------------

def generate_creative_metrics(ad_groups_map: dict) -> list[dict]:
    """Generate daily creative-level metrics with fatigue curves and anomaly injections."""
    cdn_scenario = CROSS_SYSTEM_SCENARIOS["cdn_crash_cascade"]
    price_scenario = CROSS_SYSTEM_SCENARIOS["price_increase_cascade"]
    fatigue_scenario = CREATIVE_FATIGUE_SCENARIO

    docs = []

    for campaign_id, camp_info in ad_groups_map.items():
        channel = camp_info["channel"]
        defaults = CHANNEL_DEFAULTS[channel]

        for ag in camp_info["ad_groups"]:
            ad_group_id = ag["ad_group_id"]
            n_creatives = len(ag["creatives"])

            for cre in ag["creatives"]:
                creative_id = cre["creative_id"]
                launch = date.fromisoformat(cre["launch_date"])

                for d in date_range(DATE_START, DATE_END):
                    if d < launch:
                        continue

                    days_since_launch = (d - launch).days
                    dow_factor = 0.85 if d.weekday() >= 5 else 1.0

                    # Natural fatigue curve
                    fatigue = min(0.95, 0.05 + (days_since_launch / 55) ** 1.5)

                    # Creative fatigue scenario — accelerated fatigue for specific campaign
                    if (campaign_id == fatigue_scenario["campaign_id"]
                            and channel == fatigue_scenario["channel"]
                            and days_since_launch >= fatigue_scenario["fatigue_start_day"]):
                        accel_days = days_since_launch - fatigue_scenario["fatigue_start_day"]
                        fatigue = min(0.95, fatigue + accel_days * 0.04 * fatigue_scenario["fatigue_acceleration"])

                    performance_factor = 1.0 - fatigue * 0.6

                    # Per-creative share of campaign totals
                    share = 1.0 / max(n_creatives * len(ad_groups_map.get(campaign_id, {}).get("ad_groups", [None])), 1)

                    impressions = int(jitter(defaults["base_impressions"] * share * dow_factor, 0.15))
                    clicks = int(jitter(defaults["base_clicks"] * share * dow_factor * performance_factor, 0.18))
                    conversions = max(int(jitter(defaults["base_conversions"] * share * dow_factor * performance_factor, 0.20)), 0)
                    spend = round(jitter(defaults["base_spend"] * share * dow_factor, 0.12), 2)
                    revenue = round(spend * defaults["base_roas"] * performance_factor * random.uniform(0.9, 1.1), 2)

                    ctr = round(clicks / max(impressions, 1), 5)
                    cpa = round(spend / max(conversions, 1), 2)
                    roas = round(revenue / max(spend, 0.01), 2)
                    conversion_rate = round(conversions / max(clicks, 1), 4)
                    frequency = round(1.0 + days_since_launch * 0.15 * random.uniform(0.8, 1.2), 2)

                    # CDN crash cascade — spike CPA on trigger date
                    if campaign_id in cdn_scenario["affected_campaigns"]:
                        offset = anomaly_day_offset(cdn_scenario["trigger_date"], d)
                        if 0 <= offset <= 2:
                            ramp = sigmoid_ramp(offset, steepness=3.0, midpoint=0.5)
                            conversions = max(int(conversions * (1 - 0.7 * ramp)), 0)
                            cpa = round(spend / max(conversions, 1), 2)
                            roas = round(revenue / max(spend, 0.01) * (1 - 0.6 * ramp), 2)

                    # Price increase cascade — conversion rate drops
                    if campaign_id in price_scenario["affected_campaigns"]:
                        offset = anomaly_day_offset(price_scenario["trigger_date"], d)
                        if offset >= 0:
                            drop = price_scenario["conversion_drop_pct"] / 100
                            ramp = sigmoid_ramp(offset, steepness=0.8, midpoint=3.0)
                            conversions = max(int(conversions * (1 - drop * ramp)), 0)
                            conversion_rate = round(conversions / max(clicks, 1), 4)
                            cpa = round(spend / max(conversions, 1), 2)

                    ts = datetime(d.year, d.month, d.day, 23, 59, 0)

                    doc = {
                        "@timestamp": ts.isoformat(),
                        "date": str(d),
                        "creative_id": creative_id,
                        "campaign_id": campaign_id,
                        "ad_group_id": ad_group_id,
                        "channel": channel,
                        "impressions": max(impressions, 10),
                        "clicks": max(clicks, 0),
                        "conversions": conversions,
                        "spend": spend,
                        "revenue": revenue,
                        "ctr": max(ctr, 0.0),
                        "cpa": cpa,
                        "roas": max(roas, 0.0),
                        "conversion_rate": max(conversion_rate, 0.0),
                        "frequency": frequency,
                        "fatigue_score": round(fatigue, 3),
                    }
                    docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# 4. Channel Metrics — returns (docs, spend_map) for cross-index consistency
# ---------------------------------------------------------------------------

def generate_channel_metrics(campaign_list: list[dict]) -> tuple[list[dict], dict]:
    """
    Generate daily channel metrics for each campaign.
    Returns (docs, spend_map) where spend_map[(campaign_id, date_str)] = spend.
    """
    google_spike = get_anomaly("google_cpa_spike")
    meta_fatigue = get_anomaly("meta_creative_fatigue")
    email_deliv = get_anomaly("email_deliverability")
    budget_overpace = get_anomaly("budget_overpace")

    docs = []
    spend_map = {}

    for c in campaign_list:
        channel = c["channel"]
        defaults = CHANNEL_DEFAULTS[channel]

        for d in date_range(DATE_START, DATE_END):
            # Day-of-week seasonality (weekends slightly lower)
            dow_factor = 0.85 if d.weekday() >= 5 else 1.0

            impressions = int(jitter(defaults["base_impressions"] * dow_factor, 0.12))
            clicks = int(jitter(defaults["base_clicks"] * dow_factor, 0.15))
            conversions = int(jitter(defaults["base_conversions"] * dow_factor, 0.18))
            spend = round(jitter(defaults["base_spend"] * dow_factor, 0.10), 2)
            ctr = round(clicks / max(impressions, 1), 5)
            cpa = round(spend / max(conversions, 1), 2)
            revenue = round(spend * defaults["base_roas"] * random.uniform(0.9, 1.1), 2)
            roas = round(revenue / max(spend, 0.01), 2)

            # --- Anomaly injections ---

            # 1. Google CPA spike
            if (google_spike and c["campaign_id"] == google_spike["campaign_id"]
                    and channel == "google_ads"):
                offset = anomaly_day_offset(google_spike["trigger_date"], d)
                if offset >= 0:
                    factor = 1.0 + 1.3 * sigmoid_ramp(offset, steepness=1.2, midpoint=2.0)
                    cpa = round(cpa * factor, 2)
                    spend = round(cpa * max(conversions, 1), 2)
                    roas = round(roas / factor, 2)

            # 2. Meta creative fatigue — CTR decay
            if (meta_fatigue and c["campaign_id"] == meta_fatigue["campaign_id"]
                    and channel == "meta_ads"):
                offset = anomaly_day_offset(meta_fatigue["trigger_date"], d)
                if offset >= 0:
                    decay = 1.0 - 0.55 * sigmoid_ramp(offset, steepness=0.6, midpoint=5.0)
                    ctr = round(ctr * decay, 5)
                    clicks = max(int(impressions * ctr), 1)
                    conversions = max(int(conversions * decay), 0)

            # 3. Budget overpace — increase spend
            if (budget_overpace and c["campaign_id"] == budget_overpace["campaign_id"]):
                offset = anomaly_day_offset(budget_overpace["trigger_date"], d)
                if offset >= 0:
                    overpace_factor = 1.0 + 0.4 * sigmoid_ramp(offset, steepness=1.5, midpoint=2.0)
                    spend = round(spend * overpace_factor, 2)
                    cpa = round(spend / max(conversions, 1), 2)

            # 4. Email deliverability drop
            if (email_deliv and c["campaign_id"] == email_deliv["campaign_id"]
                    and channel == "email"):
                offset = anomaly_day_offset(email_deliv["trigger_date"], d)
                if offset >= 0:
                    drop = 1.0 - 0.40 * sigmoid_ramp(offset, steepness=2.0, midpoint=1.0)
                    clicks = max(int(clicks * drop), 1)
                    conversions = max(int(conversions * drop), 0)
                    ctr = round(clicks / max(impressions, 1), 5)
                    cpa = round(spend / max(conversions, 1), 2)

            doc = {
                "campaign_id": c["campaign_id"],
                "channel": channel,
                "date": str(d),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "spend": spend,
                "cpa": cpa,
                "ctr": ctr,
                "roas": roas,
                "revenue": revenue,
            }
            docs.append(doc)
            spend_map[(c["campaign_id"], str(d))] = spend

    return docs, spend_map


# ---------------------------------------------------------------------------
# 5. Budget Ledger — uses spend_map for cross-index consistency
# ---------------------------------------------------------------------------

def generate_budget_ledger(campaign_list: list[dict], spend_map: dict) -> list[dict]:
    """Generate daily budget ledger entries, sharing spend with channel-metrics."""
    docs = []
    days_in_month = 28  # Feb 2026

    for c in campaign_list:
        monthly_budget = c["monthly_budget"]
        daily_budget = round(monthly_budget / days_in_month, 2)
        cumulative = 0.0

        for d in date_range(DATE_START, DATE_END):
            actual_spend = spend_map.get((c["campaign_id"], str(d)), daily_budget)
            cumulative += actual_spend
            day_number = (d - DATE_START).days + 1
            expected_cumulative = daily_budget * day_number
            pace_ratio = round(cumulative / max(expected_cumulative, 0.01), 3)
            projected_total = round(cumulative / max(day_number, 1) * days_in_month, 2)
            projected_overspend = round(max(projected_total - monthly_budget, 0), 2)
            remaining = round(max(monthly_budget - cumulative, 0), 2)

            doc = {
                "campaign_id": c["campaign_id"],
                "channel": c["channel"],
                "date": str(d),
                "daily_budget": daily_budget,
                "actual_spend": actual_spend,
                "cumulative_spend": round(cumulative, 2),
                "monthly_budget": monthly_budget,
                "pace_ratio": pace_ratio,
                "projected_overspend": projected_overspend,
                "remaining_budget": remaining,
            }
            docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# 6. Audience Segments
# ---------------------------------------------------------------------------

def generate_audience_segments(campaign_list: list[dict]) -> list[dict]:
    """Generate daily audience segment metrics for a subset of campaigns."""
    audience_churn = get_anomaly("audience_churn")
    docs = []

    # Not all campaigns have audience breakdowns — pick ~60%
    selected = [c for c in campaign_list if hash(c["campaign_id"]) % 5 < 3]

    for c in selected:
        channel = c["channel"]
        defaults = CHANNEL_DEFAULTS[channel]

        for seg in AUDIENCE_SEGMENTS:
            # Each segment gets ~10% of total with some variation
            seg_fraction = random.uniform(0.06, 0.15)

            for d in date_range(DATE_START, DATE_END):
                dow_factor = 0.85 if d.weekday() >= 5 else 1.0
                reach = int(jitter(defaults["base_impressions"] * seg_fraction * 2, 0.2))
                impressions = int(jitter(defaults["base_impressions"] * seg_fraction * dow_factor, 0.15))
                clicks = int(jitter(defaults["base_clicks"] * seg_fraction * dow_factor, 0.18))
                conversions = max(int(jitter(defaults["base_conversions"] * seg_fraction * dow_factor, 0.22)), 0)
                conversion_rate = round(conversions / max(clicks, 1), 4)
                base_churn = random.uniform(0.05, 0.15)
                engagement = round(random.uniform(0.4, 0.85), 3)

                churn_risk = round(jitter(base_churn, 0.1), 3)

                # Anomaly: audience churn
                if (audience_churn
                        and c["campaign_id"] == audience_churn["campaign_id"]
                        and seg == audience_churn.get("target_segment")):
                    offset = anomaly_day_offset(audience_churn["trigger_date"], d)
                    if offset >= 0:
                        churn_boost = 0.5 * sigmoid_ramp(offset, steepness=0.8, midpoint=3.0)
                        churn_risk = round(min(churn_risk + churn_boost, 0.85), 3)
                        conversion_rate = round(conversion_rate * (1 - churn_boost * 0.6), 4)
                        engagement = round(engagement * (1 - churn_boost * 0.4), 3)

                doc = {
                    "campaign_id": c["campaign_id"],
                    "segment": seg,
                    "date": str(d),
                    "reach": max(reach, 10),
                    "impressions": max(impressions, 10),
                    "clicks": max(clicks, 0),
                    "conversions": conversions,
                    "conversion_rate": max(conversion_rate, 0.0),
                    "churn_risk": churn_risk,
                    "engagement_score": max(engagement, 0.05),
                }
                docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# 7. Competitor Signals
# ---------------------------------------------------------------------------

def generate_competitor_signals() -> list[dict]:
    """Generate competitor signal documents."""
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED + 200)

    comp_launch = get_anomaly("competitor_launch")

    signal_types = ["new_campaign", "price_change", "ad_copy_change", "budget_increase", "market_entry"]
    impact_levels = ["low", "medium", "high"]
    docs = []
    sig_idx = 1

    for d in date_range(DATE_START, DATE_END):
        # 2-5 signals per day across competitors
        n_signals = random.randint(2, 5)
        for _ in range(n_signals):
            competitor = random.choice(COMPETITORS)
            signal_type = random.choice(signal_types)
            channel = random.choice(CHANNELS)
            impact = random.choice(impact_levels)
            impression_share = round(random.uniform(0.05, 0.25), 3)
            estimated_spend = round(random.uniform(500, 5000), 2)
            avg_cpc = round(random.uniform(0.5, 3.5), 2)

            # Anomaly: competitor launch
            if (comp_launch and competitor == comp_launch.get("competitor")):
                offset = anomaly_day_offset(comp_launch["trigger_date"], d)
                if offset >= 0:
                    ramp = sigmoid_ramp(offset, steepness=1.5, midpoint=1.5)
                    impression_share = round(min(impression_share + 0.3 * ramp, 0.65), 3)
                    estimated_spend = round(estimated_spend * (1 + 2.0 * ramp), 2)
                    avg_cpc = round(avg_cpc * (1 + 0.5 * ramp), 2)
                    if offset <= 3:
                        impact = "high"
                        signal_type = "new_campaign"

            doc = {
                "signal_id": f"SIG-{sig_idx:04d}",
                "date": str(d),
                "competitor": competitor,
                "signal_type": signal_type,
                "channel": channel,
                "description": (
                    f"{competitor} {signal_type.replace('_', ' ')} detected on "
                    f"{channel.replace('_', ' ')}. {fake.sentence()}"
                ),
                "impact_level": impact,
                "impression_share": impression_share,
                "estimated_spend": estimated_spend,
                "avg_cpc": avg_cpc,
            }
            docs.append(doc)
            sig_idx += 1

    return docs


# ---------------------------------------------------------------------------
# 8. Action Log (seed data)
# ---------------------------------------------------------------------------

def generate_action_log(campaign_list: list[dict]) -> list[dict]:
    """Generate seed action log entries."""
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED + 300)

    docs = []
    action_idx = 1

    # Generate ~50 seed actions spread across campaign lifecycle
    for _ in range(50):
        c = random.choice(campaign_list)
        action_type = random.choice(ACTION_TYPES)
        status = random.choice(ACTION_STATUSES)
        d = DATE_START + timedelta(days=random.randint(0, (DATE_END - DATE_START).days))
        hour = random.randint(8, 18)
        ts = datetime(d.year, d.month, d.day, hour, random.randint(0, 59), random.randint(0, 59))

        params = {}
        if action_type == "budget_reallocation":
            params = {"from_amount": round(random.uniform(100, 500), 2),
                      "to_amount": round(random.uniform(100, 500), 2)}
        elif action_type == "bid_adjustment":
            params = {"adjustment_pct": round(random.uniform(-20, 30), 1)}
        elif action_type == "creative_swap":
            params = {"old_asset": f"CRE-{random.randint(1, 200):04d}",
                      "new_asset": f"CRE-{random.randint(1, 200):04d}"}

        doc = {
            "action_id": f"ACT-{action_idx:04d}",
            "campaign_id": c["campaign_id"],
            "channel": c["channel"],
            "action_type": action_type,
            "status": status,
            "timestamp": ts.isoformat(),
            "description": (
                f"{action_type.replace('_', ' ').title()} for {c['campaign_name']}. "
                f"{fake.sentence()}"
            ),
            "parameters": params,
            "outcome": fake.sentence() if status == "executed" else None,
        }
        docs.append(doc)
        action_idx += 1

    return docs


# ---------------------------------------------------------------------------
# 9. Website Events (v2.1)
# ---------------------------------------------------------------------------

def generate_website_events(campaign_list: list[dict]) -> list[dict]:
    """Generate website landing page events with CDN crash scenario."""
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED + 400)

    cdn_scenario = CROSS_SYSTEM_SCENARIOS["cdn_crash_cascade"]
    devices = ["desktop", "mobile", "tablet"]
    countries = ["US", "UK", "CA", "DE", "FR", "AU"]
    docs = []
    session_idx = 1

    for d in date_range(DATE_START, DATE_END):
        # ~80-120 sessions per day across landing pages
        n_sessions = random.randint(80, 120)
        for _ in range(n_sessions):
            page_url = random.choice(LANDING_PAGES)
            # Assign to a random campaign that matches the page theme
            c = random.choice(campaign_list)
            device = random.choice(devices)
            country = random.choice(countries)

            # Base metrics
            load_time = int(jitter(1200, 0.3))  # ~1200ms baseline
            bounce = random.random() < 0.35
            converted = (not bounce) and (random.random() < 0.12)
            timeout = False
            cdn_status = "healthy"

            # CDN crash cascade injection
            if page_url in cdn_scenario["affected_pages"]:
                offset = anomaly_day_offset(cdn_scenario["trigger_date"], d)
                if 0 <= offset <= 2:
                    ramp = sigmoid_ramp(offset, steepness=3.0, midpoint=0.5)
                    load_time = int(load_time + cdn_scenario["load_time_spike_ms"] * ramp)
                    cdn_status = cdn_scenario["cdn_status"]
                    bounce = random.random() < (0.35 + 0.45 * ramp)
                    converted = (not bounce) and (random.random() < 0.03)
                    timeout = random.random() < 0.3 * ramp

            hour = random.randint(6, 23)
            ts = datetime(d.year, d.month, d.day, hour, random.randint(0, 59), random.randint(0, 59))

            doc = {
                "@timestamp": ts.isoformat(),
                "date": str(d),
                "page_url": page_url,
                "campaign_id": c["campaign_id"],
                "channel": c["channel"],
                "session_id": f"SESS-{session_idx:06d}",
                "load_time_ms": load_time,
                "bounce": bounce,
                "converted": converted,
                "timeout": timeout,
                "cdn_status": cdn_status,
                "device": device,
                "country": country,
            }
            docs.append(doc)
            session_idx += 1

    return docs


# ---------------------------------------------------------------------------
# 10. Product Catalog (v2.1)
# ---------------------------------------------------------------------------

def generate_product_catalog() -> list[dict]:
    """Generate product catalog events (price changes, stock updates)."""
    price_scenario = CROSS_SYSTEM_SCENARIOS["price_increase_cascade"]
    docs = []

    event_types = ["price_check", "stock_update", "price_change"]

    for d in date_range(DATE_START, DATE_END):
        for prod in PRODUCTS:
            event_type = "price_check"
            old_price = prod["base_price"]
            new_price = prod["base_price"]
            change_pct = 0.0
            stock_status = "in_stock"

            # Price increase cascade
            if prod["product_id"] == price_scenario["product_id"]:
                offset = anomaly_day_offset(price_scenario["trigger_date"], d)
                if offset == 0:
                    event_type = "price_change"
                    new_price = round(old_price * (1 + price_scenario["price_change_pct"] / 100), 2)
                    change_pct = price_scenario["price_change_pct"]
                elif offset > 0:
                    # Price remains elevated
                    event_type = "price_check"
                    old_price = round(prod["base_price"] * (1 + price_scenario["price_change_pct"] / 100), 2)
                    new_price = old_price
                    change_pct = 0.0

            # Random stock fluctuations for variety
            if random.random() < 0.05:
                stock_status = random.choice(["low_stock", "out_of_stock"])
                if stock_status == "out_of_stock":
                    event_type = "out_of_stock"

            ts = datetime(d.year, d.month, d.day, 8, 0, 0)

            doc = {
                "@timestamp": ts.isoformat(),
                "date": str(d),
                "product_id": prod["product_id"],
                "product_name": prod["name"],
                "event_type": event_type,
                "old_price": old_price,
                "new_price": new_price,
                "change_pct": change_pct,
                "stock_status": stock_status,
                "category": "consumer_goods",
            }
            docs.append(doc)

    return docs


# ---------------------------------------------------------------------------
# 11. Support Tickets (v2.1)
# ---------------------------------------------------------------------------

def generate_support_tickets() -> list[dict]:
    """Generate customer support tickets with price complaint surge."""
    from faker import Faker
    fake = Faker()
    Faker.seed(RANDOM_SEED + 500)

    price_scenario = CROSS_SYSTEM_SCENARIOS["price_increase_cascade"]
    docs = []
    ticket_idx = 1

    for d in date_range(DATE_START, DATE_END):
        # Base: 10-20 tickets per day
        n_tickets = random.randint(10, 20)

        # Price increase cascade: surge of complaint tickets
        price_offset = anomaly_day_offset(price_scenario["trigger_date"], d)
        extra_complaints = 0
        if price_offset >= 0:
            ramp = sigmoid_ramp(price_offset, steepness=1.0, midpoint=2.0)
            extra_complaints = int(15 * ramp)

        for i in range(n_tickets + extra_complaints):
            is_price_complaint = i >= n_tickets  # extra tickets are price complaints

            if is_price_complaint:
                category = "billing"
                subcategory = "charge_dispute"
                product = random.choice(PRODUCTS)
                subject_tpl = random.choice(PRICE_COMPLAINT_SUBJECTS)
                subject = subject_tpl.format(product=product["name"])
                summary_tpl = random.choice(PRICE_COMPLAINT_SUMMARIES)
                summary = summary_tpl.format(
                    pct=price_scenario["price_change_pct"],
                    product=product["name"],
                )
                sentiment = round(random.uniform(-0.9, -0.5), 2)
                priority = "high"
            else:
                category = random.choice(SUPPORT_CATEGORIES)
                subcategory = random.choice(SUPPORT_SUBCATEGORIES[category])
                subject = random.choice(NORMAL_TICKET_SUBJECTS)
                summary = fake.sentence(nb_words=12)
                sentiment = round(random.uniform(-0.3, 0.5), 2)
                priority = random.choice(["low", "medium", "high"])

            channel = random.choice(CHANNELS)
            segment = random.choice(AUDIENCE_SEGMENTS)

            hour = random.randint(7, 22)
            ts = datetime(d.year, d.month, d.day, hour, random.randint(0, 59), random.randint(0, 59))

            doc = {
                "@timestamp": ts.isoformat(),
                "date": str(d),
                "ticket_id": f"TKT-{ticket_idx:05d}",
                "category": category,
                "subcategory": subcategory,
                "channel": channel,
                "segment": segment,
                "campaign_id": random.choice([""] + [f"CAMP-2026-{i:03d}" for i in range(1, 51)]),
                "sentiment": sentiment,
                "priority": priority,
                "status": random.choice(["open", "in_progress", "resolved", "closed"]),
                "content": {
                    "subject": subject,
                    "summary": summary,
                },
            }
            docs.append(doc)
            ticket_idx += 1

    return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("CampaignPilot v2.1 — Generating synthetic data...")
    print(f"  Random seed: {RANDOM_SEED}")
    print(f"  Date range: {DATE_START} to {DATE_END}")
    print()

    # 1. Campaigns
    campaign_list = build_campaign_list()
    campaigns = generate_campaigns(campaign_list)
    write_ndjson("campaigns.ndjson", campaigns)

    # 2. Channel Metrics (also produces spend_map)
    metrics, spend_map = generate_channel_metrics(campaign_list)
    write_ndjson("channel-metrics.ndjson", metrics)

    # 3. Creative Assets (returns tuple: docs + ad_groups_map)
    creatives, ad_groups_map = generate_creative_assets(campaign_list)
    write_ndjson("creative-assets.ndjson", creatives)

    # 4. Creative Metrics (uses ad_groups_map)
    creative_metrics = generate_creative_metrics(ad_groups_map)
    write_ndjson("creative-metrics.ndjson", creative_metrics)

    # 5. Audience Segments
    segments = generate_audience_segments(campaign_list)
    write_ndjson("audience-segments.ndjson", segments)

    # 6. Competitor Signals
    signals = generate_competitor_signals()
    write_ndjson("competitor-signals.ndjson", signals)

    # 7. Budget Ledger (uses spend_map for consistency)
    ledger = generate_budget_ledger(campaign_list, spend_map)
    write_ndjson("budget-ledger.ndjson", ledger)

    # 8. Action Log
    actions = generate_action_log(campaign_list)
    write_ndjson("action-log.ndjson", actions)

    # 9. Website Events
    website_events = generate_website_events(campaign_list)
    write_ndjson("website-events.ndjson", website_events)

    # 10. Product Catalog
    product_catalog = generate_product_catalog()
    write_ndjson("product-catalog.ndjson", product_catalog)

    # 11. Support Tickets
    support_tickets = generate_support_tickets()
    write_ndjson("support-tickets.ndjson", support_tickets)

    print()
    print("Done! 11 files written to data_output/")


if __name__ == "__main__":
    main()
