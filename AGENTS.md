# AGENTS.md — Multi-Agent Stock Investment & Paper Trading Platform

This document serves as the master specification, architecture blueprint, database schema design, and operational instruction manual for AI coding agents (Cursor, Windsurf, Claude Code, Aider, etc.).

---

## 1. System Overview & Architecture

The platform is an experimental multi-agent environment designed to simulate, backtest, and compare AI-driven stock trading strategies. Agents and agent teams (built with **CrewAI**) analyze market news, macroeconomic trends, and technical indicators to make daily or weekly paper-trading investment decisions.

### System Architecture Diagram

```mermaid
flowchart TB
    subgraph Execution_Layer [Orchestration & Trigger]
        GHA[GitHub Actions Cron / Scheduled Run]
        CLI[Local Backtesting & Execution CLI]
    end

    subgraph Data_Layer [Data Ingestion & Fallback]
        YF[yfinance API - Prices & Technicals]
        NZ[Noozra API - Global News]
        NewsFB[Fallback: yfinance Ticker News / Neutral Sentiment]
    end

    subgraph Core_Engine [CrewAI Multi-Agent Engine]
        ConfigLoader[YAML Config Loader]
        CrewSeq[Sequential Crew Architecture]
        CrewHier[Hierarchical Crew Architecture]
        PydanticParser[Pydantic JSON Validator + 1x Auto-Correction]
        TradingEngine[Paper Trading & Portfolio Execution]
    end

    subgraph Storage_Layer [Dual Storage Model]
        Supa[(Supabase PostgreSQL - Public RLS)]
        LocalLogs[Local System Logs - Raw Chain-of-Thought]
    end

    subgraph UI_Layer [Dual Presentation Layer]
        JinjaBuilder[gh_pages_builder.py Jinja2 + Plotly HTML]
        GHPages[GitHub Pages Site /docs]
        StreamlitApp[Streamlit App Interactive Web UI]
    end

    GHA & CLI --> ConfigLoader
    ConfigLoader --> Data_Layer
    NZ -- Failure / No Data --> NewsFB
    Data_Layer --> CrewSeq & CrewHier
    CrewSeq & CrewHier --> PydanticParser
    PydanticParser -- Valid JSON --> TradingEngine
    PydanticParser -- 2x Failures --> |Force HOLD Action| TradingEngine
    TradingEngine --> Supa
    TradingEngine --> LocalLogs
    Supa --> JinjaBuilder --> GHPages
    Supa --> StreamlitApp

```

---

## 2. Directory Structure

```
.
├── .github/
│   └── workflows/
│       ├── daily_trading.yml          # Automated paper trading & DB update
│       └── publish_gh_pages.yml       # HTML/Markdown generation & Pages deploy
├── config/
│   ├── teams/
│   │   ├── sequential_team_alpha.yaml # Sequential Crew definition
│   │   └── hierarchical_team_beta.yaml# Hierarchical Manager Crew definition
│   └── default_settings.yaml          # Market list, risk limits, defaults
├── prompts/
│   ├── macro_analyst.txt              # News & market sentiment prompt
│   ├── technical_analyst.txt          # Technical indicators prompt
│   └── portfolio_manager.txt          # Final trade decision prompt
├── src/
│   ├── __init__.py
│   ├── config_loader.py               # YAML & Environment parser
│   ├── data/
│   │   ├── yfinance_client.py         # Stock price & technical indicators
│   │   ├── noozra_client.py           # Noozra news ingestion & fallback
│   │   └── sentiment.py              # NLP sentiment scoring module
│   ├── database/
│   │   ├── supabase_client.py         # Supabase PostgreSQL wrapper
│   │   └── models.py                  # Pydantic & DB ORM models
│   ├── agents/
│   │   ├── schemas.py                 # TradeDecision & Plan Pydantic schemas
│   │   ├── tools/
│   │   │   ├── market_tools.py        # yfinance tools for CrewAI
│   │   │   ├── news_tools.py          # News & sentiment tools for CrewAI
│   │   │   └── portfolio_tools.py     # Cash & position tools for CrewAI
│   │   ├── factory.py                 # Dynamic Crew & Agent instantiate
│   │   └── crews.py                   # Sequential & Hierarchical orchestrators
│   ├── execution/
│   │   ├── paper_trading.py           # Cash, position & PnL accounting
│   │   ├── backtester.py              # Historical simulation runner
│   │   └── metrics.py                 # Base 100, Sharpe, Drawdown calculations
│   └── dashboard/
│       ├── gh_pages_builder.py        # Jinja2 + Plotly HTML compiler
│       ├── templates/
│       │   └── index.html.j2          # Main GitHub Pages template
│       └── streamlit_app.py           # Interactive Streamlit dashboard
├── tests/
│   ├── test_data.py
│   ├── test_trading.py
│   └── test_agents.py
├── logs/                              # Gitignored raw execution logs
├── docs/                              # Compiled static output for GitHub Pages
├── requirements.txt
├── .env.example
├── AGENTS.md
└── README.md

```

---

## 3. Tech Stack & Dependencies

| Category | Technology / Library | Purpose |
| --- | --- | --- |
| **Language** | Python 3.11+ | Core runtime |
| **Agent Framework** | `crewai`, `litellm` | Multi-agent orchestration & multi-provider LLM routing |
| **Financial Data** | `yfinance`, `pandas-ta` | Market prices, technical indicators (RSI, MACD, SMA) |
| **News Data** | Noozra API (`requests`) | Global news across Politics, Finance, Business, World |
| **Database** | Supabase (`supabase`) | PostgreSQL persistence layer |
| **Data Processing** | `pandas`, `numpy` | Time-series processing, metrics calculations |
| **UI Framework 1** | Streamlit (`streamlit`) | Interactive web application |
| **UI Framework 2** | `jinja2`, `plotly` | Static HTML/Markdown generation for GitHub Pages |
| **CI/CD** | GitHub Actions | Automated execution and publishing |

---

## 4. Database Schema (Supabase PostgreSQL)

Execute these DDL statements in the Supabase SQL Editor:

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Teams Table
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    architecture VARCHAR(50) NOT NULL CHECK (architecture IN ('sequential', 'hierarchical')),
    model VARCHAR(255) DEFAULT '',
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Agents Table
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    role TEXT NOT NULL,
    llm_model VARCHAR(255) NOT NULL,
    prompt_file VARCHAR(255),
    tools_list JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Portfolios Table
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE UNIQUE,
    initial_cash NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    current_cash NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    total_value NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    benchmark_symbol VARCHAR(20) DEFAULT '^GSPC',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Active Positions Table
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    quantity NUMERIC(15, 4) NOT NULL DEFAULT 0,
    avg_buy_price NUMERIC(15, 2) NOT NULL,
    current_price NUMERIC(15, 2) NOT NULL,
    market_value NUMERIC(15, 2) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, symbol)
);

-- Transactions Log Table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    agent_name VARCHAR(255) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    quantity NUMERIC(15, 4) DEFAULT 0,
    executed_price NUMERIC(15, 2),
    total_amount NUMERIC(15, 2),
    reasoning TEXT,
    raw_log_path TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Daily Portfolio Snapshots Table
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID REFERENCES portfolios(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_value NUMERIC(15, 2) NOT NULL,
    cash_balance NUMERIC(15, 2) NOT NULL,
    portfolio_base100 NUMERIC(10, 4) NOT NULL DEFAULT 100.00,
    benchmark_base100 NUMERIC(10, 4) NOT NULL DEFAULT 100.00,
    daily_return NUMERIC(10, 6),
    max_drawdown NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, snapshot_date)
);

-- Security: Row Level Security (RLS) for Public Read Access
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON agents FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON portfolios FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON positions FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON transactions FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON portfolio_snapshots FOR SELECT USING (true);

```

---

## 5. Agent Output Validation & Fallback Rules

### Trade Decision Pydantic Schema (`src/agents/schemas.py`)

```python
from pydantic import BaseModel, Field
from typing import Literal, List

class TradeDecision(BaseModel):
    symbol: str = Field(description="Stock ticker symbol, e.g. AAPL, NVDA, MSFT")
    action: Literal["BUY", "SELL", "HOLD"] = Field(description="Trading decision")
    quantity: float = Field(default=0.0, ge=0.0, description="Quantity of shares to buy or sell")
    reasoning: str = Field(description="Detailed financial and technical justification for the decision")

class TeamTradingPlan(BaseModel):
    decisions: List[TradeDecision]

```

### Validation & Fallback Lifecycle

1. **Validation Attempt**: CrewAI's output is parsed via `TeamTradingPlan.model_validate_json()`.
2. **First Retry**: If parsing fails (invalid JSON, missing fields, or incorrect types), the execution engine triggers a CrewAI correction task containing the exact validation error string.
3. **Safety Fallback**: If parsing fails a second time:
* Action defaults to `HOLD`.
* Quantity defaults to `0.0`.
* Reasoning is logged as `"SAFETY FALLBACK: Agent output failed JSON validation twice."`.
* The error details are written to `./logs/errors.log` and registered in Supabase.



---

## 6. Mathematical Formulas & Accounting Rules

### Base 100 Indexing

Given initial capital $V_0$ at start date $t_0$, and portfolio value $V(t)$ at date $t$:

$$\text{Portfolio}_{\text{base100}}(t) = 100 \times \frac{V(t)}{V_0}$$

Given benchmark closing price $P_b(t)$ and initial price $P_b(t_0)$:

$$\text{Benchmark}_{\text{base100}}(t) = 100 \times \frac{P_b(t)}{P_b(t_0)}$$

### Paper Trading Balance Sheet Equations

* **Total Value**: $\text{Cash} + \sum (\text{Quantity}_i \times \text{Current Price}_i)$
* **Buy Execution Constraint**: $\text{Quantity} \times \text{Price} \le \text{Current Cash}$
* **Sell Execution Constraint**: $\text{Quantity} \le \text{Owned Shares}$

### Sharpe Ratio (Annualized)

$$SR = \frac{\bar{R}_p - R_f}{\sigma_p} \times \sqrt{252}$$


Where $R_f$ is risk-free rate (default = $0.02$), $\bar{R}_p$ is average daily return, and $\sigma_p$ is standard deviation of daily returns.

---

## 7. Dual Dashboard Specifications

### 1. GitHub Pages Builder (`src/dashboard/gh_pages_builder.py`)

* Reads data from Supabase.
* Generates interactive Plotly figures (`fig.to_html(full_html=False, include_plotlyjs='cdn')`).
* Renders Jinja2 template (`templates/index.html.j2`) into static files inside `./docs/`.
* Includes Base 100 comparison charts, agent breakdown cards, transaction logs, and portfolio metric tables.

### 2. Interactive Streamlit App (`src/dashboard/streamlit_app.py`)

* Connects directly to Supabase using `SUPABASE_ANON_KEY`.
* Features interactive controls: date picker, team selector, benchmark selector, and metric toggles.
* Renders dynamic Plotly time-series charts with dark/light mode compatibility.

---

## 8. Development Environment & Configuration Settings

### Environment Variables (`.env.example`)

```env
# Supabase Configuration
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key-for-backend
SUPABASE_ANON_KEY=your-supabase-anon-key-for-ui

# LLM Providers (Multi-Provider via LiteLLM)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...

```

---
