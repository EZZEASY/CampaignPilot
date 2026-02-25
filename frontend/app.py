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

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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

# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* KPI card styling */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #f8faff 0%, #eef2ff 100%);
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}
div[data-testid="stMetric"] label {
    color: #64748b !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #1a1a2e !important;
}

/* Alert severity colors */
.alert-high {
    border-left: 4px solid #e53e3e;
    padding-left: 12px;
    margin-bottom: 8px;
}
.alert-medium {
    border-left: 4px solid #ecc94b;
    padding-left: 12px;
    margin-bottom: 8px;
}
.alert-low {
    border-left: 4px solid #48bb78;
    padding-left: 12px;
    margin-bottom: 8px;
}

/* Tab styling */
button[data-baseweb="tab"] {
    font-size: 1rem !important;
    font-weight: 600 !important;
}

/* Chat message styling */
div[data-testid="stChatMessage"] {
    border-radius: 12px;
    margin-bottom: 4px;
}

/* Chat container: scrollable message area */
div[data-testid="stChatMessageContainer"] {
    max-height: 60vh;
    overflow-y: auto;
}

/* Chat input fixed at bottom */
div[data-testid="stChatInput"] {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    padding: 12px 2rem;
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
}

/* Bottom padding so messages don't hide behind fixed input */
section[data-testid="stChatFlow"] {
    padding-bottom: 80px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Plotly shared config
# ---------------------------------------------------------------------------

PLOTLY_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#1a1a2e"),
    margin=dict(l=40, r=20, t=40, b=40),
    xaxis=dict(gridcolor="rgba(0,0,0,0.08)"),
    yaxis=dict(gridcolor="rgba(0,0,0,0.08)"),
)

CHANNEL_COLORS = {
    "google": "#4285F4",
    "meta": "#1877F2",
    "tiktok": "#25F4EE",
    "email": "#48BB78",
    "linkedin": "#0A66C2",
}

# ---------------------------------------------------------------------------

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

    # KPI cards with delta trends
    try:
        totals = run_esql(
            'FROM channel-metrics'
            ' | STATS total_spend = SUM(spend), total_conversions = SUM(conversions),'
            ' avg_cpa = AVG(cpa), avg_roas = AVG(roas), avg_ctr = AVG(ctr),'
            ' total_impressions = SUM(impressions), total_clicks = SUM(clicks)'
        )

        # Period comparison for delta: first half vs second half
        period_early = run_esql(
            'FROM channel-metrics'
            ' | WHERE date < "2026-02-13"'
            ' | STATS spend = SUM(spend), conversions = SUM(conversions),'
            ' cpa = AVG(cpa), roas = AVG(roas), ctr = AVG(ctr),'
            ' impressions = SUM(impressions), clicks = SUM(clicks)'
        )
        period_late = run_esql(
            'FROM channel-metrics'
            ' | WHERE date >= "2026-02-13"'
            ' | STATS spend = SUM(spend), conversions = SUM(conversions),'
            ' cpa = AVG(cpa), roas = AVG(roas), ctr = AVG(ctr),'
            ' impressions = SUM(impressions), clicks = SUM(clicks)'
        )

        def pct_delta(early_val, late_val):
            """Return percentage change string or None."""
            if not early_val or not late_val or early_val == 0:
                return None
            change = ((late_val - early_val) / abs(early_val)) * 100
            return f"{change:+.1f}%"

        e = period_early[0] if period_early else {}
        l = period_late[0] if period_late else {}

        if totals:
            t = totals[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Total Spend",
                f"${t.get('total_spend', 0):,.0f}",
                delta=pct_delta(e.get('spend'), l.get('spend')),
            )
            c2.metric(
                "Avg CPA",
                f"${t.get('avg_cpa', 0):,.2f}",
                delta=pct_delta(e.get('cpa'), l.get('cpa')),
                delta_color="inverse",
            )
            c3.metric(
                "Avg ROAS",
                f"{t.get('avg_roas', 0):,.2f}x",
                delta=pct_delta(e.get('roas'), l.get('roas')),
            )
            c4.metric(
                "Avg CTR",
                f"{t.get('avg_ctr', 0) * 100:,.2f}%",
                delta=pct_delta(e.get('ctr'), l.get('ctr')),
            )

            c5, c6, c7, _ = st.columns(4)
            c5.metric(
                "Total Conversions",
                f"{t.get('total_conversions', 0):,}",
                delta=pct_delta(e.get('conversions'), l.get('conversions')),
            )
            c6.metric(
                "Total Impressions",
                f"{t.get('total_impressions', 0):,}",
                delta=pct_delta(e.get('impressions'), l.get('impressions')),
            )
            c7.metric(
                "Total Clicks",
                f"{t.get('total_clicks', 0):,}",
                delta=pct_delta(e.get('clicks'), l.get('clicks')),
            )
    except Exception as exc:
        st.error(f"Failed to load KPIs: {exc}")

    st.divider()

    # Daily trend chart — Plotly
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
            df = pd.DataFrame(daily)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            col_l, col_r = st.columns(2)
            with col_l:
                fig_spend = go.Figure()
                fig_spend.add_trace(go.Scatter(
                    x=df["date"], y=df["daily_spend"],
                    mode="lines+markers",
                    fill="tozeroy",
                    line=dict(color="#4285F4", width=2),
                    marker=dict(size=4),
                    name="Daily Spend",
                ))
                fig_spend.update_layout(
                    title="Daily Spend ($)",
                    **PLOTLY_LAYOUT,
                )
                st.plotly_chart(fig_spend, use_container_width=True)

            with col_r:
                fig_conv = go.Figure()
                fig_conv.add_trace(go.Scatter(
                    x=df["date"], y=df["daily_conv"],
                    mode="lines+markers",
                    fill="tozeroy",
                    line=dict(color="#48BB78", width=2),
                    marker=dict(size=4),
                    name="Daily Conversions",
                ))
                fig_conv.update_layout(
                    title="Daily Conversions",
                    **PLOTLY_LAYOUT,
                )
                st.plotly_chart(fig_conv, use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to load daily trends: {exc}")

    # Channel breakdown — Plotly
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
            df_ch = pd.DataFrame(by_channel)

            # Formatted data table
            df_display = df_ch.copy()
            df_display["total_spend"] = df_display["total_spend"].apply(lambda v: f"${v:,.0f}")
            df_display["avg_cpa"] = df_display["avg_cpa"].apply(lambda v: f"${v:,.2f}")
            df_display["avg_roas"] = df_display["avg_roas"].apply(lambda v: f"{v:.2f}x")
            df_display["total_conv"] = df_display["total_conv"].apply(lambda v: f"{v:,.0f}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            colors = [CHANNEL_COLORS.get(ch.lower(), "#8884d8") for ch in df_ch["channel"]]

            col_l2, col_r2 = st.columns(2)
            with col_l2:
                fig_spend_ch = go.Figure()
                fig_spend_ch.add_trace(go.Bar(
                    x=df_ch["channel"],
                    y=df_ch["total_spend"],
                    marker_color=colors,
                    text=df_ch["total_spend"].apply(lambda v: f"${v:,.0f}"),
                    textposition="outside",
                ))
                fig_spend_ch.update_layout(
                    title="Spend by Channel",
                    **PLOTLY_LAYOUT,
                )
                st.plotly_chart(fig_spend_ch, use_container_width=True)

            with col_r2:
                fig_roas_ch = go.Figure()
                fig_roas_ch.add_trace(go.Bar(
                    x=df_ch["channel"],
                    y=df_ch["avg_roas"],
                    marker_color=colors,
                    text=df_ch["avg_roas"].apply(lambda v: f"{v:.2f}x"),
                    textposition="outside",
                ))
                fig_roas_ch.update_layout(
                    title="Avg ROAS by Channel",
                    **PLOTLY_LAYOUT,
                )
                st.plotly_chart(fig_roas_ch, use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to load channel data: {exc}")


# ===== TAB 2: Anomaly Alerts =====
with tab_alerts:
    st.header("Anomaly Alerts")

    if st.button("🔍 Run Anomaly Scan", key="scan_btn"):
        with st.spinner("Scanning all indices for anomalies..."):
            try:
                scan_result = run_anomaly_scan()
                st.session_state["scan_result"] = scan_result
            except Exception as exc:
                st.error(f"Scan failed: {exc}")

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

                # Two-column detail layout with color bar
                css_class = f"alert-{sev}"
                left_items = list(detail_items.items())[:len(detail_items) // 2 + 1]
                right_items = list(detail_items.items())[len(detail_items) // 2 + 1:]

                st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                dl, dr = st.columns(2)
                with dl:
                    for label, val in left_items:
                        st.markdown(f"**{label}:** {val}")
                with dr:
                    for label, val in right_items:
                        st.markdown(f"**{label}:** {val}")
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Click 'Run Anomaly Scan' to detect issues across all campaigns.")


# ===== TAB 3: Chat with Agent =====
with tab_chat:
    st.header("Chat with CampaignPilot")

    # Detect backend mode
    kibana_url = os.environ.get("KIBANA_URL", "").strip()
    kibana_key = os.environ.get("KIBANA_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    has_agent_builder = bool(kibana_url and kibana_key)
    has_openrouter = bool(openrouter_key)

    if has_agent_builder:
        st.caption("Mode: Agent Builder (Kibana)")
    elif has_openrouter:
        st.caption("Mode: OpenRouter")
    else:
        st.warning(
            "No chat backend configured. Set **KIBANA_URL + KIBANA_API_KEY** "
            "or **OPENROUTER_API_KEY** in your `.env` file."
        )

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
            st.markdown(msg["content"])

    # Chat input — disabled when no backend
    user_input = st.chat_input(
        "Ask about campaign performance, anomalies, or recommendations...",
        disabled=not (has_agent_builder or has_openrouter),
    )

    if user_input:
        # Append user message and rerun to display it via history loop
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        st.session_state["_pending_input"] = user_input
        st.rerun()

    # Process pending input after rerun
    if st.session_state.get("_pending_input"):
        pending = st.session_state.pop("_pending_input")
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if has_agent_builder:
                        from agent.cli import chat_agent_builder
                        reply, conv_id = chat_agent_builder(
                            pending,
                            st.session_state.get("conversation_id"),
                        )
                        st.session_state["conversation_id"] = conv_id
                    else:
                        from agent.loop import run_conversation
                        reply, history = run_conversation(
                            pending,
                            st.session_state.get("chat_history"),
                        )
                        st.session_state["chat_history"] = history

                    # Clean literal \n and dict repr before displaying
                    if isinstance(reply, dict):
                        reply = reply.get("message", reply.get("content", str(reply)))
                    reply = str(reply).replace("\\n", "\n")

                    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
                except Exception as exc:
                    reply = f"Error: {exc}"
                    st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
        st.rerun()


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
            df_actions = pd.DataFrame(actions)
            # Select display columns
            display_cols = [c for c in [
                "action_id", "campaign_id", "channel", "action_type",
                "status", "timestamp", "description"
            ] if c in df_actions.columns]

            # Format timestamp
            if "timestamp" in df_actions.columns:
                df_actions["timestamp"] = pd.to_datetime(df_actions["timestamp"], errors="coerce")
                df_actions["timestamp"] = df_actions["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

            st.dataframe(
                df_actions[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "action_id": st.column_config.TextColumn("Action ID", width="small"),
                    "campaign_id": st.column_config.TextColumn("Campaign", width="small"),
                    "channel": st.column_config.TextColumn("Channel", width="small"),
                    "action_type": st.column_config.TextColumn("Type", width="small"),
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                    "description": st.column_config.TextColumn("Description", width="large"),
                },
            )
        else:
            st.info("No actions found matching the current filters.")
    except Exception as exc:
        st.error(f"Failed to load action log: {exc}")
