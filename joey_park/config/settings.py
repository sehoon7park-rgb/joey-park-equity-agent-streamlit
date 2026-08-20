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
    anthropic_api_key_error: str | None = None

    @property
    def scoring_weights(self) -> dict[str, float]:
        return self.config["scoring"]["weights"]

    @property
    def agents_enabled(self) -> dict[str, bool]:
        return self.config["agents"]["enabled"]

    def is_llm_configured(self) -> bool:
        return bool(self.anthropic_api_key)


def _validate_anthropic_api_key(raw: str | None) -> tuple[str | None, str | None]:
    """httpx encodes header values as ASCII; a stray non-ASCII character
    pasted into the key (e.g. via a secrets UI) crashes deep inside the
    Anthropic SDK with an opaque UnicodeEncodeError. Catch it here instead,
    where we can point at the exact character and explain the likely cause.
    """
    if not raw:
        return None, None
    key = raw.strip()
    if key.isascii():
        return key, None
    bad = [(i, ch) for i, ch in enumerate(key) if not ch.isascii()]
    first_pos, first_ch = bad[0]
    last_pos, _ = bad[-1]
    error = (
        f"ANTHROPIC_API_KEY에 ASCII가 아닌 문자가 포함되어 있습니다 (위치 {first_pos}"
        + (f"-{last_pos}" if last_pos != first_pos else "")
        + f", 예: {first_ch!r}). Secrets에 키를 붙여넣을 때 다른 텍스트가 함께 섞여 들어간 것으로 "
        "보입니다 — 'sk-ant-'로 시작하는 키 값만 다시 복사해서 앞뒤 공백/텍스트 없이 넣어주세요."
    )
    return None, error


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

    anthropic_api_key, anthropic_api_key_error = _validate_anthropic_api_key(
        os.environ.get("ANTHROPIC_API_KEY")
    )

    return Settings(
        anthropic_api_key=anthropic_api_key,
        anthropic_api_key_error=anthropic_api_key_error,
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
