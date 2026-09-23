# Historico presidencial completo e correcao de vies — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the Poder360 aggregator backend as the source of national presidential polls for 2002-2026, fix candidate matching so 2002-2014 races enter the accuracy analysis, and add a bias-adjusted variant to the 2026 projection.

**Architecture:** `fetch_poder360` (generalized `fetch2026`) writes `poder360_presidential`; `assemble` merges it with Base dos Dados gubernatorial rows; matcher uses token-set similarity with party tiebreak; `project` computes recency-weighted EAM, sigma and global left-right margin bias, producing raw and bias-adjusted rounds; report shows both.

**Tech Stack:** unchanged. Spec: `docs/superpowers/specs/2026-09-23-historico-presidencial-e-vies-design.md`.

---

### Task 1: Matcher (`utils/candidates.py`)

- [ ] Tests (`tests/test_candidates.py`): "DILMA" ↔ "Dilma Rousseff" → match; "SERRA" ↔ "José Serra"; "LULA" ↔ "LUIZ INACIO LULA DA SILVA" now matches (update old test); "BOLSONARO" with officials "Jair Bolsonaro"/"Flávio Bolsonaro" and party PL/PSL → party breaks the tie; "SIMONE TEBET" vs Lula → None; single-token names shorter than 4 chars never fuzzy-match.
- [ ] Implement: exact → candidates with `fuzz.token_set_ratio >= 85` (skip when the shorter normalized name has < 4 chars); if one best → return; if tie and `poll_party`/`official_parties` → the tied candidate with that party; else first tied; else party-unique fallback.
- [ ] `assemble._select_scenario`: pass `poll_party=top2_parties[official_name]`.
- [ ] Commit `fix: match ballot names to full poll names (token-set + party tiebreak)`.

### Task 2: Config + `fetch_poder360`

- [ ] Config: rename `POLLSTER_ALIASES_2026` → `POLLSTER_ALIASES_PODER360` (add `"Paraná": "Paraná Pesquisas"`, `"Ibope Inteligência"` already merged); `PODER360_YEARS = sorted(ELECTIONS)`; replace `PROJECTION_HISTORY_YEARS` by `PROJECTION_HISTORY_HALF_LIFE_YEARS = 8.0`, `PROJECTION_BASE_YEAR = 2022`; add `PROJECTION_BIAS_CORRECTION = True`.
- [ ] `stages/fetch_poder360.py`: `download_polls(turno, year)` (as today) and `fetch_poder360(data_dir, years=None, force=False)` → `polls_to_frame(raw, turno)` + column `ano=year` inserted first; concat; `poder360_presidential.parquet` + table; then `CREATE OR REPLACE TABLE polls_2026 AS SELECT * FROM poder360_presidential WHERE ano = 2026` and `polls_2026.parquet`. `fetch2026.py` removed; tests moved to `tests/test_fetch_poder360.py` (mock `download_polls(turno, year)`).
- [ ] CLI: `fetch-poder360 --years 2002,2026 --force`; `fetch-2026` kept as thin alias (`years=[2026]`).
- [ ] Run for real (`pollster fetch-poder360 --force`), commit parquet.

### Task 3: Assemble merge

- [ ] Test: db with `poder360_polls` (fixture, includes one national presidential 2022 row set) **and** `poder360_presidential` (converted 2014 rows Dilma/Aécio) → `polls_vs_actual` has 2014 presidente rows and the 2022 national rows come from the backend table only (no duplicates: count per pollster/race = 1).
- [ ] Implement `_load_polls(con)`: BdD rows; if `poder360_presidential` exists (check `information_schema.tables`), drop BdD rows where `LOWER(cargo)='presidente' AND sigla_uf IS NULL`, convert backend rows with `backend_to_polls_schema(df)` (in `utils/poder360.py`) and concat.
- [ ] Regenerate: `pollster assemble && pollster analyze --since 2000 && pollster report`; commit data.

### Task 4: Projection history + bias

- [ ] Tests (`tests/test_project.py`): `history_weight(year)`; `pollster_accuracy` = recency-weighted mean EAM across years; `historical_margin_bias` sign: polls overstating the left → positive; `project_election` returns `round1_adj`/`round2_adj` and summary has `variant`.
- [ ] Implement in `project.py`:
  - `history_weight(year) = 0.5 ** ((PROJECTION_BASE_YEAR - year) / HALF_LIFE)`
  - `pollster_accuracy`: `SELECT pollster_display_name, year, AVG(mae_top2)` → weighted average per pollster.
  - `historical_margin_bias`: per (year, round): `AVG(predicted_margin_lr) - AVG(actual_margin_lr)` where `_lr` = left minus right using `candidate_*_leaning` (sign flip if candidate 1 is right and 2 is left; races without a left/right pair skipped) → weighted mean.
  - `adjust_estimate(est, bias)`: find top-2 leanings from `PARTY_LEANING`; shift left candidate by `-bias/2`, right by `+bias/2`; renormalize.
  - `project_round(..., bias=0.0)`; `project_election` builds raw and adjusted rounds; `_persist` writes `variant`.
- [ ] Report: summary lists both variants; per round, a two-row-per-candidate table (`Variante`) and two bar charts; methodology gains a per-election table of historical margin errors (`historical_bias_table(con)` returning year, round, left, right, predicted, actual, error) and the bias value.
- [ ] Regenerate report + PDF, commit.

### Task 5: README + memory

- [ ] README: new command, source note (backend covers 2002-2026), bias variant explanation. Commit.
