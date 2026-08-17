"""Supabase PostgreSQL database client wrapper."""

import os
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

try:
    from supabase import create_client, Client
except ImportError:
    Client = Any  # Fallback type hint if package not installed yet
    create_client = None

from src.database.models import (
    TeamCreate, AgentCreate, PortfolioCreate,
    PositionCreate, TransactionCreate, PortfolioSnapshotCreate
)

load_dotenv()
logger = logging.getLogger(__name__)


class SupabaseDBClient:
    """Wrapper for Supabase database operations."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, use_anon: bool = False) -> None:
        """
        Initialize Supabase client.
        
        :param url: Supabase project URL (defaults to SUPABASE_URL env var)
        :param key: Supabase API Key (defaults to SUPABASE_KEY or SUPABASE_ANON_KEY env var)
        :param use_anon: If True, uses SUPABASE_ANON_KEY for read-only queries
        """
        raw_url = url if url is not None else os.getenv("SUPABASE_URL", "")
        if raw_url:
            raw_url = raw_url.rstrip("/")
            if raw_url.endswith("/rest/v1"):
                raw_url = raw_url[:-len("/rest/v1")].rstrip("/")
        self.url = raw_url
        
        if key is not None:
            self.key = key
        elif use_anon:
            self.key = os.getenv("SUPABASE_ANON_KEY", "")
        else:
            self.key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

        self.client: Optional[Client] = None
        self._is_connected = False
        self._mock_portfolios: Dict[str, Dict[str, Any]] = {}
        self._mock_positions: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._mock_transactions: List[Dict[str, Any]] = []
        self._mock_snapshots: List[Dict[str, Any]] = []
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize underlying Supabase SDK client."""
        if not create_client:
            logger.warning("supabase-py library is not installed. SupabaseDBClient running in stub mode.")
            return

        if not self.url or not self.key or "your-supabase" in self.url:
            logger.warning("Supabase credentials missing or set to placeholder. Operating in offline/mock mode.")
            return

        try:
            self.client = create_client(self.url, self.key)
            self._is_connected = True
            logger.info("Successfully connected to Supabase database.")
        except Exception as e:
            logger.warning(f"Failed to connect to Supabase: {e}. Operating in offline/mock mode.")
            self.client = None
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if active Supabase connection is established."""
        return self._is_connected

    # --- Team Operations ---

    def create_team(self, team: TeamCreate) -> Dict[str, Any]:
        """Insert or upsert a new team into 'teams' table."""
        payload = team.model_dump()
        if not self._is_connected or not self.client:
            logger.info(f"[Offline] Mock creating team: {payload['name']}")
            payload["id"] = "00000000-0000-0000-0000-000000000001"
            return payload

        # Use upsert on unique constraint 'name' to avoid conflict exceptions
        response = self.client.table("teams").upsert(payload, on_conflict="name").execute()
        if response.data:
            return response.data[0]
        
        # Fallback query if upsert returned no representation
        fetched = self.get_team_by_name(team.name)
        return fetched if fetched else {}

    def get_all_teams(self) -> List[Dict[str, Any]]:
        """Fetch all teams registered in Supabase."""
        if not self._is_connected or not self.client:
            return [
                {"id": "00000000-0000-0000-0000-000000000001", "name": "Sequential Team Alpha", "architecture": "sequential"},
                {"id": "00000000-0000-0000-0000-000000000002", "name": "Hierarchical Team Beta", "architecture": "hierarchical"}
            ]
        try:
            response = self.client.table("teams").select("*").execute()
            return response.data or []
        except Exception as e:
            logger.warning(f"Error fetching all teams: {e}")
            return []

    def get_team_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Fetch team record by name."""
        if not self._is_connected or not self.client:
            logger.info(f"[Offline] Mock fetching team by name: {name}")
            return None

        try:
            response = self.client.table("teams").select("*").eq("name", name).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.warning(f"Error fetching team by name '{name}': {e}")
            return None

    def get_or_create_team(self, team: TeamCreate) -> Dict[str, Any]:
        """Fetch existing team by name or create/upsert a team."""
        existing = self.get_team_by_name(team.name)
        if existing:
            return existing
        try:
            return self.create_team(team)
        except Exception as e:
            logger.warning(f"Failed to upsert team '{team.name}': {e}. Retrying fetch by name.")
            existing_retry = self.get_team_by_name(team.name)
            if existing_retry:
                return existing_retry
            raise e

    # --- Agent Operations ---

    def create_agent(self, agent: AgentCreate) -> Dict[str, Any]:
        """Insert agent record into 'agents' table."""
        payload = agent.model_dump(mode="json")
        if not self._is_connected or not self.client:
            logger.info(f"[Offline] Mock creating agent: {payload['name']}")
            payload["id"] = "00000000-0000-0000-0000-000000000002"
            return payload

        response = self.client.table("agents").insert(payload).execute()
        return response.data[0] if response.data else {}

    def get_agents_by_team(self, team_id: str) -> List[Dict[str, Any]]:
        """Fetch all agents belonging to a team."""
        if not self._is_connected or not self.client:
            return []

        try:
            response = self.client.table("agents").select("*").eq("team_id", str(team_id)).execute()
            return response.data or []
        except Exception as e:
            logger.warning(f"Error fetching agents for team '{team_id}': {e}")
            return []

    # --- Portfolio Operations ---

    def get_portfolio_by_id(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        """Fetch portfolio record by portfolio ID."""
        if not self._is_connected or not self.client:
            p_id = str(portfolio_id)
            return self._mock_portfolios.get(p_id)

        try:
            response = self.client.table("portfolios").select("*").eq("id", str(portfolio_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.warning(f"Error fetching portfolio by id '{portfolio_id}': {e}")
            return None

    def get_portfolio_by_team_id(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Fetch portfolio record by team ID."""
        if not self._is_connected or not self.client:
            p_id = str(team_id)
            return self._mock_portfolios.get(p_id)

        try:
            response = self.client.table("portfolios").select("*").eq("team_id", str(team_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.warning(f"Error fetching portfolio by team_id '{team_id}': {e}")
            return None

    def get_or_create_portfolio(self, team_id: str, initial_cash: float = 10000.0, benchmark: str = "^GSPC") -> Dict[str, Any]:
        """Fetch existing portfolio for team (or by portfolio ID) or create a new one."""
        if not self._is_connected or not self.client:
            p_id = str(team_id)
            if p_id in self._mock_portfolios:
                return self._mock_portfolios[p_id]
            default_id = "00000000-0000-0000-0000-000000000003"
            if default_id not in self._mock_portfolios:
                self._mock_portfolios[default_id] = {
                    "id": default_id,
                    "team_id": str(team_id),
                    "initial_cash": initial_cash,
                    "current_cash": initial_cash,
                    "total_value": initial_cash,
                    "benchmark_symbol": benchmark,
                }
            return self._mock_portfolios[default_id]

        try:
            # First check if existing portfolio by team_id
            response = self.client.table("portfolios").select("*").eq("team_id", str(team_id)).execute()
            if response.data:
                return response.data[0]

            # Second check if existing portfolio by portfolio id (in case portfolio_id was passed)
            response_by_id = self.client.table("portfolios").select("*").eq("id", str(team_id)).execute()
            if response_by_id.data:
                return response_by_id.data[0]

            portfolio = PortfolioCreate(
                team_id=team_id,
                initial_cash=initial_cash,
                current_cash=initial_cash,
                total_value=initial_cash,
                benchmark_symbol=benchmark,
            )
            insert_res = self.client.table("portfolios").insert(portfolio.model_dump(mode="json")).execute()
            return insert_res.data[0] if insert_res.data else {}
        except Exception as e:
            logger.warning(f"Could not create portfolio for team '{team_id}' (e.g. read-only client / RLS): {e}")
            return {
                "id": str(team_id),
                "team_id": str(team_id),
                "initial_cash": initial_cash,
                "current_cash": initial_cash,
                "total_value": initial_cash,
                "benchmark_symbol": benchmark,
            }

    def update_portfolio(self, portfolio_id: str, current_cash: float, total_value: float) -> Dict[str, Any]:
        """Update portfolio cash and total value."""
        if not self._is_connected or not self.client:
            p_id = str(portfolio_id)
            if p_id not in self._mock_portfolios:
                self._mock_portfolios[p_id] = {"id": p_id, "initial_cash": 10000.0}
            self._mock_portfolios[p_id]["current_cash"] = current_cash
            self._mock_portfolios[p_id]["total_value"] = total_value
            return self._mock_portfolios[p_id]

        payload = {"current_cash": current_cash, "total_value": total_value}
        response = self.client.table("portfolios").update(payload).eq("id", str(portfolio_id)).execute()
        return response.data[0] if response.data else {}

    # --- Position Operations ---

    def upsert_position(self, position: PositionCreate) -> Dict[str, Any]:
        """Upsert stock position into 'positions' table."""
        payload = position.model_dump(mode="json")
        if not self._is_connected or not self.client:
            p_id = str(payload["portfolio_id"])
            symbol = str(payload["symbol"])
            if p_id not in self._mock_positions:
                self._mock_positions[p_id] = {}
            payload["id"] = f"mock-pos-{symbol}"
            self._mock_positions[p_id][symbol] = payload
            return payload

        response = self.client.table("positions").upsert(payload, on_conflict="portfolio_id,symbol").execute()
        return response.data[0] if response.data else {}

    def get_positions(self, portfolio_id: str) -> List[Dict[str, Any]]:
        """Fetch all positions for a portfolio."""
        if not self._is_connected or not self.client:
            p_id = str(portfolio_id)
            return list(self._mock_positions.get(p_id, {}).values())

        response = self.client.table("positions").select("*").eq("portfolio_id", str(portfolio_id)).execute()
        return response.data or []

    # --- Transaction Operations ---

    def log_transaction(self, transaction: TransactionCreate) -> Dict[str, Any]:
        """Record trade execution in 'transactions' table."""
        payload = transaction.model_dump(mode="json")
        if not self._is_connected or not self.client:
            payload["id"] = f"mock-tx-{len(self._mock_transactions)+1}"
            self._mock_transactions.append(payload)
            return payload

        response = self.client.table("transactions").insert(payload).execute()
        return response.data[0] if response.data else {}

    def get_transactions(self, portfolio_id: str) -> List[Dict[str, Any]]:
        """Fetch all historical transactions for a portfolio."""
        if not self._is_connected or not self.client:
            return list(self._mock_transactions)

        response = self.client.table("transactions").select("*").eq("portfolio_id", str(portfolio_id)).order("executed_at", desc=True).execute()
        return response.data or []

    # --- Snapshot Operations ---

    def insert_snapshot(self, snapshot: PortfolioSnapshotCreate) -> Dict[str, Any]:
        """Insert daily snapshot into 'portfolio_snapshots' table."""
        payload = snapshot.model_dump(mode="json")
        if not self._is_connected or not self.client:
            payload["id"] = f"mock-snap-{len(self._mock_snapshots)+1}"
            self._mock_snapshots.append(payload)
            return payload

        response = self.client.table("portfolio_snapshots").upsert(payload, on_conflict="portfolio_id,snapshot_date").execute()
        return response.data[0] if response.data else {}

    def get_snapshots(self, portfolio_id: str) -> List[Dict[str, Any]]:
        """Fetch all snapshots for a portfolio ordered by date."""
        if not self._is_connected or not self.client:
            return list(self._mock_snapshots)

        response = self.client.table("portfolio_snapshots").select("*").eq("portfolio_id", str(portfolio_id)).order("snapshot_date", desc=False).execute()
        return response.data or []

