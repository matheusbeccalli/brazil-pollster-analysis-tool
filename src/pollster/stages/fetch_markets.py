"""Stage: store Kalshi and Polymarket markets about the Brazilian election (raw + tables)."""
import json
import pathlib
import time
from datetime import date, datetime, timezone

import click
import pandas as pd
import requests

from pollster import config
from pollster.db import get_connection, register_parquet
from pollster.utils.markets import (MARKET_COLUMNS, PRICE_COLUMNS, kalshi_candles_to_rows,
                                    kalshi_markets_to_rows, polymarket_history_to_rows,
                                    polymarket_markets_to_rows)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pollster-tool", "Accept": "application/json"}


def _get(url: str, params: dict | None = None) -> dict | list:
    resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def download_polymarket_event(slug: str) -> dict:
    return _get(f"{config.POLYMARKET_GAMMA_URL}/events/slug/{slug}")


def download_polymarket_history(token_id: str) -> dict:
    return _get(f"{config.POLYMARKET_CLOB_URL}/prices-history",
                {"market": token_id, "interval": "max", "fidelity": 1440})


def download_kalshi_series(series_ticker: str) -> list[dict]:
    events, cursor = [], None
    while True:
        params = {"series_ticker": series_ticker, "with_nested_markets": "true", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = _get(f"{config.KALSHI_API_URL}/events", params)
        events.extend(data.get("events") or [])
        cursor = data.get("cursor")
        if not cursor:
            return events


def download_kalshi_candles(series_ticker: str, ticker: str, start_ts: int, end_ts: int) -> dict:
    return _get(f"{config.KALSHI_API_URL}/series/{series_ticker}/markets/{ticker}/candlesticks",
                {"start_ts": start_ts, "end_ts": end_ts, "period_interval": 1440})


def _dump(raw_dir: pathlib.Path, name: str, payload) -> None:
    (raw_dir / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def fetch_markets(data_dir: pathlib.Path, as_of: date | None = None) -> None:
    as_of = as_of or date.today()
    fetched_at = datetime.now(timezone.utc)
    raw_dir = data_dir / "raw" / "prediction_markets" / as_of.isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)
    markets, prices = [], []

    for slug in config.POLYMARKET_EVENT_SLUGS:
        try:
            event = download_polymarket_event(slug)
        except Exception as exc:  # one missing event must not abort the run
            click.echo(f"  ! polymarket {slug}: {exc}")
            continue
        _dump(raw_dir, f"polymarket_{slug}", event)
        rows = polymarket_markets_to_rows(event, fetched_at)
        markets.extend(rows)
        for row in rows:
            if not row["yes_token_id"]:
                continue
            try:
                hist = download_polymarket_history(row["yes_token_id"])
            except Exception as exc:
                click.echo(f"  ! polymarket history {row['market_id']}: {exc}")
                continue
            _dump(raw_dir, f"polymarket_history_{row['market_id']}", hist)
            prices.extend(polymarket_history_to_rows(row["market_id"], hist))
        click.echo(f"  polymarket {slug}: {len(rows)} markets")

    start_ts = int(datetime.combine(config.KALSHI_HISTORY_START, datetime.min.time(),
                                    tzinfo=timezone.utc).timestamp())
    end_ts = int(time.time())
    for series in config.KALSHI_SERIES_TICKERS:
        try:
            events = download_kalshi_series(series)
        except Exception as exc:
            click.echo(f"  ! kalshi {series}: {exc}")
            continue
        _dump(raw_dir, f"kalshi_{series}", events)
        n = 0
        for event in events:
            rows = kalshi_markets_to_rows(event, fetched_at)
            markets.extend(rows)
            n += len(rows)
            for row in rows:
                try:
                    candles = download_kalshi_candles(series, row["market_id"], start_ts, end_ts)
                except Exception as exc:
                    click.echo(f"  ! kalshi candles {row['market_id']}: {exc}")
                    continue
                _dump(raw_dir, f"kalshi_candles_{row['market_id']}", candles)
                prices.extend(kalshi_candles_to_rows(row["market_id"], candles))
        click.echo(f"  kalshi {series}: {n} markets")

    markets_df = pd.DataFrame(markets, columns=MARKET_COLUMNS)
    prices_df = pd.DataFrame(prices, columns=PRICE_COLUMNS)
    for col in ("open_time", "close_time", "fetched_at"):
        markets_df[col] = pd.to_datetime(markets_df[col], utc=True)
    prices_df["date"] = pd.to_datetime(prices_df["date"])

    parquet_dir = data_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    con = get_connection(data_dir)
    for name, df in (("pm_markets", markets_df), ("pm_prices_daily", prices_df)):
        path = parquet_dir / f"{name}.parquet"
        df.to_parquet(path, index=False)
        register_parquet(con, name, path)
    con.close()
    click.echo(f"Stored {len(markets_df)} markets and {len(prices_df)} daily prices "
               f"(raw JSON in {raw_dir}).")
