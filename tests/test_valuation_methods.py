from joey_park.analytics.valuation_methods import evaluate

HEURISTICS = {
    "peg_cheap_below": 1.0, "peg_expensive_above": 2.5,
    "ev_ebitda_cheap_below": 10.0, "ev_ebitda_expensive_above": 25.0,
    "fcf_yield_good_above": 0.04, "fcf_yield_poor_below": 0.01,
}
METHODS = {
    "default": ["pe_multiple", "ev_ebitda", "fcf_yield"],
    "ai_software_cloud": ["ev_revenue", "fcf_yield", "peg"],
}


def test_sector_specific_methods_selected(healthy_financials, healthy_market):
    results = evaluate(healthy_financials, healthy_market, "ai_software_cloud", METHODS, HEURISTICS)
    methods_used = [r.method for r in results]
    assert methods_used == ["ev_revenue", "fcf_yield", "peg"]


def test_unknown_sector_falls_back_to_default(healthy_financials, healthy_market):
    results = evaluate(healthy_financials, healthy_market, "unknown_sector", METHODS, HEURISTICS)
    methods_used = [r.method for r in results]
    assert methods_used == ["pe_multiple", "ev_ebitda", "fcf_yield"]


def test_missing_data_yields_data_not_available(sparse_financials, healthy_market):
    results = evaluate(sparse_financials, healthy_market, "default", METHODS, HEURISTICS)
    assert all(r.verdict == "DATA_NOT_AVAILABLE" for r in results)


def test_cheap_peg_verdict(healthy_financials, healthy_market):
    results = evaluate(healthy_financials, healthy_market, "ai_software_cloud", METHODS, HEURISTICS)
    peg_result = next(r for r in results if r.method == "peg")
    assert peg_result.value == 1.2
    assert peg_result.verdict == "FAIR"  # between cheap_below=1.0 and expensive_above=2.5
