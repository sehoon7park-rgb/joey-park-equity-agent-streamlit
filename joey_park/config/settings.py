"""Configuration loading: .env + config.yaml + sector_universe.yaml.

Nothing here is hardcoded that should be user-editable — see config.yaml.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent.parent

load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    anthropic_model: str
    fred_api_key: str | None
    news_api_key: str | None
    sec_edgar_contact_email: str
    db_path: str
    log_level: str
    config: dict[str, Any] = field(default_factory=dict)
    sector_universe: dict[str, Any] = field(default_factory=dict)

    @property
    def scoring_weights(self) -> dict[str, float]:
        return self.config["scoring"]["weights"]

    @property
    def agents_enabled(self) -> dict[str, bool]:
        return self.config["agents"]["enabled"]

    def is_llm_configured(self) -> bool:
        return bool(self.anthropic_api_key)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required config file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> Settings:
    config_path = Path(os.environ.get("JOEY_PARK_CONFIG_PATH", _PACKAGE_DIR / "config.yaml"))
    universe_path = config_path.parent / "sector_universe.yaml"

    config = _load_yaml(config_path)
    sector_universe = _load_yaml(universe_path)

    weights = config["scoring"]["weights"]
    weight_sum = round(sum(weights.values()), 6)
    if weight_sum != 1.0:
        raise ValueError(
            f"scoring.weights in {config_path} must sum to 1.0, got {weight_sum}: {weights}"
        )

    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        fred_api_key=os.environ.get("FRED_API_KEY") or None,
        news_api_key=os.environ.get("NEWS_API_KEY") or None,
        sec_edgar_contact_email=os.environ.get(
            "SEC_EDGAR_CONTACT_EMAIL", "your-email@example.com"
        ),
        db_path=os.environ.get("JOEY_PARK_DB_PATH", str(_PROJECT_ROOT / "joey_park.db")),
        log_level=os.environ.get("JOEY_PARK_LOG_LEVEL", "INFO"),
        config=config,
        sector_universe=sector_universe,
    )
