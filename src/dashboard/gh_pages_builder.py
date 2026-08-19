"""Static GitHub Pages HTML Builder compiling Jinja2 templates and Plotly interactive figures."""

from typing import Optional, List, Dict, Any
import os
import glob
import logging
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader

from src.database.supabase_client import SupabaseDBClient
from src.config_loader import load_team_config
from src.execution.metrics import compute_portfolio_summary_metrics

logger = logging.getLogger(__name__)

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
        return "Unknown Model"
    return model_str.split("/")[-1]


def build_plotly_multi_team_base100_chart(teams_data: List[Dict[str, Any]]) -> str:
    """Build interactive Plotly line chart comparing multiple teams Base 100 vs Benchmark."""
    fig = go.Figure()

    has_data = False
    benchmark_drawn = False

    for i, t in enumerate(teams_data):
        snapshots = t.get("snapshots", [])
        team_name = t.get("team_name", f"Team {i+1}")
        arch = t.get("architecture", "")
        model_short = _format_model_short(t.get("model", ""))
        label = f"{team_name} ({arch.capitalize()} • {model_short})"
        color = COLOR_PALETTE[i % len(COLOR_PALETTE)]

        if snapshots:
            has_data = True
            df = pd.DataFrame(snapshots)
            df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
            df = df.sort_values("snapshot_date")

            fig.add_trace(go.Scatter(
                x=df["snapshot_date"],
                y=df["portfolio_base100"],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=3),
                marker=dict(size=5)
            ))

            if not benchmark_drawn and "benchmark_base100" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["snapshot_date"],
                    y=df["benchmark_base100"],
                    mode="lines",
                    name="S&P 500 (^GSPC Benchmark)",
                    line=dict(color="#9ca3af", width=2, dash="dash")
                ))
                benchmark_drawn = True

    if not has_data:
        # Dummy baseline data if no snapshots present yet
        dates = [datetime.now(timezone.utc).strftime("%Y-%m-%d")]
        for i, t in enumerate(teams_data or [{"team_name": "Sequential Team Alpha", "architecture": "sequential", "model": "qwen3.7-flash"}]):
            color = COLOR_PALETTE[i % len(COLOR_PALETTE)]
            name = t.get("team_name", f"Team {i+1}")
            fig.add_trace(go.Scatter(x=dates, y=[100.0], name=name, line=dict(color=color)))
        fig.add_trace(go.Scatter(x=dates, y=[100.0], name="S&P 500 Benchmark", line=dict(color="#9ca3af", dash="dash")))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=30, b=40),
        xaxis=dict(gridcolor="#1f293d", title="Date"),
        yaxis=dict(gridcolor="#1f293d", title="Base 100 Index"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(family="Inter, sans-serif")
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_plotly_returns_comparison_chart(teams_summary: List[Dict[str, Any]]) -> str:
    """Build interactive Plotly Bar chart comparing Cumulative Return % across teams & models."""
    fig = go.Figure()
    labels = [f"{t.get('team_name')} ({_format_model_short(t.get('model', ''))})" for t in teams_summary]
    returns = [t.get("cumulative_return_pct", 0.0) for t in teams_summary]
    colors = [COLOR_PALETTE[i % len(COLOR_PALETTE)] for i in range(len(teams_summary))]

    fig.add_trace(go.Bar(
        x=labels,
        y=returns,
        marker_color=colors,
        text=[f"{r:+.2f}%" for r in returns],
        textposition="auto"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=40),
        yaxis=dict(gridcolor="#1f293d", title="Cumulative Return %"),
        font=dict(family="Inter, sans-serif")
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_plotly_win_rate_chart(teams_summary: List[Dict[str, Any]]) -> str:
    """Build interactive Plotly Bar chart comparing Win Rate % across teams."""
    fig = go.Figure()
    labels = [f"{t.get('team_name')} ({_format_model_short(t.get('model', ''))})" for t in teams_summary]
    win_rates = [t.get("win_rate_pct", 0.0) for t in teams_summary]

    fig.add_trace(go.Bar(
        x=labels,
        y=win_rates,
        marker_color="#10b981",
        text=[f"{wr:.1f}%" for wr in win_rates],
        textposition="auto"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=40),
        yaxis=dict(gridcolor="#1f293d", range=[0, 100], title="Win Rate %"),
        font=dict(family="Inter, sans-serif")
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_plotly_drawdown_chart(teams_summary: List[Dict[str, Any]]) -> str:
    """Build interactive Plotly Bar chart comparing Max Drawdown % across teams."""
    fig = go.Figure()
    labels = [f"{t.get('team_name')} ({_format_model_short(t.get('model', ''))})" for t in teams_summary]
    drawdowns = [abs(t.get("max_drawdown", 0.0)) * 100.0 for t in teams_summary]

    fig.add_trace(go.Bar(
        x=labels,
        y=drawdowns,
        marker_color="#ef4444",
        text=[f"{dd:.2f}%" for dd in drawdowns],
        textposition="auto"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=40),
        yaxis=dict(gridcolor="#1f293d", title="Max Drawdown %"),
        font=dict(family="Inter, sans-serif")
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_github_pages(output_dir: str = "./docs", db_client: Optional[SupabaseDBClient] = None) -> str:
    """
    Query Supabase database, render Jinja2 HTML template, and save static site files to ./docs.
    
    :param output_dir: Directory where static site HTML and assets will be created.
    :param db_client: Optional SupabaseDBClient instance.
    :return: Path to generated index.html file.
    """
    logger.info("Initializing GitHub Pages compilation...")
    os.makedirs(output_dir, exist_ok=True)

    client = db_client or SupabaseDBClient()
    
    # 1. Fetch registered teams from DB or YAML configurations fallback
    db_teams = client.get_all_teams()
    yaml_files = glob.glob("config/teams/*.yaml")
    
    # Map YAML configs by team name to get models if not in DB
    yaml_team_map = {}
    for yf in yaml_files:
        try:
            t_cfg = load_team_config(yf)
            yaml_team_map[t_cfg.team.name] = t_cfg.team
        except Exception as e:
            logger.warning(f"Error loading team config {yf}: {e}")

    # Build comprehensive team list
    all_teams_data = []
    all_teams_summary = []
    primary_positions = []
    primary_transactions = []
    primary_agents = []
    primary_summary = None

    for db_t in db_teams:
        team_name = db_t.get("name", "Unknown Team")
        team_id = str(db_t.get("id", ""))
        architecture = db_t.get("architecture") or (yaml_team_map[team_name].architecture if team_name in yaml_team_map else "sequential")
        model = db_t.get("model") or (yaml_team_map[team_name].model if team_name in yaml_team_map else "")
        
        portfolio = (client.get_portfolio_by_team_id(team_id) if team_id else None) or {}
        portfolio_id = str(portfolio.get("id") or team_id or "00000000-0000-0000-0000-000000000003")
        
        snapshots = client.get_snapshots(portfolio_id) if portfolio_id else []
        positions = client.get_positions(portfolio_id) if portfolio_id else []
        transactions = client.get_transactions(portfolio_id) if portfolio_id else []
        agents = client.get_agents_by_team(team_id) if team_id else []
        
        summary = compute_portfolio_summary_metrics(portfolio_id, db_client=client) if portfolio_id else {
            "total_value": 10000.0,
            "initial_cash": 10000.0,
            "cumulative_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate_pct": 0.0
        }

        team_item = {
            "team_id": team_id,
            "team_name": team_name,
            "architecture": architecture,
            "model": model,
            "model_short": _format_model_short(model),
            "portfolio_id": portfolio_id,
            "snapshots": snapshots,
            "positions": positions,
            "transactions": transactions,
            "agents": agents,
            "summary": summary,
            "total_value": summary.get("total_value", 10000.0),
            "cumulative_return_pct": summary.get("cumulative_return_pct", 0.0),
            "sharpe_ratio": summary.get("sharpe_ratio", 0.0),
            "max_drawdown": summary.get("max_drawdown", 0.0),
            "win_rate_pct": summary.get("win_rate_pct", 0.0)
        }
        all_teams_data.append(team_item)
        all_teams_summary.append(team_item)

        if not primary_summary:
            primary_summary = summary
            primary_positions = positions
            primary_transactions = transactions
            primary_agents = agents

    if not primary_summary:
        primary_summary = {
            "total_value": 10000.0,
            "initial_cash": 10000.0,
            "cumulative_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate_pct": 0.0
        }

    # Generate Plotly charts HTML
    line_chart_html = build_plotly_multi_team_base100_chart(all_teams_data)
    returns_chart_html = build_plotly_returns_comparison_chart(all_teams_summary)
    win_rate_chart_html = build_plotly_win_rate_chart(all_teams_summary)
    drawdown_chart_html = build_plotly_drawdown_chart(all_teams_summary)

    # Render Jinja2 template
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("index.html.j2")

    last_updated_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    rendered_html = template.render(
        last_updated=last_updated_str,
        summary=primary_summary,
        all_teams=all_teams_summary,
        positions=primary_positions,
        transactions=primary_transactions,
        agents=primary_agents,
        line_chart_html=line_chart_html,
        returns_chart_html=returns_chart_html,
        win_rate_chart_html=win_rate_chart_html,
        drawdown_chart_html=drawdown_chart_html
    )

    output_file = os.path.join(output_dir, "index.html")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    logger.info(f"✅ Successfully compiled static dashboard to: {output_file}")
    return output_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_github_pages()

