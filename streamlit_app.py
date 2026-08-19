"""Interactive Streamlit Web Dashboard connecting strictly via SUPABASE_ANON_KEY."""

import os
import glob
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database.supabase_client import SupabaseDBClient
from src.config_loader import load_team_config
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
        .badge-arch {
            background-color: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-model {
            background-color: rgba(139, 92, 246, 0.2);
            color: #c084fc;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)


COLOR_PALETTE = [
    "#3b82f6",  # Blue
    "#10b981",  # Green
    "#f59e0b",  # Amber
    "#ec4899",  # Pink
    "#8b5cf6",  # Purple
    "#06b6d4",  # Cyan
    "#f97316",  # Orange
]


def _format_model_short(model_str: str) -> str:
    """Extract a clean short name from a model string."""
    if not model_str:
        return "Unknown"
    return model_str.split("/")[-1]


@st.cache_resource
def get_db_client() -> SupabaseDBClient:
    """Initialize read-only Supabase DB client using SUPABASE_ANON_KEY."""
    return SupabaseDBClient(use_anon=True)


def load_all_teams_metadata(db_client: SupabaseDBClient) -> List[Dict[str, Any]]:
    """Load all registered teams, augmenting with YAML metadata where helpful."""
    db_teams = db_client.get_all_teams()
    yaml_files = glob.glob("config/teams/*.yaml")
    yaml_map = {}
    for yf in yaml_files:
        try:
            cfg = load_team_config(yf)
            yaml_map[cfg.team.name] = cfg.team
        except Exception:
            pass

    merged_teams = []
    seen_names = set()

    for t in db_teams:
        name = t.get("name", "")
        seen_names.add(name)
        arch = t.get("architecture") or (yaml_map[name].architecture if name in yaml_map else "sequential")
        model = t.get("model") or (yaml_map[name].model if name in yaml_map else "")
        team_id = str(t.get("id", ""))
        merged_teams.append({
            "id": team_id,
            "name": name,
            "architecture": arch,
            "model": model,
            "model_short": _format_model_short(model),
            "description": t.get("description", "")
        })

    # Add any YAML team not yet in DB
    for name, y_meta in yaml_map.items():
        if name not in seen_names:
            merged_teams.append({
                "id": f"mock-{name.lower().replace(' ', '-')}",
                "name": name,
                "architecture": y_meta.architecture,
                "model": y_meta.model,
                "model_short": _format_model_short(y_meta.model),
                "description": y_meta.description
            })

    return merged_teams


def main():
    st.title("⚡ Tyche — Multi-Agent Stock Investment Platform")
    st.caption("Benchmark and compare AI trading strategies across LLM Models & Multi-Agent Architectures.")

    db_client = get_db_client()
    teams = load_all_teams_metadata(db_client)

    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("📊 Experiment & Filter Controls")

    # Architecture & Model Filters
    all_archs = ["All"] + sorted(list(set(t["architecture"] for t in teams if t["architecture"])))
    selected_arch = st.sidebar.selectbox("Filter Architecture", options=all_archs, index=0)

    all_models = ["All"] + sorted(list(set(t["model_short"] for t in teams if t["model_short"])))
    selected_model_short = st.sidebar.selectbox("Filter Model", options=all_models, index=0)

    # Filter teams based on selectors
    filtered_teams = [
        t for t in teams
        if (selected_arch == "All" or t["architecture"] == selected_arch) and
           (selected_model_short == "All" or t["model_short"] == selected_model_short)
    ]
    if not filtered_teams:
        filtered_teams = teams

    # Team options formatted with model & architecture
    team_display_options = {
        f"{t['name']}  [{t['architecture'].capitalize()} • {t['model_short']}]": t
        for t in filtered_teams
    }

    selected_display_name = st.sidebar.selectbox(
        "Select Primary Agent Team",
        options=list(team_display_options.keys()),
        index=0
    )
    primary_team = team_display_options[selected_display_name]

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

    # --- COLLECT DATA ACROSS ALL FILTERED TEAMS ---
    all_teams_stats = []
    all_teams_snapshots = {}

    for t in filtered_teams:
        t_id = t["id"]
        portfolio = db_client.get_portfolio_by_team_id(t_id) or {}
        p_id = str(portfolio.get("id") or t_id)
        snaps = db_client.get_snapshots(p_id)
        summary = compute_portfolio_summary_metrics(p_id, db_client=db_client)

        all_teams_snapshots[t["name"]] = snaps
        all_teams_stats.append({
            "Team Name": t["name"],
            "Architecture": t["architecture"].capitalize(),
            "Model": t["model"] or "Default",
            "Model Short": t["model_short"],
            "Total Value ($)": summary["total_value"],
            "Cumulative Return (%)": summary["cumulative_return_pct"],
            "Sharpe Ratio": summary["sharpe_ratio"],
            "Max Drawdown (%)": abs(summary["max_drawdown"]) * 100.0,
            "Win Rate (%)": summary["win_rate_pct"],
            "Portfolio ID": p_id,
            "Team ID": t_id
        })

    df_comparison = pd.DataFrame(all_teams_stats)

    # --- PRIMARY TEAM DATA ---
    primary_team_id = primary_team["id"]
    primary_portfolio = db_client.get_portfolio_by_team_id(primary_team_id) or {}
    primary_portfolio_id = str(primary_portfolio.get("id") or primary_team_id)
    primary_summary = compute_portfolio_summary_metrics(primary_portfolio_id, db_client=db_client)
    primary_positions = db_client.get_positions(primary_portfolio_id)
    primary_transactions = db_client.get_transactions(primary_portfolio_id)
    primary_agents = db_client.get_agents_by_team(primary_team_id)

    # --- TOP LEVEL NAVIGATION TABS ---
    top_tab1, top_tab2 = st.tabs([
        "⚔️ Cross-Model & Architecture Comparison",
        f"🎯 Single Team Deep Dive ({primary_team['name']})"
    ])

    # =========================================================
    # TAB 1: MODEL & ARCHITECTURE COMPARISON
    # =========================================================
    with top_tab1:
        st.subheader("⚔️ Strategy Benchmarks by Model & Architecture")
        st.markdown(
            "Compare the trading performance of multi-agent teams across different foundation models "
            "(Qwen, GPT, Gemma, Mistral, etc.) and organizational architectures (Sequential vs Hierarchical)."
        )

        # 1. Comparison Matrix Table
        st.dataframe(
            df_comparison[[
                "Team Name", "Architecture", "Model Short", "Total Value ($)",
                "Cumulative Return (%)", "Sharpe Ratio", "Max Drawdown (%)", "Win Rate (%)"
            ]].style.format({
                "Total Value ($)": "${:,.2f}",
                "Cumulative Return (%)": "{:+.2f}%",
                "Sharpe Ratio": "{:.2f}",
                "Max Drawdown (%)": "{:.2f}%",
                "Win Rate (%)": "{:.1f}%"
            }),
            use_container_width=True
        )

        st.markdown("---")

        # 2. Multi-Team Base 100 Performance Overlay Chart
        st.subheader("📈 Multi-Team Base 100 Overlay vs S&P 500 Benchmark")

        fig_multi = go.Figure()
        has_snap_data = False
        benchmark_plotted = False

        for i, t in enumerate(filtered_teams):
            t_name = t["name"]
            snaps = all_teams_snapshots.get(t_name, [])
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            label = f"{t_name} ({t['architecture'].capitalize()} • {t['model_short']})"

            if snaps:
                has_snap_data = True
                df_s = pd.DataFrame(snaps)
                df_s["snapshot_date"] = pd.to_datetime(df_s["snapshot_date"]).dt.date
                mask = (df_s["snapshot_date"] >= start_date) & (df_s["snapshot_date"] <= end_date)
                df_f = df_s.loc[mask]
                if df_f.empty:
                    df_f = df_s

                fig_multi.add_trace(go.Scatter(
                    x=df_f["snapshot_date"],
                    y=df_f["portfolio_base100"],
                    mode="lines+markers",
                    name=label,
                    line=dict(color=color, width=2.5),
                    marker=dict(size=5)
                ))

                if not benchmark_plotted and "benchmark_base100" in df_f.columns:
                    fig_multi.add_trace(go.Scatter(
                        x=df_f["snapshot_date"],
                        y=df_f["benchmark_base100"],
                        mode="lines",
                        name=f"Benchmark ({benchmark})",
                        line=dict(color="#9ca3af", width=2, dash="dash")
                    ))
                    benchmark_plotted = True

        if not has_snap_data:
            # Baseline placeholder
            dates = [today]
            for i, t in enumerate(filtered_teams):
                color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
                fig_multi.add_trace(go.Scatter(x=dates, y=[100.0], name=t["name"], line=dict(color=color)))
            fig_multi.add_trace(go.Scatter(x=dates, y=[100.0], name=f"Benchmark ({benchmark})", line=dict(color="#9ca3af", dash="dash")))

        fig_multi.update_layout(
            template="plotly_dark",
            xaxis_title="Date",
            yaxis_title="Base 100 Index",
            height=450,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_multi, use_container_width=True)

        st.markdown("---")

        # 3. Grouped Comparative Visualizations (Model & Architecture)
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.subheader("📊 Return (%) by Model & Architecture")
            fig_bar_ret = px.bar(
                df_comparison,
                x="Team Name",
                y="Cumulative Return (%)",
                color="Model Short",
                pattern_shape="Architecture",
                text="Cumulative Return (%)",
                title="Cumulative Return Comparison",
                color_discrete_sequence=COLOR_PALETTE
            )
            fig_bar_ret.update_traces(texttemplate="%{text:.2f}%", textposition="auto")
            fig_bar_ret.update_layout(template="plotly_dark", height=380)
            st.plotly_chart(fig_bar_ret, use_container_width=True)

        with col_c2:
            st.subheader("🎯 Sharpe Ratio by Model & Architecture")
            fig_bar_sr = px.bar(
                df_comparison,
                x="Team Name",
                y="Sharpe Ratio",
                color="Model Short",
                pattern_shape="Architecture",
                text="Sharpe Ratio",
                title="Sharpe Ratio (Annualized)",
                color_discrete_sequence=COLOR_PALETTE
            )
            fig_bar_sr.update_traces(texttemplate="%{text:.2f}", textposition="auto")
            fig_bar_sr.update_layout(template="plotly_dark", height=380)
            st.plotly_chart(fig_bar_sr, use_container_width=True)

        col_c3, col_c4 = st.columns(2)
        with col_c3:
            st.subheader("📉 Max Drawdown (%)")
            fig_bar_dd = px.bar(
                df_comparison,
                x="Team Name",
                y="Max Drawdown (%)",
                color="Architecture",
                text="Max Drawdown (%)",
                title="Max Drawdown (Lower is Better)",
                color_discrete_sequence=["#ef4444", "#f97316"]
            )
            fig_bar_dd.update_traces(texttemplate="%{text:.2f}%", textposition="auto")
            fig_bar_dd.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig_bar_dd, use_container_width=True)

        with col_c4:
            st.subheader("🏆 Win Rate (%)")
            fig_bar_wr = px.bar(
                df_comparison,
                x="Team Name",
                y="Win Rate (%)",
                color="Model Short",
                text="Win Rate (%)",
                title="Win Rate % by Model",
                color_discrete_sequence=COLOR_PALETTE
            )
            fig_bar_wr.update_traces(texttemplate="%{text:.1f}%", textposition="auto")
            fig_bar_wr.update_layout(template="plotly_dark", height=350)
            st.plotly_chart(fig_bar_wr, use_container_width=True)

    # =========================================================
    # TAB 2: SINGLE TEAM DEEP DIVE
    # =========================================================
    with top_tab2:
        # Team header metadata
        st.subheader(f"💼 {primary_team['name']}")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(f"**Architecture:** <span class='badge-arch'>{primary_team['architecture'].capitalize()}</span>", unsafe_allow_html=True)
        with col_m2:
            st.markdown(f"**LLM Model:** <span class='badge-model'>{primary_team['model'] or 'Default'}</span>", unsafe_allow_html=True)
        with col_m3:
            st.markdown(f"**Portfolio ID:** `{primary_portfolio_id[:8]}...`")

        if primary_team.get("description"):
            st.caption(primary_team["description"])

        st.markdown("---")

        # --- KPI CARDS ROW ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric(
                label="Total Portfolio Value",
                value=f"${primary_summary['total_value']:,.2f}",
                delta=f"${primary_summary['total_value'] - primary_summary['initial_cash']:,.2f}"
            )
        with kpi2:
            st.metric(
                label="Cumulative Return",
                value=f"{primary_summary['cumulative_return_pct']:+.2f}%",
                delta=f"{primary_summary['cumulative_return_pct']:+.2f}%"
            )
        with kpi3:
            st.metric(
                label="Sharpe Ratio",
                value=f"{primary_summary['sharpe_ratio']:.2f}"
            )
        with kpi4:
            st.metric(
                label="Max Drawdown",
                value=f"{primary_summary['max_drawdown'] * 100:.2f}%",
                delta=f"-{abs(primary_summary['max_drawdown']) * 100:.2f}%",
                delta_color="inverse"
            )

        st.markdown("---")

        # --- SINGLE TEAM BASE 100 CHART ---
        st.subheader("📈 Performance Index (Base 100 vs Benchmark)")
        single_snaps = all_teams_snapshots.get(primary_team["name"], [])
        if single_snaps:
            df_snap = pd.DataFrame(single_snaps)
            df_snap["snapshot_date"] = pd.to_datetime(df_snap["snapshot_date"]).dt.date
            mask = (df_snap["snapshot_date"] >= start_date) & (df_snap["snapshot_date"] <= end_date)
            df_filtered = df_snap.loc[mask]
            if df_filtered.empty:
                df_filtered = df_snap

            fig_single = go.Figure()
            fig_single.add_trace(go.Scatter(
                x=df_filtered["snapshot_date"],
                y=df_filtered["portfolio_base100"],
                mode="lines+markers",
                name=f"{primary_team['name']} (Base 100)",
                line=dict(color="#3b82f6", width=3)
            ))
            fig_single.add_trace(go.Scatter(
                x=df_filtered["snapshot_date"],
                y=df_filtered["benchmark_base100"],
                mode="lines",
                name=f"Benchmark ({benchmark})",
                line=dict(color="#9ca3af", width=2, dash="dash")
            ))
            fig_single.update_layout(
                template="plotly_dark",
                xaxis_title="Date",
                yaxis_title="Base 100 Value",
                height=400,
                margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_single, use_container_width=True)
        else:
            st.info("No historical daily snapshots logged yet for this team.")

        # --- DETAIL TABS ---
        dtab1, dtab2, dtab3, dtab4 = st.tabs([
            "💼 Active Positions & Balance",
            "📜 Transaction History & Reasoning",
            "🤖 Agent Architecture",
            "📑 Raw Execution Logs"
        ])

        with dtab1:
            st.subheader("Current Holdings")
            if primary_positions:
                df_pos = pd.DataFrame(primary_positions)
                st.dataframe(
                    df_pos[["symbol", "quantity", "avg_buy_price", "current_price", "market_value"]],
                    use_container_width=True
                )
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

        with dtab2:
            st.subheader("Trade Execution History")
            if primary_transactions:
                df_tx = pd.DataFrame(primary_transactions)
                action_filter = st.multiselect(
                    "Filter Action",
                    options=["BUY", "SELL", "HOLD"],
                    default=["BUY", "SELL", "HOLD"],
                    key="single_team_action_filter"
                )
                df_tx_filtered = df_tx[df_tx["action"].isin(action_filter)]
                st.dataframe(
                    df_tx_filtered[["executed_at", "agent_name", "symbol", "action", "quantity", "executed_price", "total_amount", "reasoning"]],
                    use_container_width=True
                )
            else:
                st.write("No transaction logs recorded.")

        with dtab3:
            st.subheader(f"Agent Team Configuration — {primary_team['name']}")
            if primary_agents:
                st.dataframe(pd.DataFrame(primary_agents), use_container_width=True)
            else:
                st.json({
                    "team_name": primary_team["name"],
                    "architecture": primary_team["architecture"],
                    "model": primary_team["model"],
                    "agents": [
                        {"name": "Macro Analyst", "role": "News & Sentiment", "llm_model": primary_team["model"] or "qwen3.7-flash"},
                        {"name": "Technical Analyst", "role": "RSI / SMA / MACD Indicators", "llm_model": primary_team["model"] or "qwen3.7-flash"},
                        {"name": "Portfolio Manager", "role": "Trade Execution & Risk Control", "llm_model": primary_team["model"] or "qwen3.7-flash"}
                    ]
                })

        with dtab4:
            st.subheader("Raw Chain-of-Thought System Logs")
            log_files = glob.glob("./logs/*.log")
            if log_files:
                selected_log = st.selectbox("Select Log File", options=log_files, key="single_team_log_select")
                if selected_log and os.path.exists(selected_log):
                    with open(selected_log, "r", encoding="utf-8") as f:
                        log_content = f.read()
                    st.code(log_content[-5000:], language="text")
            else:
                st.info("No system execution log files found in `./logs/` directory.")


if __name__ == "__main__":
    main()

