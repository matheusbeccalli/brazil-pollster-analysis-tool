import json
from datetime import date

import duckdb
import pandas as pd

from pollster.stages import fetch_markets as FM
from tests.test_markets import KALSHI_EVENT, POLY_EVENT


def _fake_downloads(monkeypatch, fail_slug=None):
    def poly_event(slug):
        if slug == fail_slug:
            raise RuntimeError("404")
        return {**POLY_EVENT, "slug": slug}

    def poly_history(token_id):
        return {"history": [{"t": 1758240010, "p": 0.59}, {"t": 1758326404, "p": 0.485}]}

    def kalshi_series(series):
        return [{**KALSHI_EVENT, "series_ticker": series}]

    def kalshi_candles(series, ticker, start_ts, end_ts):
        return {"candlesticks": [
            {"end_period_ts": 1764997200, "open_interest_fp": "1", "volume_fp": "2",
             "price": {"close_dollars": "0.17", "high_dollars": "0.2", "low_dollars": "0.1", "open_dollars": "0.1"},
             "yes_ask": {"close_dollars": "0.2"}, "yes_bid": {"close_dollars": "0.1"}}]}

    monkeypatch.setattr(FM, "download_polymarket_event", poly_event)
    monkeypatch.setattr(FM, "download_polymarket_history", poly_history)
    monkeypatch.setattr(FM, "download_kalshi_series", kalshi_series)
    monkeypatch.setattr(FM, "download_kalshi_candles", kalshi_candles)


def test_fetch_markets_writes_raw_json_parquets_and_tables(tmp_data_dir, monkeypatch):
    _fake_downloads(monkeypatch)
    monkeypatch.setattr(FM.config, "POLYMARKET_EVENT_SLUGS", ["brazil-presidential-election"])
    monkeypatch.setattr(FM.config, "KALSHI_SERIES_TICKERS", ["KXBRPRES"])
    FM.fetch_markets(tmp_data_dir, as_of=date(2026, 9, 23))

    raw = tmp_data_dir / "raw" / "prediction_markets" / "2026-09-23"
    assert (raw / "polymarket_brazil-presidential-election.json").exists()
    assert (raw / "polymarket_history_601819.json").exists()
    assert (raw / "kalshi_KXBRPRES.json").exists()
    assert (raw / "kalshi_candles_KXBRPRES-26-FBOL.json").exists()
    assert json.loads((raw / "kalshi_KXBRPRES.json").read_text())[0]["series_ticker"] == "KXBRPRES"

    markets = pd.read_parquet(tmp_data_dir / "parquet" / "pm_markets.parquet")
    prices = pd.read_parquet(tmp_data_dir / "parquet" / "pm_prices_daily.parquet")
    assert sorted(markets["platform"].unique()) == ["kalshi", "polymarket"]
    assert len(markets) == 4
    assert set(prices["market_id"]) == {"601819", "9", "KXBRPRES-26-FBOL", "KXBRPRES-26-XXX"}

    con = duckdb.connect(str(tmp_data_dir / "pollster.duckdb"))
    assert con.execute("SELECT COUNT(*) FROM pm_markets").fetchone()[0] == 4
    assert con.execute("SELECT COUNT(*) FROM pm_prices_daily").fetchone()[0] == len(prices)
    con.close()


def test_fetch_markets_continues_when_one_event_fails(tmp_data_dir, monkeypatch):
    _fake_downloads(monkeypatch, fail_slug="missing-slug")
    monkeypatch.setattr(FM.config, "POLYMARKET_EVENT_SLUGS", ["missing-slug", "brazil-presidential-election"])
    monkeypatch.setattr(FM.config, "KALSHI_SERIES_TICKERS", [])
    FM.fetch_markets(tmp_data_dir, as_of=date(2026, 9, 23))
    markets = pd.read_parquet(tmp_data_dir / "parquet" / "pm_markets.parquet")
    assert len(markets) == 2
