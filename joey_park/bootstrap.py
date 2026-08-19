"""Wires providers/DB/LLM/orchestrator from Settings — shared by the CLI
and the Streamlit UI so there is exactly one place that constructs the app.
"""
from __future__ import annotations

from joey_park.agents.data_agent import DataAgent
from joey_park.agents.orchestrator import Orchestrator
from joey_park.config.settings import Settings, load_settings
from joey_park.data.providers.fred_provider import FredProvider
from joey_park.data.providers.sec_edgar_provider import SecEdgarProvider
from joey_park.data.providers.yfinance_provider import YFinanceProvider
from joey_park.db.database import Database
from joey_park.llm.anthropic_provider import AnthropicProvider


def build_orchestrator(settings: Settings | None = None) -> tuple[Orchestrator, Database, Settings]:
    settings = settings or load_settings()
    db = Database(settings.db_path)

    yfinance_provider = YFinanceProvider()
    sec_edgar_provider = SecEdgarProvider(settings.sec_edgar_contact_email)
    fred_provider = FredProvider(settings.fred_api_key)
    data_agent = DataAgent(yfinance_provider, sec_edgar_provider, fred_provider)

    llm = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)

    orchestrator = Orchestrator(settings, db, data_agent, llm)
    return orchestrator, db, settings
