"""Portfolio 'investor archetype' classifier — Recommended Enhancement, not
sourced from any of the three source documents (see docs/DECISION_LOG.md).

Deterministic and rule-based (no LLM): classifies a portfolio's *current
composition* — not the person — along two axes built from dimension scores
already computed by the Fundamental/Valuation/Technical agents:

  growth_axis      = weighted-avg(growth_score) - weighted-avg(valuation_score)
                      (positive = paying up for growth; negative = buying cheap)
  aggression_axis   = weighted-avg(momentum_score) - weighted-avg(quality_score)
                      (positive = momentum-chasing; negative = quality/stability)

This is a simple 2x2 framing (four archetypes), not a psychological profile
of the investor — the label describes the portfolio's current tilt and
will change as holdings/scores change.
"""
from __future__ import annotations

from dataclasses import dataclass

_ARCHETYPES = {
    (True, True): ("성장추격형", "🚀", "고성장·고모멘텀 종목 위주로 구성되어 있습니다. 밸류에이션 부담과 변동성이 큰 편입니다."),
    (True, False): ("성장우량형", "🌱", "성장성은 높지만 상대적으로 안정적인 우량주 위주로 구성되어 있습니다."),
    (False, True): ("역발상모멘텀형", "🎯", "저평가된 종목 중 모멘텀이 살아있는 종목 위주로 구성되어 있습니다."),
    (False, False): ("가치안정형", "🛡️", "저평가·고퀄리티 종목 위주로 구성되어 안정성이 높은 편입니다."),
}


@dataclass
class ArchetypeResult:
    name: str
    icon: str
    description: str
    growth_axis: float
    aggression_axis: float
    concentration_note: str


def classify_portfolio(
    holdings: list[dict],  # [{ticker, market_value, growth_score, valuation_score, momentum_score, quality_score}]
) -> ArchetypeResult | None:
    scored = [h for h in holdings if h.get("market_value", 0) > 0]
    total_value = sum(h["market_value"] for h in scored)
    if total_value == 0:
        return None

    def w_avg(field: str) -> float | None:
        weighted = [(h["market_value"] / total_value) * h[field] for h in scored if h.get(field) is not None]
        weights_used = [h["market_value"] / total_value for h in scored if h.get(field) is not None]
        if not weighted or sum(weights_used) == 0:
            return None
        return sum(weighted) / sum(weights_used)

    growth = w_avg("growth_score")
    valuation = w_avg("valuation_score")
    momentum = w_avg("momentum_score")
    quality = w_avg("quality_score")

    if growth is None or valuation is None or momentum is None or quality is None:
        return None

    growth_axis = growth - valuation
    aggression_axis = momentum - quality

    name, icon, description = _ARCHETYPES[(growth_axis >= 0, aggression_axis >= 0)]

    top_weight = max(h["market_value"] for h in scored) / total_value
    if top_weight >= 0.40:
        concentration_note = f"최대 비중 종목이 전체의 {top_weight:.0%}를 차지 — 집중 투자 성향"
    elif len({h.get("sector") for h in scored if h.get("sector")}) >= 4:
        concentration_note = "여러 섹터에 고르게 분산되어 있습니다"
    else:
        concentration_note = "특정 섹터에 다소 치우쳐 있습니다"

    return ArchetypeResult(
        name=name,
        icon=icon,
        description=description,
        growth_axis=growth_axis,
        aggression_axis=aggression_axis,
        concentration_note=concentration_note,
    )
