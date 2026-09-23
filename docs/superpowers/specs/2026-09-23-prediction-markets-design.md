# Mercados de previsao (Kalshi e Polymarket) — design

Data: 2026-09-23. Objetivo: **guardar** os dados dos mercados de previsao sobre a eleicao
brasileira de 2026 para analises futuras. Nada da analise ou dos relatorios atuais usa esses dados.

## Decisoes

- Mesma base: `data/parquet/` + `pollster.duckdb`, tabelas com prefixo `pm_`.
- Snapshot bruto das APIs em `data/raw/prediction_markets/<YYYY-MM-DD>/` (JSON), para
  reparsear se o esquema mudar. Versionado no git (pequeno).
- Comando `pollster fetch-markets [--as-of YYYY-MM-DD]`: sempre baixa tudo de novo (o
  historico e retroativo nas duas APIs) e substitui as tabelas/parquets.
- Listas explicitas de eventos/series em `config.py` (`POLYMARKET_EVENT_SLUGS`,
  `KALSHI_SERIES_TICKERS`), verificadas em 2026-09-23. Extensivel para ciclos futuros.

## Fontes

Polymarket (sem auth):
- `GET https://gamma-api.polymarket.com/events/slug/{slug}` → evento com `markets[]`
  (`id, question, groupItemTitle, outcomes, outcomePrices, clobTokenIds, startDate, endDate,
  closed, volumeNum, liquidityNum, conditionId, umaResolutionStatus`).
- `GET https://clob.polymarket.com/prices-history?market={clobTokenId}&interval=max&fidelity=1440`
  → `{history: [{t, p}]}` (t = epoch s, p = preco do token YES = probabilidade).

Kalshi (sem auth):
- `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={S}&with_nested_markets=true`
  → eventos e mercados da serie (`ticker, event_ticker, yes_sub_title, status, result,
  open_time, close_time, expiration_time, ...`).
- `GET .../series/{S}/markets/{ticker}/candlesticks?start_ts&end_ts&period_interval=1440`
  → candles diarios (`end_period_ts, price{open,high,low,close,mean}_dollars, yes_bid, yes_ask,
  volume_fp, open_interest_fp`).

## Esquema unificado

`pm_markets` (uma linha por mercado):

| coluna | tipo | nota |
|---|---|---|
| platform | str | `polymarket` / `kalshi` |
| event_id | str | slug (Polymarket) / event_ticker (Kalshi) |
| event_title | str | |
| market_id | str | id numerico (Polymarket) / ticker (Kalshi) |
| question | str | |
| outcome | str | candidato/desfecho (`groupItemTitle` / `yes_sub_title`) |
| yes_token_id | str | clobTokenId do YES (Polymarket) ou vazio |
| open_time, close_time | timestamp | |
| status | str | `open`/`closed`/`resolved` normalizado |
| result | str | `yes`/`no`/vazio |
| last_price | float | prob. atual do YES (0-1) |
| volume | float | em USD/contratos conforme a plataforma |
| liquidity | float | Polymarket; open interest atual na Kalshi |
| fetched_at | timestamp | |

`pm_prices_daily` (uma linha por mercado e dia):

| coluna | tipo |
|---|---|
| platform, market_id | str |
| date | date |
| price_close | float (0-1) |
| price_open, price_high, price_low | float (Kalshi; Polymarket = close) |
| yes_bid, yes_ask | float (Kalshi) |
| volume, open_interest | float (Kalshi) |

## Componentes

- `src/pollster/utils/markets.py`: funcoes puras `polymarket_markets_to_rows(event_json, fetched_at)`,
  `polymarket_history_to_rows(market_id, history_json)`, `kalshi_markets_to_rows(events_json, fetched_at)`,
  `kalshi_candles_to_rows(ticker, candles_json)`.
- `src/pollster/stages/fetch_markets.py`: `download_*` (requests) + `fetch_markets(data_dir, as_of)`
  que grava raw JSON, monta os DataFrames, salva `pm_markets.parquet`, `pm_prices_daily.parquet`
  e registra as tabelas.
- CLI `fetch-markets`.
- Testes: parsers com fixtures JSON pequenas; fetch com `download_*` mockados.

## Fora de escopo

Usar os dados na projecao/relatorio; agendamento automatico; outros paises.
