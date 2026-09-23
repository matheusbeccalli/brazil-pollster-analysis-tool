from pollster.config import ELECTIONS, PARTY_LEANING, POLLSTER_MERGES


def test_elections_have_both_rounds():
    for year, dates in ELECTIONS.items():
        assert "round_1" in dates, f"{year} missing round_1"
        assert "round_2" in dates, f"{year} missing round_2"


def test_elections_cover_required_years():
    for year in [2014, 2018, 2022]:
        assert year in ELECTIONS, f"Missing election year {year}"


def test_party_leaning_has_major_parties():
    assert PARTY_LEANING["PT"] == "left"
    assert PARTY_LEANING["PL"] == "right"
    assert PARTY_LEANING["MDB"] == "center"


def test_pollster_merges_ibope_ipec():
    assert POLLSTER_MERGES.get("Ibope") == POLLSTER_MERGES.get("Ipec")


def test_2026_election_dates_and_aliases():
    from datetime import date
    from pollster.config import ELECTIONS, POLLSTER_ALIASES_PODER360, PODER360_AGREGADOR_URL
    assert ELECTIONS[2026]["round_1"] == date(2026, 10, 4)
    assert ELECTIONS[2026]["round_2"] == date(2026, 10, 25)
    assert POLLSTER_ALIASES_PODER360["AtlasIntel"] == "AtlasIntel/Internet"
    assert PODER360_AGREGADOR_URL.startswith("https://monitor-agregador.poder360.com.br")


def test_prediction_market_sources():
    from pollster.config import (POLYMARKET_EVENT_SLUGS, KALSHI_SERIES_TICKERS,
                                 POLYMARKET_GAMMA_URL, POLYMARKET_CLOB_URL, KALSHI_API_URL)
    assert "brazil-presidential-election" in POLYMARKET_EVENT_SLUGS
    assert "KXBRPRES" in KALSHI_SERIES_TICKERS
    assert POLYMARKET_GAMMA_URL.startswith("https://") and POLYMARKET_CLOB_URL.startswith("https://")
    assert KALSHI_API_URL.endswith("/trade-api/v2")
