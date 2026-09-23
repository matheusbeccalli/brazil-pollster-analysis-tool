# Prediction Markets Storage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store Kalshi and Polymarket markets and daily price history about the 2026 Brazilian election in the existing DuckDB/parquet base, for future analyses (no use in the current reports).

**Architecture:** Pure parsers in `utils/markets.py` turn raw API JSON into two unified row shapes (markets, daily prices). `stages/fetch_markets.py` downloads (event/series lists from `config.py`), writes raw JSON snapshots, builds the DataFrames and persists `pm_markets` / `pm_prices_daily`. CLI `fetch-markets`.

**Tech Stack:** requests, pandas, duckdb, pytest. Spec: `docs/superpowers/specs/2026-09-23-prediction-markets-design.md`.

---

### Task 1: Config

**Files:** Modify `src/pollster/config.py`; Test `tests/test_config.py`.

- [ ] Test: `POLYMARKET_EVENT_SLUGS` contains `"brazil-presidential-election"`; `KALSHI_SERIES_TICKERS` contains `"KXBRPRES"`; URLs defined.
- [ ] Implement:

```python
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_EVENT_SLUGS = [
    "brazil-presidential-election",
    "brazil-presidential-election-first-round-winner",
    "brazil-presidential-election-first-round-2nd-place",
    "brazil-presidential-election-first-round-3rd-place",
    "which-candidates-will-advance-to-brazils-presidential-runoff",
    "will-any-presidential-candidate-win-outright-in-the-first-round-of-the-brazil-election",
    "brazil-presidential-election-first-round-lula-da-silva-vote-share",
    "who-will-trump-endorse-for-president-of-brazil-20260803210809",
    "lula-participates-in-debate-before-first-round",
    "will-the-workers-party-nominate-lula-for-president-of-brazil-by-august-15",
]
KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES_TICKERS = [
    "KXBRPRES", "KXBRPRES1R", "KXBRAZILPRES1R", "KXBRPRESADVANCE", "KXBRPRES1MOV",
    "KXBRPRESIDENT2", "KXBRPRESIDENT3", "KXBRPRESIDENT4", "KXBRPRESIDENT5",
    "KXVOTEBR1", "KXBRBALLOT", "KXTRUMPFLAVIO",
    "KXBRSENMOSTSEATS", "KXBRAZILSENATE", "KXBRDEP", "KXBRGOVMOSTSEATS", "KXDFGOV",
]
KALSHI_HISTORY_START = date(2025, 1, 1)
```

- [ ] Commit `feat(config): prediction market sources`.

### Task 2: Parsers (`src/pollster/utils/markets.py`)

**Test `tests/test_markets.py`** with small inline JSON fixtures. Functions and unified columns:

```python
MARKET_COLUMNS = ["platform", "event_id", "event_title", "market_id", "question", "outcome",
                  "yes_token_id", "open_time", "close_time", "status", "result", "last_price",
                  "volume", "liquidity", "fetched_at"]
PRICE_COLUMNS = ["platform", "market_id", "date", "price_close", "price_open", "price_high",
                 "price_low", "yes_bid", "yes_ask", "volume", "open_interest"]

def polymarket_markets_to_rows(event: dict, fetched_at) -> list[dict]
def polymarket_history_to_rows(market_id: str, history: dict) -> list[dict]   # {history:[{t,p}]}; keep last point per UTC date
def kalshi_markets_to_rows(event: dict, fetched_at) -> list[dict]             # event with nested markets[]
def kalshi_candles_to_rows(ticker: str, candles: dict) -> list[dict]          # {candlesticks:[...]}
```

Mapping rules: Polymarket `status` = `resolved` if `umaResolutionStatus == "resolved"`, else `closed` if `closed`, else `open`; `result` = `yes` if resolved and first outcomePrice == "1", `no` if == "0"; `last_price` = first outcomePrice; `yes_token_id` = first clobTokenId. Kalshi `status`: `active`→`open`, `closed`→`closed`, `settled`/`finalized`→`resolved`; `result` from `result`; `last_price` from `last_price_dollars`; `volume` from `volume_fp`; `liquidity` from `open_interest_fp`.

- [ ] Write tests → fail → implement → pass → commit `feat: prediction market parsers`.

### Task 3: Fetch stage + CLI

**Files:** Create `src/pollster/stages/fetch_markets.py`; Modify `cli.py`; Test `tests/test_fetch_markets.py` (mock `download_polymarket_event`, `download_polymarket_history`, `download_kalshi_series`, `download_kalshi_candles`).

`fetch_markets(data_dir, as_of=None)`:
1. `raw_dir = data_dir / "raw" / "prediction_markets" / as_of.isoformat()`; write `polymarket_<slug>.json`, `polymarket_history_<market_id>.json`, `kalshi_<series>.json`, `kalshi_candles_<ticker>.json`.
2. Build DataFrames with parsers; `pm_markets.parquet`, `pm_prices_daily.parquet`; register tables `pm_markets`, `pm_prices_daily`.
3. Kalshi candles: `start_ts` = `KALSHI_HISTORY_START`, `end_ts` = now, `period_interval=1440`; skip markets with no candles.
4. Failures on one series/event log a warning and continue (a missing slug must not abort the run).

- [ ] Tests → implement → run `pollster fetch-markets` for real → commit with parquets and raw JSON.

### Task 4: README + memory

- [ ] README section "Mercados de previsao (Kalshi e Polymarket)": command, tables, raw dir, note that nothing uses them yet. Commit `docs: prediction markets`.
