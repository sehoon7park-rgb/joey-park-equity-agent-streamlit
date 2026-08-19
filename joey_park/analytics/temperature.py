"""'Temperature' / anomaly-detection score — Recommended Enhancement, not
sourced from any of the three source documents (see docs/DECISION_LOG.md).

Inspired by the "이상 신호 온도" (anomaly-signal temperature) concept in the
UI reference the user pointed to (a Mahalanobis-distance-style measure of
how far a stock's recent trading behavior sits from its own trailing
history). This module implements a simplified version of that idea:

    temperature = sqrt(z_return^2 + z_volume^2 + z_volatility^2)

treating the three signals as independent (a true Mahalanobis distance
would use their covariance matrix; this Euclidean combination is a
documented simplification, not a claim of statistical rigor). Every input
is computed from the same price_history already fetched by yfinance — no
new data source, no LLM.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from joey_park.data.models import MarketSnapshot

_SHORT_WINDOW = 10  # "recent" window, trading days
_MIN_BARS_REQUIRED = 40


@dataclass
class TemperatureResult:
    temperature: float | None  # combined anomaly magnitude; None if insufficient data
    z_return: float | None
    z_volume: float | None
    z_volatility: float | None
    label: str  # "평상시" / "주의" / "고온" / "DATA_NOT_AVAILABLE"


def _rolling_mean(values: list[float], window: int) -> list[float]:
    return [
        sum(values[i - window + 1 : i + 1]) / window
        for i in range(window - 1, len(values))
    ]


def _rolling_std(values: list[float], window: int) -> list[float]:
    out = []
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1 : i + 1]
        out.append(statistics.pstdev(chunk))
    return out


def _zscore_latest(series: list[float]) -> float | None:
    if len(series) < 5:
        return None
    latest = series[-1]
    baseline = series[:-1]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline)
    if std == 0:
        return 0.0
    return (latest - mean) / std


def compute_temperature(market: MarketSnapshot) -> TemperatureResult:
    bars = market.price_history
    if len(bars) < _MIN_BARS_REQUIRED:
        return TemperatureResult(None, None, None, None, "DATA_NOT_AVAILABLE")

    closes = [b.close for b in bars]
    volumes = [float(b.volume) for b in bars]
    returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]

    rolling_return = _rolling_mean(returns, _SHORT_WINDOW)
    rolling_vol_of_return = _rolling_std(returns, _SHORT_WINDOW)
    rolling_volume = _rolling_mean(volumes, _SHORT_WINDOW)

    z_return = _zscore_latest(rolling_return)
    z_volatility = _zscore_latest(rolling_vol_of_return)
    z_volume = _zscore_latest(rolling_volume)

    components = [z for z in (z_return, z_volatility, z_volume) if z is not None]
    if not components:
        return TemperatureResult(None, None, None, None, "DATA_NOT_AVAILABLE")

    temperature = (sum(z**2 for z in components)) ** 0.5

    if temperature >= 2.5:
        label = "고온"
    elif temperature >= 1.5:
        label = "주의"
    else:
        label = "평상시"

    return TemperatureResult(
        temperature=temperature,
        z_return=z_return,
        z_volume=z_volume,
        z_volatility=z_volatility,
        label=label,
    )
