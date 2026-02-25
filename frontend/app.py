"""
CampaignPilot Streamlit Frontend — 4-tab marketing intelligence dashboard.

Tabs:
  1. Dashboard — KPI cards, daily trends, channel breakdown
  2. Anomaly Alerts — severity-sorted anomaly cards
  3. Chat with Agent — conversational interface via Agent Builder or OpenRouter
  4. Action Log — filterable action history table

Usage:
    streamlit run frontend/app.py
"""

import os
import sys
import json

import streamlit as st

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from tools.es_client import run_esql
from tools.metrics_tools import get_metrics_summary
from tools.budget_tools import get_portfolio_budget_summary
from tools.competitor_tools import get_competitor_summary
from tools.action_tools import get_actions
from workflows.anomaly_scan import run_anomaly_scan

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CampaignPilot",
    page_icon="📊",
    layout="wide",
)

st.title("CampaignPilot — Marketing Intelligence")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_dashboard, tab_alerts, tab_chat, tab_actions = st.tabs([
    "📊 Dashboard", "🚨 Anomaly Alerts", "💬 Chat with Agent", "📋 Action Log"
])

# ===== TAB 1: Dashboard =====
with tab_dashboard:
    st.header("Portfolio Overview")

    # KPI cards
    try:
        totals = run_esql(
            'FROM channel-metrics'
            ' | STATS total_spend = SUM(spend), total_conversions = SUM(conversions),'
            ' avg_cpa = AVG(cpa), avg_roas = AVG(roas), avg_ctr = AVG(ctr),'
            ' total_impressions = SUM(impressions), total_clicks = SUM(clicks)'
        )
        if totals:
            t = totals[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Spend", f"${t.get('total_spend', 0):,.0f}")
            c2.metric("Avg CPA", f"${t.get('avg_cpa', 0):,.2f}")
            c3.metric("Avg ROAS", f"{t.get('avg_roas', 0):,.2f}x")
            c4.metric("Avg CTR", f"{t.get('avg_ctr', 0) * 100:,.2f}%")

            c5, c6, c7, _ = st.columns(4)
            c5.metric("Total Conversions", f"{t.get('total_conversions', 0):,}")
            c6.metric("Total Impressions", f"{t.get('total_impressions', 0):,}")
            c7.metric("Total Clicks", f"{t.get('total_clicks', 0):,}")
    except Exception as e:
        st.error(f"Failed to load KPIs: {e}")

    st.divider()

    # Daily trend chart
    st.subheader("Daily Spend & Conversions Trend")
    try:
        daily = run_esql(
            'FROM channel-metrics'
            ' | STATS daily_spend = SUM(spend), daily_conv = SUM(conversions),'
            ' daily_clicks = SUM(clicks)'
            ' BY date'
            ' | SORT date ASC | LIMIT 60'
        )
        if daily:
            import pandas as pd
            df = pd.DataFrame(daily)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            col_l, col_r = st.columns(2)
            with col_l:
                st.line_chart(df[["daily_spend"]], use_container_width=True)
            with col_r:
                st.line_chart(df[["daily_conv"]], use_container_width=True)
    except Exception as e:
        st.error(f"Failed to load daily trends: {e}")

    # Channel breakdown
    st.subheader("Channel Performance")
    try:
        by_channel = run_esql(
            'FROM channel-metrics'
            ' | STATS total_spend = SUM(spend), avg_cpa = AVG(cpa),'
            ' avg_roas = AVG(roas), total_conv = SUM(conversions)'
            ' BY channel'
            ' | SORT total_spend DESC'
        )
        if by_channel:
            import pandas as pd
            df_ch = pd.DataFrame(by_channel)
            st.dataframe(df_ch, use_container_width=True, hide_index=True)

            col_l2, col_r2 = st.columns(2)
            with col_l2:
                st.bar_chart(df_ch.set_index("channel")[["total_spend"]], use_container_width=True)
            with col_r2:
                st.bar_chart(df_ch.set_index("channel")[["avg_roas"]], use_container_width=True)
    except Exception as e:
        st.error(f"Failed to load channel data: {e}")


# ===== TAB 2: Anomaly Alerts =====
with tab_alerts:
    st.header("Anomaly Alerts")

    if st.button("🔍 Run Anomaly Scan", key="scan_btn"):
        with st.spinner("Scanning all indices for anomalies..."):
            try:
                scan_result = run_anomaly_scan()
                st.session_state["scan_result"] = scan_result
            except Exception as e:
                st.error(f"Scan failed: {e}")

    scan_result = st.session_state.get("scan_result")
    if scan_result:
        total = scan_result["total_alerts"]
        by_sev = scan_result["alerts_by_severity"]
        high_count = len(by_sev.get("high", []))
        med_count = len(by_sev.get("medium", []))

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Alerts", total)
        c2.metric("High Severity", high_count)
        c3.metric("Medium Severity", med_count)

        st.divider()

        for alert in scan_result["alerts"]:
            sev = alert.get("severity", "low")
            icon = "🔴" if sev == "high" else "🟡" if sev == "medium" else "🟢"
            alert_type = alert.get("alert_type", "unknown").replace("_", " ").title()
            campaign_name = alert.get("campaign_name", alert.get("campaign_id", "N/A"))

            with st.expander(f"{icon} {alert_type} — {campaign_name}", expanded=(sev == "high")):
                # Build detail items dynamically
                detail_items = {}
                for key in ["campaign_id", "channel", "metric", "pct_change",
                            "pace_ratio", "fatigue_score", "avg_churn",
                            "competitor", "impression_share", "segment",
                            "latest_date", "asset_id", "headline"]:
                    if key in alert and alert[key]:
                        label = key.replace("_", " ").title()
                        val = alert[key]
                        if isinstance(val, float):
                            if "pct" in key or "ratio" in key or "share" in key or "score" in key or "churn" in key:
                                val = f"{val:.2f}"
                            else:
                                val = f"{val:,.2f}"
                        detail_items[label] = val

                for label, val in detail_items.items():
                    st.write(f"**{label}:** {val}")
    else:
        st.info("Click 'Run Anomaly Scan' to detect issues across all campaigns.")


# ===== TAB 3: Chat with Agent =====
with tab_chat:
    st.header("Chat with CampaignPilot")

    # Initialize chat history
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = None
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = None

    # Display chat history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask about campaign performance, anomalies, or recommendations...")

    if user_input:
        # Show user message
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    kibana_url = os.environ.get("KIBANA_URL", "").strip()
                    kibana_key = os.environ.get("KIBANA_API_KEY", "").strip()

                    if kibana_url and kibana_key:
                        # Agent Builder mode
                        from agent.cli import chat_agent_builder
                        reply, conv_id = chat_agent_builder(
                            user_input,
                            st.session_state.get("conversation_id"),
                        )
                        st.session_state["conversation_id"] = conv_id
                    else:
                        # OpenRouter fallback
                        from agent.loop import run_conversation
                        reply, history = run_conversation(
                            user_input,
                            st.session_state.get("chat_history"),
                        )
                        st.session_state["chat_history"] = history

                    st.write(reply)
                    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
                except Exception as e:
                    err_msg = f"Error: {e}"
                    st.error(err_msg)
                    st.session_state["chat_messages"].append({"role": "assistant", "content": err_msg})


# ===== TAB 4: Action Log =====
with tab_actions:
    st.header("Action Log")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_filter = st.selectbox(
            "Status", ["all", "proposed", "approved", "executed", "rejected"],
            key="action_status_filter",
        )
    with col_f2:
        campaign_filter = st.text_input("Campaign ID", key="action_campaign_filter", placeholder="e.g. CAMP-2026-041")

    try:
        actions = get_actions(
            campaign_id=campaign_filter if campaign_filter else None,
            status=status_filter if status_filter != "all" else None,
            limit=50,
        )
        if actions:
            import pandas as pd
            df_actions = pd.DataFrame(actions)
            # Select display columns
            display_cols = [c for c in [
                "action_id", "campaign_id", "channel", "action_type",
                "status", "timestamp", "description"
            ] if c in df_actions.columns]
            st.dataframe(df_actions[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No actions found matching the current filters.")
    except Exception as e:
        st.error(f"Failed to load action log: {e}")
