"""Static GitHub Pages HTML Builder compiling Jinja2 templates and Plotly interactive figures."""

from typing import Optional, List, Dict, Any
import os
import logging
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader

from src.database.supabase_client import SupabaseDBClient
from src.execution.metrics import compute_portfolio_summary_metrics

logger = logging.getLogger(__name__)


def build_plotly_base100_chart(snapshots: list) -> str:
    """Build interactive Plotly line chart comparing Portfolio Base 100 vs Benchmark Base 100."""
    fig = go.Figure()

    if snapshots:
        df = pd.DataFrame(snapshots)
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
        df = df.sort_values("snapshot_date")

        fig.add_trace(go.Scatter(
            x=df["snapshot_date"],
            y=df["portfolio_base100"],
            mode="lines+markers",
            name="Portfolio (Base 100)",
            line=dict(color="#3b82f6", width=3),
            marker=dict(size=6)
        ))

        fig.add_trace(go.Scatter(
            x=df["snapshot_date"],
            y=df["benchmark_base100"],
            mode="lines",
            name="S&P 500 (^GSPC Base 100)",
            line=dict(color="#9ca3af", width=2, dash="dash")
        ))
    else:
        # Dummy baseline data if no snapshots present yet
        dates = [datetime.now(timezone.utc).strftime("%Y-%m-%d")]
        fig.add_trace(go.Scatter(x=dates, y=[100.0], name="Portfolio (Base 100)", line=dict(color="#3b82f6")))
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


def build_plotly_win_rate_chart(teams_summary: list) -> str:
    """Build interactive Plotly Bar chart comparing Win Rate % across teams."""
    fig = go.Figure()
    team_names = [t.get("team_name", "Team Alpha") for t in teams_summary]
    win_rates = [t.get("win_rate_pct", 0.0) for t in teams_summary]

    fig.add_trace(go.Bar(
        x=team_names,
        y=win_rates,
        marker_color="#10b981",
        text=[f"{wr:.1f}%" for wr in win_rates],
        textposition="auto"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=30),
        yaxis=dict(gridcolor="#1f293d", range=[0, 100], title="Win Rate %"),
        font=dict(family="Inter, sans-serif")
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_plotly_drawdown_chart(teams_summary: list) -> str:
    """Build interactive Plotly Bar chart comparing Max Drawdown % across teams."""
    fig = go.Figure()
    team_names = [t.get("team_name", "Team Alpha") for t in teams_summary]
    drawdowns = [abs(t.get("max_drawdown", 0.0)) * 100.0 for t in teams_summary]

    fig.add_trace(go.Bar(
        x=team_names,
        y=drawdowns,
        marker_color="#ef4444",
        text=[f"{dd:.2f}%" for dd in drawdowns],
        textposition="auto"
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=30, t=20, b=30),
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
    team = client.get_team_by_name("Sequential Team Alpha")
    if team and "id" in team:
        team_id = str(team["id"])
        portfolio = client.get_portfolio_by_team_id(team_id) or {}
        portfolio_id = str(portfolio.get("id") or team_id)
        agents = client.get_agents_by_team(team_id)
    else:
        team_id = "00000000-0000-0000-0000-000000000001"
        portfolio_id = "00000000-0000-0000-0000-000000000003"
        agents = []

    # Fetch DB data
    snapshots = client.get_snapshots(portfolio_id)
    positions = client.get_positions(portfolio_id)
    transactions = client.get_transactions(portfolio_id)

    # Compute Summary Metrics
    summary = compute_portfolio_summary_metrics(portfolio_id, db_client=client)
    teams_summary = [{"team_name": "Sequential Team Alpha", "win_rate_pct": summary["win_rate_pct"], "max_drawdown": summary["max_drawdown"]}]

    # Generate Plotly charts HTML
    line_chart_html = build_plotly_base100_chart(snapshots)
    win_rate_chart_html = build_plotly_win_rate_chart(teams_summary)
    drawdown_chart_html = build_plotly_drawdown_chart(teams_summary)

    # Render Jinja2 template
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("index.html.j2")

    last_updated_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    rendered_html = template.render(
        last_updated=last_updated_str,
        summary=summary,
        positions=positions,
        transactions=transactions,
        agents=agents,
        line_chart_html=line_chart_html,
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
