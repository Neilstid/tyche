"""Interactive Streamlit Web Dashboard connecting strictly via SUPABASE_ANON_KEY."""

import os
import glob
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database.supabase_client import SupabaseDBClient
from src.execution.metrics import compute_portfolio_summary_metrics

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Tyche — Multi-Agent Trading Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
    <style>
        .main {
            background-color: #0b0f19;
        }
        .metric-card {
            background-color: #111827;
            border: 1px solid #1f293d;
            border-radius: 10px;
            padding: 16px;
            text-align: center;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 48px;
            background-color: #111827;
            border-radius: 8px;
            color: #9ca3af;
        }
        .stTabs [aria-selected="true"] {
            background-color: #2563eb !important;
            color: #ffffff !important;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_client() -> SupabaseDBClient:
    """Initialize read-only Supabase DB client using SUPABASE_ANON_KEY."""
    return SupabaseDBClient(use_anon=True)


def main():
    st.title("⚡ Tyche — Multi-Agent Stock Investment Platform")
    st.caption("Real-time AI paper trading analytics, multi-agent evaluation, and performance monitoring.")

    db_client = get_db_client()

    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("📊 Filter Controls")

    # Team Selector
    db_teams = db_client.get_all_teams()
    team_names = [t["name"] for t in db_teams] if db_teams else ["Sequential Team Alpha", "Hierarchical Team Beta"]
    team_name = st.sidebar.selectbox(
        "Select Agent Team",
        options=team_names,
        index=0
    )

    # Date Range Picker
    today = datetime.now(timezone.utc).date()
    start_default = today - timedelta(days=30)
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(start_default, today),
        max_value=today
    )

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = start_default, today

    # Benchmark Symbol Selector
    benchmark = st.sidebar.selectbox(
        "Benchmark Symbol",
        options=["^GSPC (S&P 500)", "^IXIC (Nasdaq 100)", "^DJI (Dow Jones)"],
        index=0
    ).split(" ")[0]

    # Resolve Team & Portfolio IDs
    selected_team = next((t for t in db_teams if t.get("name") == team_name), None) if db_teams else None
    if not selected_team:
        selected_team = db_client.get_team_by_name(team_name)

    if selected_team and "id" in selected_team:
        team_id = str(selected_team["id"])
        portfolio = db_client.get_portfolio_by_team_id(team_id) or {}
        portfolio_id = str(portfolio.get("id") or team_id)
        agents = db_client.get_agents_by_team(team_id)
    else:
        team_id = "00000000-0000-0000-0000-000000000001"
        portfolio_id = "00000000-0000-0000-0000-000000000003"
        agents = []

    # Fetch Data from Supabase
    snapshots = db_client.get_snapshots(portfolio_id)
    positions = db_client.get_positions(portfolio_id)
    transactions = db_client.get_transactions(portfolio_id)
    summary = compute_portfolio_summary_metrics(portfolio_id, db_client=db_client)

    # --- KPI CARDS ROW ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Total Portfolio Value",
            value=f"${summary['total_value']:,.2f}",
            delta=f"${summary['total_value'] - summary['initial_cash']:,.2f}"
        )

    with col2:
        st.metric(
            label="Cumulative Return",
            value=f"{summary['cumulative_return_pct']:+.2f}%",
            delta=f"{summary['cumulative_return_pct']:+.2f}%"
        )

    with col3:
        st.metric(
            label="Sharpe Ratio (Annualized)",
            value=f"{summary['sharpe_ratio']:.2f}"
        )

    with col4:
        st.metric(
            label="Max Drawdown",
            value=f"{summary['max_drawdown'] * 100:.2f}%",
            delta=f"-{abs(summary['max_drawdown']) * 100:.2f}%",
            delta_color="inverse"
        )

    st.markdown("---")

    # --- BASE 100 TIME-SERIES CHART ---
    st.subheader("📈 Performance Index (Base 100 vs Benchmark)")

    if snapshots:
        df_snap = pd.DataFrame(snapshots)
        df_snap["snapshot_date"] = pd.to_datetime(df_snap["snapshot_date"]).dt.date
        mask = (df_snap["snapshot_date"] >= start_date) & (df_snap["snapshot_date"] <= end_date)
        df_filtered = df_snap.loc[mask]

        if df_filtered.empty:
            df_filtered = df_snap

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_filtered["snapshot_date"],
            y=df_filtered["portfolio_base100"],
            mode="lines+markers",
            name=f"{team_name} (Base 100)",
            line=dict(color="#3b82f6", width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df_filtered["snapshot_date"],
            y=df_filtered["benchmark_base100"],
            mode="lines",
            name=f"Benchmark ({benchmark})",
            line=dict(color="#9ca3af", width=2, dash="dash")
        ))
        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Date",
            yaxis_title="Base 100 Value",
            height=400,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No historical daily snapshots logged yet. Run a backtest or daily trading cycle to generate snapshot data.")

    # --- TABS SECTION ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "💼 Active Positions & Balance",
        "📜 Transaction History & Reasoning",
        "🤖 Agent Architecture",
        "📑 Raw Execution Logs"
    ])

    # Tab 1: Current Positions & Allocation
    with tab1:
        st.subheader("Current Holdings")
        if positions:
            df_pos = pd.DataFrame(positions)
            st.dataframe(
                df_pos[["symbol", "quantity", "avg_buy_price", "current_price", "market_value"]],
                use_container_width=True
            )

            # Asset Allocation Pie Chart
            fig_pie = px.pie(
                df_pos,
                names="symbol",
                values="market_value",
                title="Portfolio Allocation by Ticker",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Plotly
            )
            fig_pie.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("No open stock positions in portfolio.")

    # Tab 2: Transaction History
    with tab2:
        st.subheader("Trade Execution History")
        if transactions:
            df_tx = pd.DataFrame(transactions)
            action_filter = st.multiselect(
                "Filter Action",
                options=["BUY", "SELL", "HOLD"],
                default=["BUY", "SELL", "HOLD"]
            )
            df_tx_filtered = df_tx[df_tx["action"].isin(action_filter)]
            st.dataframe(
                df_tx_filtered[["executed_at", "agent_name", "symbol", "action", "quantity", "executed_price", "total_amount", "reasoning"]],
                use_container_width=True
            )
        else:
            st.write("No transaction logs recorded.")

    # Tab 3: Agent Architecture
    with tab3:
        st.subheader(f"Agent Team Configuration — {team_name}")
        if agents:
            st.dataframe(pd.DataFrame(agents), use_container_width=True)
        else:
            st.json({
                "team_name": team_name,
                "architecture": "sequential",
                "agents": [
                    {"name": "Macro Analyst", "role": "News & Sentiment", "llm_model": "openrouter/qwen/qwen3.7-flash"},
                    {"name": "Technical Analyst", "role": "RSI / SMA / MACD Indicators", "llm_model": "openrouter/qwen/qwen3.7-flash"},
                    {"name": "Portfolio Manager", "role": "Trade Execution & Risk Control", "llm_model": "openrouter/qwen/qwen3.7-flash"}
                ]
            })

    # Tab 4: Raw Execution Logs
    with tab4:
        st.subheader("Raw Chain-of-Thought System Logs")
        log_files = glob.glob("./logs/*.log")
        if log_files:
            selected_log = st.selectbox("Select Log File", options=log_files)
            if selected_log and os.path.exists(selected_log):
                with open(selected_log, "r", encoding="utf-8") as f:
                    log_content = f.read()
                st.code(log_content[-5000:], language="text")
        else:
            st.info("No system execution log files found in `./logs/` directory.")


if __name__ == "__main__":
    main()
