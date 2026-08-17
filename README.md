# 📈 Tyche — Multi-Agent Stock Investment & Paper Trading Platform

**Tyche** is an experimental multi-agent stock investment, backtesting, and paper-trading platform powered by **CrewAI**, **LiteLLM**, **yfinance**, **pandas-ta**, **Noozra API**, and **Supabase**. 

The platform simulates autonomous agent teams (built with both **Sequential** and **Hierarchical** multi-agent architectures) that analyze real-time market price technicals, macro news, and sentiment indicators to execute daily paper trading strategies.

---

## 🚀 Key Features & Goals

- 🤖 **Multi-Agent Execution Architectures**:
  - **Sequential Team Architecture**: Step-by-step pipeline passing context from Macro Analyst $\rightarrow$ Technical Analyst $\rightarrow$ Portfolio Manager.
  - **Hierarchical Manager Architecture**: A central Manager Agent delegates analysis tasks dynamically to specialized agent roles.
- 🔀 **Multi-Provider LLM Support**: Multi-model routing powered by `litellm` (OpenAI GPT-4o, Anthropic Claude, Google Gemini).
- 📊 **Financial Data & Technical Indicators**: Automated fetching of historical price data via `yfinance` with technical indicators calculated via `pandas-ta` (RSI, SMA, MACD, Trend signals).
- 📰 **News & Sentiment Analysis**: Real-time global news ingestion via **Noozra API** with fallback to `yfinance` ticker news and rule-based NLP sentiment scoring.
- 🛡️ **Pydantic Validation & Safety Fallbacks**: Strict JSON output validation via Pydantic schemas. Includes automatic single-retry correction tasks and a fail-safe fallback (`HOLD` action, `$0` allocation) to protect against malformed LLM responses.
- 🗄️ **Dual Storage Architecture**:
  - **Supabase PostgreSQL**: Live persistence for teams, agents, portfolios, active positions, transaction logs, and daily snapshots with Row Level Security (RLS).
  - **Local Execution Logs**: Full raw chain-of-thought execution logs stored locally in `./logs`.
- 💻 **Dual Presentation Layer**:
  - **Interactive Streamlit Web App**: Real-time interactive dashboard featuring date filters, portfolio selector, benchmark toggles, and dynamic Plotly charts.
  - **Static GitHub Pages Site Generator**: Automated HTML/Plotly compilation using Jinja2 templates deployed directly to `./docs` for GitHub Pages hosting.
- ⚙️ **Automated CI/CD Workflows**: Scheduled GitHub Actions for automated daily trading cycles and static site deployment.

---

## 🏗️ System Architecture

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

## 📁 Repository Structure

```
.
├── .github/
│   └── workflows/
│       ├── daily_trading.yml          # Automated paper trading & DB snapshot
│       └── publish_gh_pages.yml       # Static HTML build & GitHub Pages deploy
├── config/
│   ├── teams/
│   │   ├── sequential_team_alpha.yaml # Sequential Crew configuration
│   │   └── hierarchical_team_beta.yaml# Hierarchical Crew configuration
│   └── default_settings.yaml          # Target tickers, initial cash & risk limits
├── prompts/
│   ├── macro_analyst.txt              # Macro Analyst prompt template
│   ├── technical_analyst.txt          # Technical Analyst prompt template
│   └── portfolio_manager.txt          # Portfolio Manager prompt template
├── src/
│   ├── config_loader.py               # YAML configuration parser
│   ├── data/
│   │   ├── yfinance_client.py         # Financial market price & indicator fetching
│   │   ├── noozra_client.py           # Noozra API news client & fallback chain
│   │   └── sentiment.py               # NLP rule-based sentiment engine
│   ├── database/
│   │   ├── supabase_client.py         # Supabase PostgreSQL database client
│   │   └── models.py                  # Pydantic schemas & database ORM models
│   ├── agents/
│   │   ├── schemas.py                 # Pydantic schemas for agent decisions
│   │   ├── factory.py                 # Dynamic CrewAI Agent & Crew factory
│   │   ├── crews.py                   # Crew execution orchestrator
│   │   └── tools/                     # CrewAI agent tools (market, news, portfolio)
│   ├── execution/
│   │   ├── paper_trading.py           # Balance sheet accounting & trade processor
│   │   ├── backtester.py              # Historical backtesting simulator
│   │   └── metrics.py                 # Financial metrics (Base 100, Sharpe, Drawdown)
│   └── dashboard/
│       ├── gh_pages_builder.py        # Static Jinja2 + Plotly HTML compiler
│       ├── streamlit_app.py           # Interactive Streamlit dashboard UI
│       └── templates/
│           └── index.html.j2          # Main HTML template for GitHub Pages
├── docs/                              # Compiled static output for GitHub Pages
├── main.py                            # Unified CLI entry point
├── pyproject.toml                     # Project metadata & dependencies
├── requirements.txt                   # Dependency list
├── .env.example                       # Environment variables template
├── AGENTS.md                          # Master architectural spec for AI agents
└── README.md                          # Project documentation
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites

- **Python 3.11 or 3.12**
- Git

### 2. Clone the Repository

```bash
git clone https://github.com/your-org/tyche.git
cd tyche
```

### 3. Create & Activate Virtual Environment

Using `uv` (recommended):
```bash
uv venv .venv
# On Windows PowerShell:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

Or using standard `venv`:
```bash
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Environment Configuration

Copy the example `.env` file and configure your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API credentials:

```env
# Supabase Configuration
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key-for-backend
SUPABASE_ANON_KEY=your-supabase-anon-key-for-ui

# LLM Providers (Configure whichever provider you use)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
```

> **Note**: If Supabase credentials are missing or omitted, Tyche automatically operates in **Offline / Mock Mode**, enabling seamless offline testing and local execution!

### 6. Database Setup (Supabase SQL Schema)

If connected to a Supabase project, execute the SQL DDL statements in the Supabase SQL Editor to initialize tables and Row Level Security (RLS) policies:

<details>
<summary><b>Click to expand Supabase SQL DDL Script</b></summary>

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    architecture VARCHAR(50) NOT NULL CHECK (architecture IN ('sequential', 'hierarchical')),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE UNIQUE,
    initial_cash NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    current_cash NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    total_value NUMERIC(15, 2) NOT NULL DEFAULT 10000.00,
    benchmark_symbol VARCHAR(20) DEFAULT '^GSPC',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

-- Enable RLS and public read policies
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
</details>

---

## ⚡ How to Run

Tyche provides a unified command-line interface via `main.py`.

### 1. System Verification & Health Diagnostic Mode

Verify all data clients, news fallback pipelines, sentiment scoring, configuration loaders, and database connections:

```bash
python main.py --mode verification
```

### 2. Run Daily Paper Trading Pipeline

Executes market decision cycles for all active agent teams and records transactions and portfolio snapshots:

```bash
python main.py --mode paper_trading
```

### 3. Run Historical Backtesting Mode

Simulate historical trading cycles across specified tickers and date ranges:

```bash
python main.py --mode backtest
```

### 4. Build Static GitHub Pages Site

Generates interactive Plotly visual charts and static HTML pages into `./docs/index.html`:

```bash
python main.py --mode build_dashboard
```

### 5. Launch Interactive Streamlit Web UI

Run the interactive web UI dashboard:

```bash
streamlit run src/dashboard/streamlit_app.py
```

### 6. Run Unit Tests

Execute the unit test suite:

```bash
pytest
```

---

## 📐 Mathematical Metrics & Accounting Rules

### Base 100 Indexing Formula
To compare performance across teams and benchmarks starting from an indexed base value of 100:

$$\text{Portfolio}_{\text{base100}}(t) = 100 \times \frac{V(t)}{V_0}$$

$$\text{Benchmark}_{\text{base100}}(t) = 100 \times \frac{P_b(t)}{P_b(t_0)}$$

### Balance Sheet Accounting Constraints
- **Total Portfolio Value**: $\text{Cash} + \sum_{i} (\text{Quantity}_i \times \text{Price}_i)$
- **Buy Execution Rule**: $\text{Quantity} \times \text{Price} \le \text{Current Cash}$
- **Sell Execution Rule**: $\text{Quantity} \le \text{Shares Currently Owned}$

### Annualized Sharpe Ratio
$$SR = \frac{\bar{R}_p - R_f}{\sigma_p} \times \sqrt{252}$$

*Where $R_f = 0.02$ (risk-free rate), $\bar{R}_p$ is average daily return, and $\sigma_p$ is standard deviation of daily returns.*

---

## 🤖 Agent Output Validation & Fail-Safe Lifecycle

Tyche enforces strict output typing using Pydantic models:

```python
class TradeDecision(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    quantity: float
    reasoning: str

class TeamTradingPlan(BaseModel):
    decisions: List[TradeDecision]
```

1. **Validation Attempt**: Agent responses are parsed using `TeamTradingPlan.model_validate_json()`.
2. **Auto-Correction Retry**: If validation fails, CrewAI launches a targeted correction task containing the exact validation error message.
3. **Safety Fallback**: If validation fails a second time, the system automatically forces a `HOLD` action (`quantity=0.0`) to safeguard portfolio cash.

---

## 📄 License & System Specification

For detailed architectural specs, ORM schemas, and agent design rules, refer to [AGENTS.md](file:///c:/Users/Neil%20Farmer/Documents/GitHub/tyche/AGENTS.md).
