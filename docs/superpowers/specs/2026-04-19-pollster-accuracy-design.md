# Brazilian Election Pollster Accuracy Analysis — Design Spec

## Overview

A Python CLI tool that ranks Brazilian polling institutes by prediction accuracy, comparing their final pre-election polls against official TSE election results (valid votes). Covers presidential and gubernatorial races across 2014, 2018, and 2022 (both rounds). Data is downloaded once from Base dos Dados and stored locally in a DuckDB database for fast, reproducible analysis.

## Investigation Findings

Before finalizing the design, we investigated all practical data sources. The conclusions:

- **TSE Portal (`pesqele-divulgacao.tse.jus.br`) has no JSON API** — it's a legacy JSF/PrimeFaces server-rendered app. Scraping it requires stateful browser automation (ViewState tokens, JSESSIONID). Results capped at 50 per query.
- **TSE poll result PDFs vary wildly across pollsters.** The `pindograma/pdf-poll-parser` project built pollster-specific rule-based parsers for 6 institutes covering 2012-2018, then **abandoned automation** and switched to manual data entry for 2020 and 2022. Automated PDF extraction at scale is impractical.
- **Poder360's direct API is paywalled** (requires Poder Monitor subscription).
- **Base dos Dados mirrors Poder360's poll data for free** on Google BigQuery public datasets. Same data, same schema, no subscription. Coverage 2000-2022, includes president and governor, all pollsters, all states, with candidate percentages, scenarios, pollster names, sample sizes, and margin of error already normalized.
- **Base dos Dados also hosts official TSE election results** at `br_tse_eleicoes.resultados_candidato` (coverage 1994-2022).

This means the entire extraction problem is solved: two BigQuery datasets contain 100% of what we need, pre-parsed and normalized.

## Decisions Made

- **Approach:** Download pre-parsed data from Base dos Dados (Poder360 poll data + TSE official results) once, store locally in DuckDB. No scraping, no PDF parsing, no LLM extraction.
- **Local storage:** DuckDB database file (`data/pollster.duckdb`) with tables backed by Parquet files. Portable, queryable with SQL, fast.
- **Output:** Static HTML report (single self-contained file).
- **Pollster identity:** `instituto` string column from Poder360 data. Optional override/merge table in config for known lineages (e.g., IBOPE → Ipec). We also store each poll's `numero_registro` (TSE protocol) for cross-referencing.
- **Poll selection:** Last poll per pollster per race, regardless of days before election. Equal weight.
- **Bias analysis:** Party-based left/right classification via hardcoded party-to-leaning map.
- **Pipeline design:** Re-runnable staged pipeline. Adding a future election year requires only re-running `fetch` (once Base dos Dados covers that year) plus config additions.
- **CLI:** Click with subcommands per stage, plus `pollster query` for ad-hoc SQL.

---

## Project Structure

```
brazil-pollster-analysis-tool/
├── pyproject.toml
├── src/
│   └── pollster/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI with subcommands
│       ├── config.py               # Election dates, party/leaning map, pollster merges
│       ├── db.py                   # DuckDB connection helper
│       ├── stages/
│       │   ├── __init__.py
│       │   ├── fetch.py            # Stage 1: download from Base dos Dados → Parquet + DuckDB
│       │   ├── assemble.py         # Stage 2: filter, rebase, join into unified dataset
│       │   ├── analyze.py          # Stage 3: compute metrics, aggregate by pollster
│       │   └── report.py           # Stage 4: generate HTML report
│       └── utils/
│           ├── __init__.py
│           ├── normalize.py        # Pollster name normalization + merges
│           ├── rebase.py           # Rebase poll numbers to valid votes
│           └── candidates.py       # Fuzzy match poll candidates to official candidates
├── data/                           # Git-ignored, all pipeline artifacts
│   ├── parquet/                    # Raw data downloaded from Base dos Dados
│   │   ├── poder360_pesquisas.parquet
│   │   └── tse_resultados_candidato.parquet
│   ├── pollster.duckdb             # Local DuckDB database with all tables
│   └── reports/                    # Generated HTML reports
└── tests/
```

**Why DuckDB + Parquet:**
- Parquet files are the portable source of truth — commit/archive/share them independently of the code.
- DuckDB reads Parquet natively with zero ETL overhead and gives you a full SQL engine over them.
- All pipeline intermediate tables (assembled, analyzed) become views or materialized tables in the same DuckDB file.
- `pollster query "SELECT * FROM polls WHERE ..."` enables ad-hoc exploration without writing Python.

---

## Stage 1: Fetch (`pollster fetch`)

Downloads two datasets from Base dos Dados and stores them locally.

### Approach

**Primary method: `basedosdados` Python package**

The `basedosdados` PyPI package pulls data directly from Google BigQuery public datasets. It handles auth for free-tier Google Cloud accounts (1 TB/month of free BigQuery queries — our data is a few MB, cost is zero).

```python
import basedosdados as bd
polls_df = bd.read_sql(
    "SELECT * FROM `basedosdados.br_poder360_pesquisas.microdados`",
    billing_project_id="my-project"
)
```

**Fallback method: direct download of Base dos Dados storage buckets**

If the Python package has issues, Base dos Dados also exposes Parquet files via public GCS URLs (discoverable through their web UI). This path requires no Google Cloud credentials — just HTTP GETs.

### Data fetched

**1. Poll data** — `basedosdados.br_poder360_pesquisas.microdados`

Filter at query time to: `ano IN (2014, 2018, 2022) AND cargo IN ('PRESIDENTE', 'GOVERNADOR')`.

Columns captured:
- `id_pesquisa`, `id_cenario`, `id_candidato_poder360` — unique row keys
- `ano`, `data`, `data_referencia`, `turno` — temporal
- `cargo`, `sigla_uf`, `nome_municipio` — race identity
- `instituto`, `contratante`, `orgao_registro`, `numero_registro` — pollster identity + TSE registration
- `quantidade_entrevistas`, `margem_mais`, `margem_menos`, `tipo`, `tipo_voto` — methodology
- `descricao_cenario` — scenario label (e.g., "cenário 1", "cenário estimulado")
- `nome_candidato`, `sigla_partido` — candidate
- `condicao` — candidate status flag
- `percentual` — voting intention percentage (the core number)

Saved as `data/parquet/poder360_pesquisas.parquet`.

**2. Official election results** — `basedosdados.br_tse_eleicoes.resultados_candidato`

Filter at query time to: `ano IN (2014, 2018, 2022) AND cargo IN ('PRESIDENTE', 'GOVERNADOR')`.

Columns captured:
- `ano`, `turno`, `tipo_eleicao`, `sigla_uf`
- `cargo`, `numero_partido`, `sigla_partido`, `numero_candidato`, `sequencial_candidato`
- `id_candidato_bd` — Base dos Dados canonical candidate ID
- `resultado` — election result (elected, not elected, etc.)
- `votos` — vote count (aggregated to state × round × candidate level; presidential rows have `sigla_uf = 'BR'`)

Saved as `data/parquet/tse_resultados_candidato.parquet`.

### Register in DuckDB

After downloading both Parquet files, create/update `data/pollster.duckdb`:

```sql
CREATE OR REPLACE TABLE poder360_polls AS SELECT * FROM 'data/parquet/poder360_pesquisas.parquet';
CREATE OR REPLACE TABLE tse_results AS SELECT * FROM 'data/parquet/tse_resultados_candidato.parquet';
```

### Idempotency

- `fetch` skips the download if the Parquet files already exist, unless `--force` is passed.
- `--year 2022` downloads only a specific year.
- Fetch logs row counts and file sizes to give the user confidence the data arrived.

---

## Stage 2: Assemble (`pollster assemble`)

Transforms the raw tables into a single analysis-ready `polls_vs_actual` table.

### Step 1: Build `actual_results` view

From `tse_results`, compute valid-vote percentages per candidate per race:

- `tse_results` rows are at the municipality level (`id_municipio`). Sum `votos` to the race level by grouping on (`ano`, `turno`, `cargo`, `sigla_uf`, candidate key). For presidential, `sigla_uf = 'BR'` is used in Poder360 poll data; check whether TSE results use state rows for presidential or a national aggregate — if the former, sum across states to national.
- Compute `votos_validos_pct = votos / sum(votos) over race_group * 100`
- Rank candidates by `votos` within each race (descending); take the **top-2 by vote count** as the "race finalists". This definition holds regardless of whether round 2 occurred: the top two finishers in round 1 are the finalists even if the winner got > 50% and round 2 was not triggered.
- Join `br_tse_eleicoes.candidatos` if needed to resolve `nome_candidato` from `sequencial_candidato` / `id_candidato_bd` (check schema during implementation).
- Output: one row per (race, candidate-rank-1-or-2) with `nome_candidato`, `sigla_partido`, `votos`, `votos_validos_pct`

### Step 2: Identify "final poll per pollster per race"

From `poder360_polls`, for each (`ano`, `turno`, `cargo`, `sigla_uf`, `instituto`) combination:
- Filter on `data` ≤ election day for that round (election dates from config). `data` is treated as the poll's effective date (typically publication / fieldwork end). If first-pass validation against known polls shows `data_referencia` is a better fit for "when the poll reflected public opinion," we'll switch — the choice is encapsulated in one query and easy to flip.
- Keep only the poll with the latest `data` per pollster × race
- If a poll has multiple scenarios (`id_cenario`), see step 3 for scenario selection

### Step 3: Scenario selection within a poll

A single `id_pesquisa` may have multiple scenarios. Selection rule:
- Compute the set of top-2 official candidates for the race (from step 1)
- Filter the poll's scenarios to those where BOTH top-2 finalists appear as `nome_candidato`
- If multiple scenarios qualify, prefer the one with the most candidates (most complete lineup)
- If none qualify, skip this pollster × race (logged as "no matching scenario")

### Step 4: Candidate name matching

Poll `nome_candidato` values are matched to official `nome_candidato` values via:
1. Exact match after normalization (uppercase, strip accents, strip punctuation)
2. Fuzzy match (Jaro-Winkler ≥ 0.92)
3. Party-based fallback: if a poll candidate shares `sigla_partido` with an official candidate and the name is partial (e.g., "LULA" vs "LUIZ INÁCIO LULA DA SILVA"), match by party

Unmatched candidates are logged and excluded. If either of the top-2 can't be matched, the poll is excluded.

### Step 5: Rebase poll percentages to valid votes

Within the selected scenario of each poll:
```
poll_valid_pct_i = poll_raw_pct_i / sum(all_candidate_raw_pcts_in_scenario) * 100
```
The denominator is the sum of ALL candidates' raw percentages in the scenario (not just top-2). This removes undecided/blank/null from the base. Then only the top-2 rebased percentages are used downstream.

### Step 6: Pollster normalization

- Start with `instituto` string from Poder360 (already partially normalized)
- Apply config-driven overrides:
  - **Merges:** `{"IBOPE": "IBOPE/Ipec", "Ipec": "IBOPE/Ipec"}` — multiple source strings → one display name
  - **Aliases:** `{"Datafolha Instituto de Pesquisas": "Datafolha"}` — string cleanups
- Output column: `pollster_display_name`

### Step 7: Assign party leaning

Using the config party-to-leaning map, add `leaning` for each candidate (left / center / right / unknown).

### Output

Single DuckDB table `polls_vs_actual`:

| Column | Description |
|---|---|
| `year`, `round`, `cargo`, `sigla_uf` | Race identity |
| `pollster_display_name`, `instituto_raw` | Pollster |
| `numero_registro` | TSE registration number |
| `poll_date` (from `data`), `sample_size` (from `quantidade_entrevistas`), `margin_plus`, `margin_minus` | Poll methodology |
| `cenario_descricao` | Scenario used |
| `candidate_1_name`, `candidate_1_party`, `candidate_1_leaning` | Top-2 finalist 1 |
| `candidate_1_poll_raw_pct`, `candidate_1_poll_valid_pct`, `candidate_1_actual_valid_pct` | Poll vs. actual for finalist 1 |
| `candidate_2_name`, `candidate_2_party`, `candidate_2_leaning` | Top-2 finalist 2 |
| `candidate_2_poll_raw_pct`, `candidate_2_poll_valid_pct`, `candidate_2_actual_valid_pct` | Poll vs. actual for finalist 2 |

Stored as a materialized DuckDB table and also written to `data/parquet/polls_vs_actual.parquet` for portability.

---

## Stage 3: Analyze (`pollster analyze`)

Operates on `polls_vs_actual`. Produces several output tables in DuckDB.

### Per-poll metrics (`poll_level_metrics`)

One row per poll observation, computed via SQL:
- `error_1 = candidate_1_poll_valid_pct - candidate_1_actual_valid_pct` (signed)
- `error_2 = candidate_2_poll_valid_pct - candidate_2_actual_valid_pct` (signed)
- `abs_error_1 = |error_1|`, `abs_error_2 = |error_2|`
- `mae_top2 = (abs_error_1 + abs_error_2) / 2` — Mosteller Measure 3
- `predicted_margin = candidate_1_poll_valid_pct - candidate_2_poll_valid_pct`
- `actual_margin = candidate_1_actual_valid_pct - candidate_2_actual_valid_pct`
- `margin_error = |predicted_margin - actual_margin|`
- `left_signed_error`, `right_signed_error` — filled based on each candidate's `leaning`

### Aggregated pollster rankings (`pollster_rankings`)

For each `pollster_display_name`:
- `n_races` — observation count
- `mean_mae`, `median_mae`
- `mean_margin_error`
- `mean_left_bias` — mean of `left_signed_error` across observations where a left-leaning candidate appeared in top-2
- `mean_right_bias` — analogous for right
- `mae_ci_low`, `mae_ci_high` — bootstrap 95% CI on mean MAE (10,000 resamples of the pollster's race-level MAEs, 2.5th and 97.5th percentiles). Computed in Python using numpy (DuckDB doesn't natively bootstrap), then loaded back as a table.

### Breakdown views

Same aggregations partitioned by:
- `pollster_rankings_by_year` — partition on `year`
- `pollster_rankings_by_round` — partition on `round`
- `pollster_rankings_by_race_type` — partition on `cargo`

Each is a materialized DuckDB table AND a Parquet export in `data/parquet/`.

---

## Stage 4: Report (`pollster report`)

Reads analysis tables and generates a self-contained HTML file. Charts via matplotlib (embedded as SVG). No JavaScript.

### Report sections

1. **Executive summary** — top 5 most accurate pollsters by mean MAE, headline finding, total polls and races analyzed, data source attribution (Base dos Dados / Poder360 / TSE).
2. **Overall pollster ranking table** — sorted by mean MAE. Columns: rank, pollster, N races, mean MAE, median MAE, 95% CI, mean margin error, left bias, right bias. Color-coded green (low) to red (high). Footnote for pollsters with N < 3.
3. **Per-election breakdown** — sub-tables for 2014, 2018, 2022.
4. **Presidential vs. gubernatorial split** — side-by-side performance comparison.
5. **Round 1 vs. Round 2 split** — accuracy by round.
6. **Charts:**
   - Bar chart: mean MAE with bootstrap 95% CI error bars
   - Scatter plot: predicted margin vs. actual margin, colored by pollster, 45-degree reference line
   - Heatmap: pollster × election year mean MAE
7. **Methodology notes** — data provenance, rebasing formula, poll selection rule, pollster merge rationale, caveats.

### Styling

Minimal inline CSS, monochrome-friendly palette. Default sort: MAE ascending.

### Output

`data/reports/pollster_accuracy_report.html` — single self-contained file.

---

## Ad-hoc Query (`pollster query`)

Convenience subcommand for ad-hoc SQL against the local DuckDB:

```bash
pollster query "SELECT pollster_display_name, AVG(mae_top2) FROM poll_level_metrics WHERE year=2022 GROUP BY 1 ORDER BY 2"
pollster query --sql-file analysis.sql
```

Prints results as a formatted table. Supports `--format csv|json|parquet` for export.

---

## Configuration (`config.py`)

All hardcoded domain knowledge in one place:

- **Election dates:** year → {round_1_date, round_2_date} — used for the "poll before election day" filter
- **Pollster merges:** `{raw_name: canonical_name}` dict for known lineages (e.g., IBOPE/Ipec)
- **Pollster display aliases:** `{raw_name: clean_name}` for cosmetic cleanups
- **Party-to-leaning map:** `{party_abbr: "left" | "center" | "right"}`
- **Base dos Dados config:**
  - BigQuery project IDs / dataset IDs (in case they change)
  - Billing project ID placeholder (user provides their own GCP project)

### Adding a Future Election (e.g., 2026)

1. Wait for Base dos Dados to update `br_poder360_pesquisas.microdados` and `br_tse_eleicoes.resultados_candidato` with 2026 data
2. Add 2026 dates to `config.py`
3. Add any new pollsters / party mappings
4. Run `pollster fetch --force` to re-download, then `pollster run` for full pipeline

---

## Tech Stack

- **Python 3.10+**
- **basedosdados** — Python package for downloading from BigQuery public datasets
- **google-cloud-bigquery** — transitive dependency
- **duckdb** — local analytics database
- **pandas** — data manipulation
- **pyarrow** — Parquet I/O
- **numpy** — bootstrap CIs
- **matplotlib** — charts
- **click** — CLI framework
- **rapidfuzz** — fuzzy candidate name matching (faster than FuzzyWuzzy)

---

## Pipeline Invariants

- Each stage is idempotent: re-running doesn't re-do completed work unless `--force` is passed.
- Parquet files in `data/parquet/` are the portable source of truth — they can be archived, shared, or committed to a data repo separately from code.
- The DuckDB file is a convenience layer rebuildable from the Parquet files at any time.
- `pollster run` executes fetch → assemble → analyze → report in sequence.
- No network access required after `fetch` completes — subsequent stages are fully offline.

---

## Why This Design Is Simpler Than the Original Plan

| Original plan | Revised plan |
|---|---|
| Download 3 metadata ZIPs + 3 PDF ZIPs (GBs) | Download 2 small Parquet files (~MBs) |
| Parse CSVs across 3 different column schemas | One pre-normalized Parquet file |
| Extract poll numbers from thousands of PDFs via Claude API | Data already pre-parsed, zero LLM cost |
| Scrape Wikipedia as fallback | Unnecessary — Base dos Dados is comprehensive |
| Handle scenario selection from free-form PDF text | Scenario metadata already structured in dataset |
| 6-stage pipeline | 4-stage pipeline |
| Pollster names vary per CSV → complex CNPJ matching | Pollster names already normalized in `instituto` column |
| Manual maintenance for new elections (PDF formats change) | Just re-run fetch when Base dos Dados updates |

The data engineering work has already been done by Poder360 and Base dos Dados. Our job is to filter, compute accuracy metrics, and present them.
