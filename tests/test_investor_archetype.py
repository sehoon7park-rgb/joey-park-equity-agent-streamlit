from joey_park.analytics.investor_archetype import classify_portfolio


def _holding(ticker, market_value, growth, valuation, momentum, quality, sector="tech"):
    return {
        "ticker": ticker,
        "market_value": market_value,
        "growth_score": growth,
        "valuation_score": valuation,
        "momentum_score": momentum,
        "quality_score": quality,
        "sector": sector,
    }


def test_growth_chaser_archetype():
    holdings = [_holding("A", 1000, growth=0.9, valuation=0.2, momentum=0.9, quality=0.3)]
    result = classify_portfolio(holdings)
    assert result.name == "성장추격형"
    assert result.growth_axis > 0
    assert result.aggression_axis > 0


def test_value_stability_archetype():
    holdings = [_holding("A", 1000, growth=0.3, valuation=0.9, momentum=0.2, quality=0.9)]
    result = classify_portfolio(holdings)
    assert result.name == "가치안정형"
    assert result.growth_axis < 0
    assert result.aggression_axis < 0


def test_empty_portfolio_returns_none():
    assert classify_portfolio([]) is None


def test_missing_scores_returns_none():
    holdings = [{"ticker": "A", "market_value": 1000, "sector": "tech"}]
    assert classify_portfolio(holdings) is None


def test_concentration_note_flags_concentrated_portfolio():
    holdings = [
        _holding("A", 8000, 0.5, 0.5, 0.5, 0.5),
        _holding("B", 2000, 0.5, 0.5, 0.5, 0.5),
    ]
    result = classify_portfolio(holdings)
    assert "집중" in result.concentration_note


def test_concentration_note_flags_diversified_portfolio():
    holdings = [
        _holding("A", 250, 0.5, 0.5, 0.5, 0.5, sector="tech"),
        _holding("B", 250, 0.5, 0.5, 0.5, 0.5, sector="finance"),
        _holding("C", 250, 0.5, 0.5, 0.5, 0.5, sector="healthcare"),
        _holding("D", 250, 0.5, 0.5, 0.5, 0.5, sector="energy"),
    ]
    result = classify_portfolio(holdings)
    assert "분산" in result.concentration_note
