from datetime import datetime, timezone

import pandas as pd

from pollster.utils.markets import (MARKET_COLUMNS, PRICE_COLUMNS, kalshi_candles_to_rows,
                                    kalshi_markets_to_rows, polymarket_history_to_rows,
                                    polymarket_markets_to_rows)

FETCHED = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

POLY_EVENT = {
    "id": "45915", "slug": "brazil-presidential-election", "title": "Brazil Presidential Election",
    "markets": [
        {"id": "601819", "question": "Will Lula win?", "groupItemTitle": "Lula",
         "outcomes": '["Yes", "No"]', "outcomePrices": '["0.405", "0.595"]',
         "clobTokenIds": '["111", "222"]', "startDate": "2025-09-18T20:07:59.727557Z",
         "endDate": "2026-10-04T00:00:00Z", "closed": False, "umaResolutionStatus": None,
         "volumeNum": 11930358.1, "liquidityNum": 352977.48},
        {"id": "9", "question": "Will PT nominate Lula?", "groupItemTitle": None,
         "outcomes": '["Yes", "No"]', "outcomePrices": '["1", "0"]',
         "clobTokenIds": '["333", "444"]', "startDate": "2026-01-01T00:00:00Z",
         "endDate": "2026-08-15T06:00:00Z", "closed": True, "umaResolutionStatus": "resolved",
         "volumeNum": 10.0, "liquidityNum": 0.0},
    ],
}

KALSHI_EVENT = {
    "event_ticker": "KXBRPRES-26", "series_ticker": "KXBRPRES",
    "title": "Brazil Presidential election winner?",
    "markets": [
        {"ticker": "KXBRPRES-26-FBOL", "title": "Will Flávio Bolsonaro win?",
         "yes_sub_title": "Flávio Bolsonaro", "status": "active", "result": "",
         "open_time": "2025-12-05T19:30:00Z", "close_time": "2027-10-25T14:00:00Z",
         "last_price_dollars": "0.5700", "volume_fp": "1071795.75", "open_interest_fp": "417240.80"},
        {"ticker": "KXBRPRES-26-XXX", "title": "Will X win?", "yes_sub_title": "X",
         "status": "settled", "result": "no", "open_time": "2025-12-05T19:30:00Z",
         "close_time": "2026-01-01T00:00:00Z", "last_price_dollars": "0.0000",
         "volume_fp": "5", "open_interest_fp": "0"},
    ],
}


def test_polymarket_markets_to_rows():
    rows = polymarket_markets_to_rows(POLY_EVENT, FETCHED)
    assert [list(r.keys()) for r in rows] == [MARKET_COLUMNS] * 2
    lula, pt = rows
    assert lula["platform"] == "polymarket"
    assert lula["event_id"] == "brazil-presidential-election"
    assert lula["market_id"] == "601819"
    assert lula["outcome"] == "Lula"
    assert lula["yes_token_id"] == "111"
    assert lula["status"] == "open" and lula["result"] == ""
    assert lula["last_price"] == 0.405
    assert lula["volume"] == 11930358.1 and lula["liquidity"] == 352977.48
    assert lula["open_time"] == pd.Timestamp("2025-09-18T20:07:59.727557Z")
    assert lula["fetched_at"] == FETCHED
    assert pt["status"] == "resolved" and pt["result"] == "yes"
    assert pt["outcome"] == "Yes"   # falls back to first outcome when groupItemTitle is missing


def test_polymarket_history_keeps_last_point_per_day():
    hist = {"history": [{"t": 1758240010, "p": 0.59},   # 2025-09-19 00:00:10 UTC
                        {"t": 1758280000, "p": 0.55},   # 2025-09-19 11:06 UTC
                        {"t": 1758326404, "p": 0.485}]} # 2025-09-20
    rows = polymarket_history_to_rows("601819", hist)
    assert [list(r.keys()) for r in rows] == [PRICE_COLUMNS] * 2
    assert [(str(r["date"]), r["price_close"]) for r in rows] == [("2025-09-19", 0.55), ("2025-09-20", 0.485)]
    assert rows[0]["platform"] == "polymarket" and rows[0]["market_id"] == "601819"
    assert rows[0]["price_open"] == 0.55 and rows[0]["yes_bid"] is None


def test_kalshi_markets_to_rows():
    rows = kalshi_markets_to_rows(KALSHI_EVENT, FETCHED)
    assert [list(r.keys()) for r in rows] == [MARKET_COLUMNS] * 2
    fb, xx = rows
    assert fb["platform"] == "kalshi" and fb["event_id"] == "KXBRPRES-26"
    assert fb["market_id"] == "KXBRPRES-26-FBOL" and fb["outcome"] == "Flávio Bolsonaro"
    assert fb["yes_token_id"] == ""
    assert fb["status"] == "open" and fb["result"] == ""
    assert fb["last_price"] == 0.57 and fb["volume"] == 1071795.75 and fb["liquidity"] == 417240.80
    assert fb["close_time"] == pd.Timestamp("2027-10-25T14:00:00Z")
    assert xx["status"] == "resolved" and xx["result"] == "no"


def test_kalshi_candles_to_rows():
    candles = {"candlesticks": [
        {"end_period_ts": 1764997200, "open_interest_fp": "8144.00", "volume_fp": "8476.00",
         "price": {"close_dollars": "0.1700", "high_dollars": "0.2400", "low_dollars": "0.1400",
                   "open_dollars": "0.1400"},
         "yes_ask": {"close_dollars": "0.2200"}, "yes_bid": {"close_dollars": "0.1700"}},
        {"end_period_ts": 1765083600, "open_interest_fp": "9000", "volume_fp": "0",
         "price": {"close_dollars": None, "high_dollars": None, "low_dollars": None, "open_dollars": None},
         "yes_ask": {"close_dollars": "0.2300"}, "yes_bid": {"close_dollars": "0.1800"}},
    ]}
    rows = kalshi_candles_to_rows("KXBRPRES-26-FBOL", candles)
    assert [list(r.keys()) for r in rows] == [PRICE_COLUMNS] * 2
    a, b = rows
    assert str(a["date"]) == "2025-12-06"
    assert a["price_close"] == 0.17 and a["price_high"] == 0.24 and a["yes_ask"] == 0.22
    assert a["volume"] == 8476.0 and a["open_interest"] == 8144.0
    assert b["price_close"] is None and b["yes_bid"] == 0.18
