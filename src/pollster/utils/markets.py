"""Parsers for Polymarket (Gamma/CLOB) and Kalshi API JSON into unified rows."""
import json
from datetime import datetime, timezone

import pandas as pd

MARKET_COLUMNS = ["platform", "event_id", "event_title", "market_id", "question", "outcome",
                  "yes_token_id", "open_time", "close_time", "status", "result", "last_price",
                  "volume", "liquidity", "fetched_at"]
PRICE_COLUMNS = ["platform", "market_id", "date", "price_close", "price_open", "price_high",
                 "price_low", "yes_bid", "yes_ask", "volume", "open_interest"]

KALSHI_STATUS = {"active": "open", "open": "open", "closed": "closed",
                 "settled": "resolved", "finalized": "resolved", "determined": "resolved"}


def _float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts(value) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(ts) else ts


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    try:
        return json.loads(value) if value else []
    except (TypeError, ValueError):
        return []


def _market_row(**kw) -> dict:
    return {col: kw.get(col) for col in MARKET_COLUMNS}


def _price_row(**kw) -> dict:
    return {col: kw.get(col) for col in PRICE_COLUMNS}


def polymarket_markets_to_rows(event: dict, fetched_at: datetime) -> list[dict]:
    rows = []
    for m in event.get("markets") or []:
        outcomes = _json_list(m.get("outcomes"))
        prices = _json_list(m.get("outcomePrices"))
        tokens = _json_list(m.get("clobTokenIds"))
        resolved = m.get("umaResolutionStatus") == "resolved"
        status = "resolved" if resolved else ("closed" if m.get("closed") else "open")
        first_price = _float(prices[0]) if prices else None
        result = ""
        if resolved and first_price is not None:
            result = "yes" if first_price >= 0.999 else ("no" if first_price <= 0.001 else "")
        rows.append(_market_row(
            platform="polymarket", event_id=event.get("slug"), event_title=event.get("title"),
            market_id=str(m.get("id")), question=m.get("question"),
            outcome=m.get("groupItemTitle") or (outcomes[0] if outcomes else ""),
            yes_token_id=str(tokens[0]) if tokens else "",
            open_time=_ts(m.get("startDate")), close_time=_ts(m.get("endDate")),
            status=status, result=result, last_price=first_price,
            volume=_float(m.get("volumeNum")), liquidity=_float(m.get("liquidityNum")),
            fetched_at=fetched_at))
    return rows


def polymarket_history_to_rows(market_id: str, history: dict) -> list[dict]:
    """Keep the last observation of each UTC day."""
    by_day: dict = {}
    for point in history.get("history") or []:
        t, p = point.get("t"), _float(point.get("p"))
        if t is None or p is None:
            continue
        day = datetime.fromtimestamp(int(t), tz=timezone.utc).date()
        by_day[day] = p
    return [_price_row(platform="polymarket", market_id=str(market_id), date=day,
                       price_close=p, price_open=p, price_high=p, price_low=p)
            for day, p in sorted(by_day.items())]


def kalshi_markets_to_rows(event: dict, fetched_at: datetime) -> list[dict]:
    rows = []
    for m in event.get("markets") or []:
        rows.append(_market_row(
            platform="kalshi", event_id=event.get("event_ticker"), event_title=event.get("title"),
            market_id=m.get("ticker"), question=m.get("title"),
            outcome=m.get("yes_sub_title") or m.get("subtitle") or "",
            yes_token_id="",
            open_time=_ts(m.get("open_time")), close_time=_ts(m.get("close_time")),
            status=KALSHI_STATUS.get((m.get("status") or "").lower(), m.get("status") or ""),
            result=(m.get("result") or "").lower(),
            last_price=_float(m.get("last_price_dollars")),
            volume=_float(m.get("volume_fp")), liquidity=_float(m.get("open_interest_fp")),
            fetched_at=fetched_at))
    return rows


def kalshi_candles_to_rows(ticker: str, candles: dict) -> list[dict]:
    rows = []
    for c in candles.get("candlesticks") or []:
        ts = c.get("end_period_ts")
        if ts is None:
            continue
        price = c.get("price") or {}
        rows.append(_price_row(
            platform="kalshi", market_id=ticker,
            date=datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
            price_close=_float(price.get("close_dollars")), price_open=_float(price.get("open_dollars")),
            price_high=_float(price.get("high_dollars")), price_low=_float(price.get("low_dollars")),
            yes_bid=_float((c.get("yes_bid") or {}).get("close_dollars")),
            yes_ask=_float((c.get("yes_ask") or {}).get("close_dollars")),
            volume=_float(c.get("volume_fp")), open_interest=_float(c.get("open_interest_fp"))))
    return rows
