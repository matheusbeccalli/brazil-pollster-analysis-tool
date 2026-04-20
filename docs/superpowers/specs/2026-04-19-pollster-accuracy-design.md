# Brazilian Election Pollster Accuracy Analysis — Design Spec

## Overview

A Python CLI tool that ranks Brazilian polling institutes by prediction accuracy, comparing their final pre-election polls against official TSE election results (valid votes). Covers presidential and gubernatorial races across 2014, 2018, and 2022 (both rounds). Designed to be re-runnable for future elections.

## Decisions Made

- **Approach:** API-first — investigate the TSE portal (`pesqele-divulgacao.tse.jus.br`) for structured JSON data before falling back to PDF extraction via Claude API. Wikipedia scraping serves as MVP validation.
- **Output:** Static HTML report (single self-contained file).
- **Pollster identity:** CNPJ-based, with manual merge table for known successor entities (IBOPE → Ipec treated as one lineage).
- **Poll selection:** Last poll per pollster per race, regardless of how many days before the election. Equal weight.
- **Bias analysis:** Party-based left/right classification via hardcoded party-to-leaning map.
- **Pipeline design:** Re-runnable staged pipeline with intermediate Parquet files. Adding a new election year requires only config changes.
- **CLI:** Click with subcommands per stage.

---

## Project Structure

```
brazil-pollster-analysis-tool/
├── pyproject.toml
├── src/
│   └── pollster/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI with subcommands
│       ├── config.py               # Election dates, party mappings, pollster merges
│       ├── stages/
│       │   ├── __init__.py
│       │   ├── download.py         # Stage 1: download raw data
│       │   ├── extract.py          # Stage 2: extract poll numbers
│       │   ├── results.py          # Stage 3: fetch official election results
│       │   ├── assemble.py         # Stage 4: build unified dataset
│       │   ├── analyze.py          # Stage 5: compute accuracy metrics
│       │   └── report.py           # Stage 6: generate HTML report
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── tse_api.py          # TSE portal API extractor
│       │   ├── pdf_extractor.py    # PDF + Claude API fallback extractor
│       │   └── wikipedia.py        # Wikipedia scraper (validation/MVP)
│       └── utils/
│           ├── __init__.py
│           ├── normalize.py        # Pollster name/CNPJ normalization
│           └── rebase.py           # Rebase poll numbers to valid votes
├── data/                           # Git-ignored, all pipeline artifacts
│   ├── raw/                        # Downloaded ZIPs, CSVs, PDFs
│   ├── extracted/                  # Parsed poll numbers (JSON per poll)
│   ├── results/                    # Official election results
│   ├── assembled/                  # Unified dataset (Parquet)
│   ├── analysis/                   # Computed metrics (Parquet)
│   └── reports/                    # Generated HTML reports
└── tests/
```

---

## Stage 1: Download (`pollster download`)

### 1a. TSE Metadata CSVs

Download and extract `pesquisa_eleitoral_20XX.zip` from the TSE CDN:
- `https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/pesquisa_eleitoral_20XX.zip`

Parse with Latin-1 encoding, semicolon delimiter. Normalize column names across years:

| Normalized        | 2014              | 2018               | 2022              |
|-------------------|-------------------|--------------------|--------------------|
| `pollster_name`   | `NM_EMPRESA`      | `NM_EMPRESA`       | `NM_EMPRESA`       |
| `trade_name`      | `NM_EMPRESA_FANTASIA` | `NM_EMPRESA_FANTASIA` | `NM_EMPRESA_FANTASIA` |
| `cnpj`            | `NR_CNPJ_EMPRESA` | `NR_CNPJ_EMPRESA`  | `NR_CNPJ_EMPRESA`  |
| `race`            | `DS_CARGO`        | `DS_CARGOS`        | `DS_CARGO`         |
| `state`           | `SG_UF`           | `SG_UF`            | `SG_UF`            |
| `field_start`     | `DT_INICIO_PESQUISA` | `DT_INICIO_PESQUISA` | `DT_INICIO_PESQUISA` |
| `field_end`       | `DT_FIM_PESQUISA` | `DT_FIM_PESQUISA`  | `DT_FIM_PESQUISA`  |
| `sample_size`     | `QT_ENTREVISTADO` | `QT_ENTREVISTADOS` | `QT_ENTREVISTADO`  |
| `protocol`        | `NR_PROTOCOLO_REGISTRO` | `NR_PROTOCOLO_REGISTRO` | `NR_PROTOCOLO_REGISTRO` |

Date parsing: 2014/2022 use `YYYY-MM-DD HH:MM:SS`, 2018 uses `DD/MM/YYYY`.

Save normalized metadata as `data/raw/metadata_{year}.parquet`.

### 1b. TSE Portal API Probe

Investigate `pesqele-divulgacao.tse.jus.br` for a JSON API:
- Fetch the page, inspect for API patterns
- Try common endpoint patterns
- If found, document endpoints and schema in `data/raw/tse_api_schema.json`
- Cache discovery result to avoid re-probing

### 1c. Questionnaire PDFs

Download `questionario_pesquisa_20XX.zip` only if the API path fails or is incomplete. Use metadata CSVs to identify needed protocol numbers, extract only those PDFs.

### 1d. Official Election Results

Download raw result files from `dadosabertos.tse.jus.br/dataset/resultados-20XX`. Save to `data/raw/results_{year}/`. Parsing and processing happens in Stage 3.

### Filtering

Before extraction, filter metadata to:
- Race type: `PRESIDENTE` or `GOVERNADOR`
- Years: 2014, 2018, 2022
- For each pollster (CNPJ) × race combination, keep only the final poll (latest `field_end` before the relevant election day — round 1 date for 1st-round polls, round 2 date for 2nd-round polls)

---

## Stage 2: Extract (`pollster extract`)

Three extractors, tried in priority order per poll:

### Priority 1: TSE Portal API (`tse_api.py`)

Query the API for each poll in the filtered set, matched by protocol number. Parse structured response into standardized format.

### Priority 2: PDF + Claude API (`pdf_extractor.py`)

For polls not covered by the API:
1. Locate PDF by protocol number in the questionnaire archive
2. Extract text using `pdfplumber`
3. Send to Claude API (Sonnet) with structured prompt requesting JSON extraction of candidate names and percentages
4. Validate response: percentages sum to ~100%, candidate names non-empty
5. Process sequentially with configurable delay for rate limiting

### Priority 3: Wikipedia (`wikipedia.py`)

Scrape poll tables from Wikipedia for presidential races:
- English Wikipedia for 2018 and 2022 presidential
- PT-Wikipedia for 2014 presidential
- Parse HTML tables, match to TSE metadata by pollster name + date proximity
- Not used for governor races (too sparse)
- Serves as validation — compare against API/PDF numbers for same polls

### Output Format

Each poll saved as `data/extracted/{year}/{protocol}.json`:

```json
{
    "protocol": "BR-00123/2022",
    "year": 2022,
    "round": 1,
    "race": "PRESIDENTE",
    "state": "BR",
    "pollster_cnpj": "00.000.000/0001-00",
    "field_end_date": "2022-09-30",
    "source": "tse_api",
    "scenarios": [
        {
            "candidates": {
                "LULA": 48.0,
                "JAIR BOLSONARO": 34.0,
                "SIMONE TEBET": 8.0,
                "CIRO GOMES": 6.0
            },
            "undecided": 2.0,
            "blank_null": 2.0
        }
    ]
}
```

### Scenario Selection

Polls may contain multiple scenarios (different candidate lineups). Selection logic:
- Match against candidates who actually ran (from official results)
- 1st round: select scenario containing both top-2 finishers
- 2nd round: typically only one scenario
- Fuzzy-match candidate names (handle "LULA" vs "LUIZ INÁCIO LULA DA SILVA", etc.)

---

## Stage 3: Results (`pollster results`)

Parse the raw official result files downloaded in Stage 1d. For each race (year × round × state × office):
- Compute total valid votes per candidate
- Compute valid-vote percentage per candidate
- Identify top-2 candidates (those who advanced to round 2, or both finalists in round 2)

Output: `data/results/results_{year}.parquet`

---

## Stage 4: Assemble (`pollster assemble`)

Merge extracted polls, metadata, and official results into a single dataset.

### Steps

1. **Load all extracted polls** from JSON files into a DataFrame
2. **Join with metadata** on protocol number for pollster name, CNPJ, sample size, methodology, fieldwork dates
3. **Normalize pollsters** using CNPJ as primary key. Config-driven merge table for known lineages (IBOPE/Ipec merged under one entry). Assign clean `pollster_display_name`.
4. **Join official results** for each race, attaching actual valid-vote percentages for top-2 candidates. Candidate name matching via fuzzy match + alias table.
5. **Identify top-2 candidates** from official results. Filter poll scenario data to just these two.
6. **Rebase to valid votes:** `poll_valid_pct_i = (poll_raw_pct_i / sum(all_candidate_raw_pcts)) * 100` — the denominator includes ALL candidates in the poll scenario (not just top-2), which removes undecided/blank/null from the base. After rebasing, only the top-2 candidates' rebased percentages are used for error computation.
7. **Assign party leaning** using hardcoded party → left/center/right mapping

### Output

`data/assembled/polls.parquet` with columns:
- `year`, `round`, `race_type`, `state`
- `pollster_display_name`, `pollster_cnpj`, `field_end_date`, `sample_size`, `protocol`
- `candidate_1_name`, `candidate_1_party`, `candidate_1_leaning`, `candidate_1_poll_raw_pct`, `candidate_1_poll_valid_pct`, `candidate_1_actual_valid_pct`
- `candidate_2_name`, `candidate_2_party`, `candidate_2_leaning`, `candidate_2_poll_raw_pct`, `candidate_2_poll_valid_pct`, `candidate_2_actual_valid_pct`
- `source` (tse_api / pdf_claude / wikipedia)

---

## Stage 5: Analyze (`pollster analyze`)

### Per-Poll Metrics

For each poll observation:
1. **Signed error per candidate:** `error_i = poll_valid_pct_i - actual_valid_pct_i`
2. **Absolute error per candidate:** `|error_i|`
3. **MAE on top-2 (Mosteller Measure 3):** `(|error_cand1| + |error_cand2|) / 2`
4. **Predicted margin:** `cand1_poll_valid_pct - cand2_poll_valid_pct`
5. **Actual margin:** `cand1_actual_valid_pct - cand2_actual_valid_pct`
6. **Margin error:** `|predicted_margin - actual_margin|`

### Aggregated Pollster Metrics

For each pollster, across all their observations:
- **N races** — number of race observations
- **Mean MAE** — primary ranking metric
- **Median MAE** — robustness against outliers
- **Mean margin error**
- **Mean signed bias (left)** — average signed error for left-leaning candidates
- **Mean signed bias (right)** — average signed error for right-leaning candidates
- **Bootstrap 95% CI on MAE** — 10,000 resamples of the pollster's race-level MAEs, report 2.5th and 97.5th percentiles

### Breakdown Views

Same metrics sliced by:
- Per election year (2014, 2018, 2022)
- Per round (1st vs 2nd)
- Per race type (presidential vs gubernatorial)

### Output

- `data/analysis/poll_level_metrics.parquet` — one row per poll observation
- `data/analysis/pollster_rankings.parquet` — aggregated rankings with CIs
- `data/analysis/pollster_rankings_by_year.parquet`
- `data/analysis/pollster_rankings_by_round.parquet`
- `data/analysis/pollster_rankings_by_race_type.parquet`

---

## Stage 6: Report (`pollster report`)

Generates a self-contained static HTML report. Charts rendered as embedded SVGs via matplotlib. No JavaScript dependencies.

### Report Sections

1. **Executive summary** — top 5 most accurate pollsters by mean MAE, headline finding, total polls/races analyzed.

2. **Overall pollster ranking table** — sorted by mean MAE. Columns: rank, pollster name, N races, mean MAE, median MAE, 95% CI, mean margin error, left bias, right bias. Color-coded green (low error) to red (high error). Footnote warning for pollsters with < 3 observations.

3. **Per-election breakdown** — sub-tables for 2014, 2018, 2022. Shows whether pollsters improved or regressed over time.

4. **Presidential vs. gubernatorial split** — side-by-side comparison of performance by race level.

5. **Round 1 vs. Round 2 split** — secondary table showing whether pollsters are more accurate with only 2 candidates.

6. **Charts:**
   - **Bar chart: pollster MAE with bootstrap 95% CI error bars** — sorted by MAE. Wide CIs show uncertainty honestly.
   - **Scatter plot: predicted margin vs. actual margin** — one point per observation, colored by pollster. 45-degree line = perfect prediction.
   - **Heatmap: pollster × election year MAE** — consistency over time at a glance.

7. **Methodology notes** — data sources, rebasing formula, poll selection rule, IBOPE/Ipec merge rationale.

### Styling

Clean, minimal inline CSS. Monochrome-friendly palette. Default sort by MAE.

### Output

`data/reports/pollster_accuracy_report.html`

---

## Configuration (`config.py`)

All hardcoded domain knowledge in one file:

- **Election dates:** year → {round_1, round_2} date mapping
- **TSE data URLs:** CDN paths for metadata CSVs, questionnaire ZIPs, results CSVs
- **CSV column mappings:** per-year column name normalization
- **Pollster merges:** CNPJ-based merge table for known successor entities
- **Pollster display names:** CNPJ → clean display name
- **Party-to-leaning map:** party abbreviation → left/center/right
- **Candidate aliases:** common name variations for fuzzy matching

### Adding a New Election (e.g., 2026)

1. Add election dates and URLs to `config.py`
2. Run `pollster download --year 2026`
3. Add any new pollster display names / merges to config
4. Run `pollster run` — full pipeline regenerates the report

---

## Tech Stack

- **Python 3.10+**
- **pandas** — data manipulation
- **pdfplumber** — PDF text extraction (fallback path)
- **anthropic** — Claude API for PDF interpretation (Sonnet for cost)
- **matplotlib** — charts for the report
- **scipy** — bootstrap confidence intervals
- **click** — CLI framework
- **requests** — HTTP downloads and API calls
- **beautifulsoup4** — Wikipedia scraping
- **pyarrow** — Parquet I/O

---

## Pipeline Invariants

- Each stage is idempotent: if outputs exist and inputs haven't changed, skip. `--force` overrides.
- Each extracted poll is a standalone JSON file — pipeline is resumable mid-extraction.
- All intermediate data lives in `data/` (git-ignored).
- The only manual maintenance is `config.py` when adding new elections.
- `pollster run` executes all stages in sequence for a full end-to-end run.
