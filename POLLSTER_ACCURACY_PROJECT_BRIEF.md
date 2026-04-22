# Brazilian Election Pollster Accuracy Analysis — Project Brief

## Objective

Build a Python tool that determines which Brazilian polling institute (instituto de pesquisa) produces the most accurate election predictions, based on TSE-registered polls compared against official election results.

## Scope

### Elections to analyze

**Presidential elections:** 2014, 2018, 2022 — both 1st and 2nd rounds (6 races total).

**State governor elections:** 2014, 2018, 2022 — all 27 states (UFs), both rounds where applicable (~130–160 races total).

### Poll selection rule

For each pollster × race combination, use **only the final poll published before election day**. If a pollster published multiple polls, keep only the one closest to (but before) the election date.

### Candidates of interest

**Top-2 candidates only** — the two candidates who advanced to the 2nd round (or in a 2nd round, both candidates). Ignore minor candidates for error computation.

### What "accuracy" means

Compare each poll's predicted vote shares to the **official results in valid votes** (votos válidos — excludes blank/null ballots). Since polls report numbers that include undecided/blank/null in the denominator, you must **rebase poll numbers to valid votes** before comparing.

**Rebasing formula:** For each candidate, `poll_valid_pct = poll_raw_pct / sum(all_candidate_raw_pcts) * 100`. This removes the blank/null/undecided from the denominator.

---

## Data Sources

### 1. Poll data (voting intention numbers)

**This is the hard part.** The actual per-candidate vote percentages are NOT in the TSE bulk CSV files. Those CSVs only contain metadata (pollster name, dates, sample size, methodology text). The actual numbers live in:

**TSE Questionnaire PDFs** — downloadable as ZIP archives:
- `https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/questionario_pesquisa_2014.zip`
- `https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/questionario_pesquisa_2018.zip`
- `https://cdn.tse.jus.br/estatistica/sead/odsele/pesquisa_eleitoral/questionario_pesquisa_2022.zip`

Each ZIP contains **thousands of individual PDFs** (one per registered poll). Each PDF contains the questionnaire AND the voting intention results, but in inconsistent formats across pollsters and years.

**TSE pesqele-divulgacao portal** — `https://pesqele-divulgacao.tse.jus.br/` — web interface that shows poll results. May have a JSON API backend worth exploring.

**Alternative/complementary: Poder360 aggregator** — historically offered an open API at `https://pesquisas.poder360.com.br/api/consulta/fetch/` with data going back to 2000 (presidential, gubernatorial, senatorial, mayoral). The R package `pollingBR` (github.com/sergiospagnuolo/pollingBR) wraps it, but the API token expired in 2021. The Poder360 data is now behind a paywall ("Poder Monitor" subscription). Worth checking if the API still works with a fresh token or if there's a public mirror.

**Alternative: Wikipedia tables** — English Wikipedia has well-structured poll tables for the 2018 and 2022 presidential elections. PT-Wikipedia has tables for 2014. These cover the major national pollsters well but are thin on state-level governor races.

### 2. TSE metadata CSVs (already downloaded)

User has three ZIP files already extracted:
- `pesquisa_eleitoral_2014.zip` → CSVs by UF + `_BR.csv` (presidential) + `_BRASIL.csv` (all races)
- `pesquisa_eleitoral_2018.zip` → same structure
- `pesquisa_eleitoral_2022.zip` → same structure

**Encoding:** Latin-1 (ISO-8859-1), semicolon-delimited, CRLF line terminators.

**Key columns across years (column names vary slightly):**

| Field | 2014 | 2018 | 2022 |
|-------|------|------|------|
| Pollster (legal name) | `NM_EMPRESA` | `NM_EMPRESA` | `NM_EMPRESA` |
| Trade name | `NM_EMPRESA_FANTASIA` | `NM_EMPRESA_FANTASIA` | `NM_EMPRESA_FANTASIA` |
| CNPJ | `NR_CNPJ_EMPRESA` | `NR_CNPJ_EMPRESA` | `NR_CNPJ_EMPRESA` |
| Race | `DS_CARGO` | `DS_CARGOS` | `DS_CARGO` |
| State | `SG_UF` | `SG_UF` | `SG_UF` |
| Start date | `DT_INICIO_PESQUISA` | `DT_INICIO_PESQUISA` | `DT_INICIO_PESQUISA` |
| End date | `DT_FIM_PESQUISA` | `DT_FIM_PESQUISA` | `DT_FIM_PESQUISA` |
| Sample size | `QT_ENTREVISTADO` | `QT_ENTREVISTADOS` | `QT_ENTREVISTADO` |
| Protocol | `NR_PROTOCOLO_REGISTRO` | `NR_PROTOCOLO_REGISTRO` | `NR_PROTOCOLO_REGISTRO` |
| Methodology (text) | `DS_METODOLOGIA_PESQUISA` | `DS_METODOLOGIA_PESQUISA` | `DS_METODOLOGIA_PESQUISA` |

**Date formats also differ:** 2014 and 2022 use `YYYY-MM-DD HH:MM:SS`; 2018 uses `DD/MM/YYYY`.

These CSVs are useful for:
- Cross-referencing which polls are TSE-registered
- Getting exact fieldwork dates, sample sizes, methodology
- Matching polls by protocol number

But they **do NOT contain voting intention percentages**.

### 3. Official election results

Download from TSE:
- `https://dadosabertos.tse.jus.br/dataset/resultados-2014`
- `https://dadosabertos.tse.jus.br/dataset/resultados-2018`
- `https://dadosabertos.tse.jus.br/dataset/resultados-2022`

Or use the `basedosdados` Python package / BigQuery, or the R package `electionsBR`.

**You need valid-vote percentages** for the top-2 candidates in each race (president per round, governor per state per round).

---

## Recommended Architecture

### Phase 1: Data extraction (the hard part)

**For the questionnaire PDFs:** Each PDF has a different layout depending on the pollster. Some are structured tables, others are free-text. The recommended approach is:

1. Download and unzip all three `questionario_pesquisa_20XX.zip` files
2. Filter to only presidential and gubernatorial polls (use the metadata CSVs to identify relevant protocol numbers)
3. For each PDF, extract the voting intention table. **Because formats vary wildly, the most practical approach is to use an LLM (Claude API) to interpret each PDF**: send the PDF (or its text extraction) to Claude with a structured prompt asking it to return a JSON with `{candidate_name: percentage}` for each scenario found. This handles format variation without brittle regex/template matching.
4. Match extracted results back to the metadata CSV by protocol number to get pollster name, dates, sample size.

**Important: the PDFs often contain multiple "scenarios" (cenários)** — different hypothetical candidate lineups. You want the scenario that matches the actual candidates who ran. For 2nd-round polls, there's typically only one scenario (the two finalists).

**Rate limiting / cost:** With potentially 3,000–5,000 PDFs, sending each to Claude API will take time and tokens. Consider:
- Pre-filtering using metadata CSVs to only process polls within 30 days of election day
- Further filtering to only the last poll per pollster per race
- Batching: extract text from PDF first (using `pdftotext` or similar), then send text to Claude rather than raw PDF bytes

### Phase 2: Data assembly

Build a single DataFrame with columns:
- `year`, `round` (1 or 2), `race` (e.g., "Presidente" or "Governador-SP"), `state`
- `pollster` (normalized name — see note below), `cnpj`
- `field_end_date`, `sample_size`, `protocol`
- `candidate_1_name`, `candidate_1_poll_pct`, `candidate_1_actual_valid_pct`
- `candidate_2_name`, `candidate_2_poll_pct`, `candidate_2_actual_valid_pct`

**Pollster name normalization is critical.** The same institute appears under different names across years and contexts:
- "IBOPE INTELIGÊNCIA" vs "IBOPE" vs "Ipec" (Ipec is the successor entity to IBOPE's election polling division after 2021)
- "INSTITUTO DATAFOLHA" vs "Datafolha"
- Commissioned polls show the contractor name, not always the fieldwork institute

Use `NR_CNPJ_EMPRESA` as the primary key for matching, not the name string.

### Phase 3: Analysis

For each poll observation, compute:

1. **Rebase to valid votes:** `poll_valid_i = poll_raw_i / (poll_raw_1 + poll_raw_2 + ... + poll_raw_n) * 100` where n covers all candidates (not just top 2).

2. **Signed error per candidate:** `error_i = poll_valid_i - actual_valid_i` (positive = poll overestimated that candidate).

3. **Absolute error per candidate:** `|error_i|`

4. **MAE on top-2 (= Mosteller Measure 3):** `(|error_cand1| + |error_cand2|) / 2`

5. **Margin error:** `|predicted_margin - actual_margin|` where `margin = cand1_pct - cand2_pct`.

6. **Signed bias by candidate:** For each pollster, average the signed errors across all races. A consistently positive value for Lula, for example, means the pollster systematically overestimates Lula.

### Phase 4: Reporting

Produce a report (HTML or PDF) with:

1. **Overall pollster ranking table** sorted by mean MAE, showing: pollster name, number of races covered, mean MAE, mean margin error, mean signed bias for left-leaning candidate, mean signed bias for right-leaning candidate.

2. **Per-election breakdown** (2014, 2018, 2022 separately) — same metrics.

3. **Presidential vs. gubernatorial split** — did pollsters perform differently at different levels?

4. **Chart: pollster MAE with bootstrap 95% confidence intervals.** With only 6 presidential races per pollster, CIs will be wide — that's the point, it shows what the data can actually support.

5. **Scatter plot: predicted margin vs. actual margin** across all races, colored by pollster.

---

## Key Methodological Notes

- **Include ALL polls** regardless of whether they were commissioned by campaigns/parties or by media outlets. No filtering on this dimension.
- **Unadjusted accuracy only** — no controls for sample size, methodology, or days-to-election. The pollster's accuracy is reported as-is, which is what matters to the news consumer.
- **Pool 1st and 2nd rounds together** for the overall ranking. But also report them separately as a secondary analysis, since 2nd-round polls (only 2 candidates) are structurally easier to get right.
- **Governor races greatly expand the sample size.** A pollster that covers 10 states gets 10 observations per election instead of 1. This is the main reason to include them.
- **Election dates for reference:**
  - 2014: 1st round Oct 5, 2nd round Oct 26
  - 2018: 1st round Oct 7, 2nd round Oct 28
  - 2022: 1st round Oct 2, 2nd round Oct 30

---

## Tech Stack Suggestion

- **Python 3.10+**
- **pandas** for data manipulation
- **pdfplumber** or **pdftotext** for PDF text extraction
- **anthropic** Python SDK for LLM-based PDF interpretation (Claude Sonnet for cost efficiency)
- **matplotlib** / **plotly** for charts
- **scipy** or manual bootstrap for confidence intervals
- **Click** or **argparse** for CLI interface

---

## Getting Started

The simplest way to validate the pipeline end-to-end before tackling the full PDF extraction:

1. Start with the **2022 presidential election only** (2 rounds, ~20 pollsters with final-week polls)
2. Manually enter the data from Wikipedia (or scrape it) — just the final poll per pollster for R1 and R2
3. Get the actual results from TSE
4. Run the full analysis pipeline
5. Verify the numbers make sense (e.g., AtlasIntel should show up as more accurate than Datafolha/Ipec for 2022, since those two famously overestimated Lula's lead)
6. Then scale up to PDFs and governor races

This way you debug the analysis logic on clean data before wrestling with PDF extraction.
