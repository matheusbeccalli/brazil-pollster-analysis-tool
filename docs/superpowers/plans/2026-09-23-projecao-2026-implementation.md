# Projecao 2026 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the 2026 presidential polls from the Poder360 aggregator backend and produce a first- and second-round projection report (weighted average + Monte Carlo calibrated on 2022 pollster error).

**Architecture:** Two new pipeline stages next to the existing ones: `fetch2026` (download + parse into `polls_2026`) and `project` (weights, estimate, simulation, HTML). A small pure parser module (`utils/poder360.py`) isolates the API quirks. Task 0 fixes a pre-existing rebase bug in `assemble` so historical EAM (used as weights) is meaningful.

**Tech Stack:** Python 3.12, pandas, numpy, duckdb, requests, matplotlib (SVG), click, pytest. Spec: `docs/superpowers/specs/2026-09-23-projecao-2026-design.md`.

---

## File structure

- Modify `src/pollster/config.py` — 2026 dates, 2026 pollster aliases, API URL, projection constants.
- Modify `src/pollster/stages/assemble.py` — drop `condicao == 1` rows before scenario selection/rebase (bug fix).
- Create `src/pollster/utils/poder360.py` — pure parsing of the aggregator JSON.
- Create `src/pollster/stages/fetch2026.py` — download, parquet, duckdb table.
- Create `src/pollster/stages/project.py` — weights, estimates, Monte Carlo, result dataclass, persistence.
- Create `src/pollster/stages/project_report.py` — HTML report.
- Modify `src/pollster/cli.py` — `fetch-2026`, `project` commands.
- Modify `README.md` — usage.
- Tests: `tests/test_poder360.py`, `tests/test_fetch2026.py`, `tests/test_project.py`, `tests/test_project_report.py`, extend `tests/test_assemble.py`.

---

### Task 0: Fix rebase bug — exclude non-candidate rows (condicao = 1) in assemble

**Files:**
- Modify: `src/pollster/stages/assemble.py` (`_select_final_polls`)
- Test: `tests/test_assemble.py`

- [ ] **Step 1: Write the failing test**

```python
def test_assemble_excludes_condicao_1_rows_from_rebase(tmp_db, tmp_data_dir):
    from tests.fixtures import make_polls_df, make_results_df, make_candidates_df
    polls = make_polls_df()
    extra = polls.iloc[[0]].copy()
    extra["nome_candidato"] = "brancos / nulos"; extra["sigla_partido"] = None
    extra["condicao"] = 1; extra["percentual"] = 20.0
    polls = pd.concat([polls, extra], ignore_index=True)
    tmp_db.execute("CREATE TABLE poder360_polls AS SELECT * FROM polls")
    results = make_results_df(); tmp_db.execute("CREATE TABLE tse_results AS SELECT * FROM results")
    cands = make_candidates_df(); tmp_db.execute("CREATE TABLE tse_candidates AS SELECT * FROM cands")
    assemble_data(tmp_db, data_dir=tmp_data_dir)
    df = tmp_db.execute("SELECT * FROM polls_vs_actual WHERE pollster_display_name='Datafolha'").fetchdf()
    # 48 / (48+34+8+6) * 100 = 50.0 — blank row must not be in the denominator
    assert abs(df.iloc[0]["candidate_1_poll_valid_pct"] - 50.0) < 1e-6
```

(Adapt fixture names to what `tests/fixtures.py` exports; the fixtures already have `condicao = 1` for candidates, so set candidate rows' `condicao` to 0 in the fixture if needed.)

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/test_assemble.py -k condicao -v`
- [ ] **Step 3: Implement** — in `_select_final_polls`, right after loading `polls`:

```python
    if "condicao" in polls.columns:
        polls = polls[(polls["condicao"].isna()) | (polls["condicao"] == 0)]
```

- [ ] **Step 4: Run all tests** — `pytest -q`; expect PASS.
- [ ] **Step 5: Commit** — `fix: exclude undecided/blank rows (condicao=1) from valid-vote rebase`
- [ ] **Step 6: Regenerate historical outputs** — `pollster fetch && pollster assemble && pollster analyze --since 2000 && pollster report`; commit parquets + report as `data: regenerate accuracy analysis after rebase fix`.

---

### Task 1: Config additions

**Files:** Modify `src/pollster/config.py`; Test `tests/test_config.py`.

- [ ] **Step 1: Failing test**

```python
def test_2026_election_dates_and_aliases():
    from pollster.config import ELECTIONS, POLLSTER_ALIASES_2026, PODER360_AGREGADOR_URL
    assert ELECTIONS[2026]["round_1"] == date(2026, 10, 4)
    assert ELECTIONS[2026]["round_2"] == date(2026, 10, 25)
    assert POLLSTER_ALIASES_2026["AtlasIntel"] == "AtlasIntel/Internet"
    assert PODER360_AGREGADOR_URL.startswith("https://monitor-agregador.poder360.com.br")
```

- [ ] **Step 2: Implement** — append to `config.py`:

```python
ELECTIONS[2026] = {"round_1": date(2026, 10, 4), "round_2": date(2026, 10, 25)}

POLLSTER_ALIASES_2026: dict[str, str] = {
    "AtlasIntel": "AtlasIntel/Internet",
    "Futura Inteligência": "Futura",
    "Ipec": "IBOPE/Ipec",
    "Instituto Ideia": "Ideia Big Data",
    "CNT (Confederação Nacional do Transporte)": "MDA",
}

PODER360_AGREGADOR_URL = "https://monitor-agregador.poder360.com.br/pesquisas/v1/api"
PODER360_CARGO_PRESIDENTE = 3
PODER360_UF_BRASIL = 6

PROJECTION_YEAR = 2026
PROJECTION_WINDOW_DAYS = 14
PROJECTION_RECENCY_TAU_DAYS = 7.0
PROJECTION_REFERENCE_SAMPLE = 2000
PROJECTION_SIGMA_FLOOR = 3.0
PROJECTION_SIGMA_OTHER = 1.5
PROJECTION_N_SIMS = 10_000
PROJECTION_SEED = 2026
PROJECTION_RUNOFF_PAIR = ("Lula", "Flávio Bolsonaro")
PROJECTION_HISTORY_YEARS = (2022,)
```

(`ELECTIONS[2026]` must be assigned after the dict literal; put it directly under the literal.)

- [ ] **Step 3: Run tests, commit** — `feat(config): 2026 election dates, pollster aliases, projection constants`

---

### Task 2: Poder360 JSON parser

**Files:** Create `src/pollster/utils/poder360.py`; Test `tests/test_poder360.py`.

- [ ] **Step 1: Failing tests**

```python
from pollster.utils.poder360 import (parse_sample_size, is_valid_candidate,
                                     split_scenarios, polls_to_frame, candidate_key)

def test_parse_sample_size_handles_thousands_as_decimal():
    assert parse_sample_size(2.006) == 2006
    assert parse_sample_size(2000) == 2000
    assert parse_sample_size(None) is None
    assert parse_sample_size(0) is None

def test_is_valid_candidate():
    assert is_valid_candidate("Lula")
    for bad in ["brancos / nulos", "não sabem / não responderam", "indecisos",
                "nenhum deles", "ninguém / brancos / nulos", "Outros", "não iria votar"]:
        assert not is_valid_candidate(bad), bad

def test_split_scenarios_on_repeated_name():
    flat = [{"nome": "Lula", "percentual": 46}, {"nome": "Flávio Bolsonaro", "percentual": 44},
            {"nome": "brancos / nulos", "percentual": 8},
            {"nome": "Lula", "percentual": 49}, {"nome": "Romeu Zema", "percentual": 39},
            {"partido": "UP", "percentual": 1}]  # no name -> ignored
    scen = split_scenarios(flat)
    assert len(scen) == 2
    assert [e["nome"] for e in scen[1]] == ["Lula", "Romeu Zema"]

def test_candidate_key_is_accent_and_case_insensitive():
    assert candidate_key("Flavio Bolsonaro") == candidate_key("FLÁVIO BOLSONARO")

def test_polls_to_frame_long_format():
    raw = [{"id": 1, "instituto": "AtlasIntel", "data": "2026-09-16T00:00:00.000Z",
            "contratante": "Bloomberg", "entrevistas": 5.018, "margem": 1, "registro": "BR-1",
            "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 44.1},
                            {"nome": "Flávio Bolsonaro", "partido": "PL", "percentual": 41.7},
                            {"nome": "brancos / nulos", "partido": "N/A", "percentual": 5}]]}]
    df = polls_to_frame(raw, turno=1)
    assert list(df.columns) == ["poll_id", "instituto", "pollster_display_name", "data", "contratante",
                                "entrevistas", "margem", "registro", "turno", "cenario_idx",
                                "nome_candidato", "candidate_key", "partido", "percentual", "is_valid_candidate"]
    assert len(df) == 3
    assert df["entrevistas"].iloc[0] == 5018
    assert df["pollster_display_name"].iloc[0] == "AtlasIntel/Internet"
    assert str(df["data"].iloc[0].date()) == "2026-09-16"
    assert df["is_valid_candidate"].tolist() == [True, True, False]
```

- [ ] **Step 2: Implement `src/pollster/utils/poder360.py`**

```python
import unicodedata
import pandas as pd
from pollster.config import POLLSTER_ALIASES_2026
from pollster.utils.normalize import normalize_pollster_name

NON_VALID_PATTERNS = ("branco", "nulo", "indecis", "nao sabe", "nao respond", "nao decid",
                      "nao opinou", "nenhum", "ninguem", "nao vai votar", "nao iria votar", "outros")

FRAME_COLUMNS = ["poll_id", "instituto", "pollster_display_name", "data", "contratante",
                 "entrevistas", "margem", "registro", "turno", "cenario_idx",
                 "nome_candidato", "candidate_key", "partido", "percentual", "is_valid_candidate"]


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def candidate_key(name: str) -> str:
    return " ".join(_strip_accents(name or "").lower().split())


def parse_sample_size(value) -> int | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v < 100:          # "2.006" parsed as 2.006 -> 2006
        v *= 1000
    return int(round(v))


def is_valid_candidate(name: str) -> bool:
    key = candidate_key(name)
    return bool(key) and not any(p in key for p in NON_VALID_PATTERNS)


def split_scenarios(entries: list[dict]) -> list[list[dict]]:
    scenarios, current, seen = [], [], set()
    for e in entries:
        name = e.get("nome")
        if not name:
            continue
        key = candidate_key(name)
        if key in seen:
            scenarios.append(current)
            current, seen = [], set()
        current.append(e)
        seen.add(key)
    if current:
        scenarios.append(current)
    return scenarios


def normalize_pollster_2026(raw_name: str) -> str:
    name = (raw_name or "").strip()
    name = POLLSTER_ALIASES_2026.get(name, name)
    return normalize_pollster_name(name)


def polls_to_frame(raw: list[dict], turno: int) -> pd.DataFrame:
    rows = []
    for poll in raw:
        date = pd.to_datetime(str(poll.get("data", ""))[:10], errors="coerce")
        base = {
            "poll_id": poll.get("id"),
            "instituto": poll.get("instituto") or poll.get("contratante") or "",
            "pollster_display_name": normalize_pollster_2026(poll.get("instituto") or poll.get("contratante") or ""),
            "data": date,
            "contratante": poll.get("contratante"),
            "entrevistas": parse_sample_size(poll.get("entrevistas")),
            "margem": poll.get("margem"),
            "registro": poll.get("registro"),
            "turno": turno,
        }
        idx = 0
        for group in poll.get("apuracoes", []) or []:
            for scenario in split_scenarios(group):
                for e in scenario:
                    name = e["nome"].strip()
                    rows.append({**base, "cenario_idx": idx, "nome_candidato": name,
                                 "candidate_key": candidate_key(name), "partido": e.get("partido"),
                                 "percentual": e.get("percentual"),
                                 "is_valid_candidate": is_valid_candidate(name)})
                idx += 1
    return pd.DataFrame(rows, columns=FRAME_COLUMNS)
```

- [ ] **Step 3: Run tests, commit** — `feat: parser for Poder360 aggregator JSON`

---

### Task 3: fetch-2026 stage + CLI

**Files:** Create `src/pollster/stages/fetch2026.py`; Modify `src/pollster/cli.py`; Test `tests/test_fetch2026.py`.

- [ ] **Step 1: Failing test**

```python
import pandas as pd
from pollster.stages import fetch2026

def test_fetch_2026_writes_parquet_and_table(tmp_data_dir, monkeypatch):
    def fake_download(turno):
        return [{"id": turno, "instituto": "Quaest", "data": "2026-09-20", "contratante": "Globo",
                 "entrevistas": 2004, "margem": 2, "registro": "BR-2",
                 "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 37},
                                {"nome": "Flávio Bolsonaro", "partido": "PL", "percentual": 33}]]}]
    monkeypatch.setattr(fetch2026, "download_polls", fake_download)
    fetch2026.fetch_2026(tmp_data_dir, force=True)
    df = pd.read_parquet(tmp_data_dir / "parquet" / "polls_2026.parquet")
    assert sorted(df["turno"].unique()) == [1, 2]
    import duckdb
    con = duckdb.connect(str(tmp_data_dir / "pollster.duckdb"))
    assert con.execute("SELECT COUNT(*) FROM polls_2026").fetchone()[0] == 4
    con.close()
```

- [ ] **Step 2: Implement `src/pollster/stages/fetch2026.py`**

```python
import pathlib
import click
import pandas as pd
import requests

from pollster.config import (PODER360_AGREGADOR_URL, PODER360_CARGO_PRESIDENTE,
                             PODER360_UF_BRASIL, PROJECTION_YEAR)
from pollster.db import get_connection, register_parquet
from pollster.utils.poder360 import polls_to_frame

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pollster-tool",
           "Origin": "https://drive.poder360.com.br",
           "Referer": "https://drive.poder360.com.br/",
           "Content-Type": "application/json"}


def download_polls(turno: int, year: int = PROJECTION_YEAR) -> list[dict]:
    payload = {"cargosId": PODER360_CARGO_PRESIDENTE, "ano": year, "turno": str(turno),
               "unidadesFederativasId": PODER360_UF_BRASIL, "cidade": "", "pagina": 1}
    resp = requests.post(PODER360_AGREGADOR_URL, json=payload, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise click.ClickException(f"Unexpected response from Poder360 for turno {turno}: {str(data)[:200]}")
    return data


def fetch_2026(data_dir: pathlib.Path, force: bool = False) -> None:
    parquet_dir = data_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    path = parquet_dir / "polls_2026.parquet"
    con = get_connection(data_dir)
    if path.exists() and not force:
        click.echo(f"2026 polls already exist at {path}. Use --force to re-download.")
        register_parquet(con, "polls_2026", path)
        con.close()
        return
    frames = []
    for turno in (1, 2):
        click.echo(f"Downloading 2026 presidential polls, turno {turno}, from Poder360...")
        raw = download_polls(turno)
        df = polls_to_frame(raw, turno=turno)
        click.echo(f"  → {df['poll_id'].nunique()} polls, {len(df)} rows.")
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_parquet(path, index=False)
    register_parquet(con, "polls_2026", path)
    con.close()
    click.echo("Fetch 2026 complete.")
```

CLI addition in `cli.py`:

```python
@cli.command("fetch-2026")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch_2026_cmd(force):
    """Download 2026 presidential polls from the Poder360 aggregator."""
    from pollster.stages.fetch2026 import fetch_2026
    fetch_2026(pathlib.Path(config.DATA_DIR_NAME), force=force)
```

- [ ] **Step 3: Run tests; run `pollster fetch-2026 --force` for real; commit** — `feat: fetch-2026 stage (Poder360 aggregator)` (include the parquet).

---

### Task 4: Projection core (weights, estimate, Monte Carlo)

**Files:** Create `src/pollster/stages/project.py`; Test `tests/test_project.py`.

Public API:

```python
@dataclass
class RoundProjection:
    turno: int
    polls: pd.DataFrame          # one row per (poll, candidate) used, with weights
    estimate: pd.DataFrame       # candidate, partido, weighted_pct, simple_pct, ci_low, ci_high, p_first, p_top2
    sims: np.ndarray             # (n_sims, n_candidates) valid-vote shares, columns follow estimate order
    p_decided: float             # P(someone > 50) — only meaningful for turno 1

@dataclass
class ProjectionResult:
    as_of: date; window_days: int; sigma_margin: float; sigma_other: float; n_sims: int
    eam_by_pollster: dict[str, float]; median_eam: float
    round1: RoundProjection; round2: RoundProjection | None

def pollster_accuracy(con) -> tuple[dict[str, float], float]
def historical_sigma_margin(con) -> float
def main_scenarios(polls: pd.DataFrame, turno: int) -> pd.DataFrame
def select_window(polls: pd.DataFrame, as_of: date, window_days: int) -> pd.DataFrame
def add_weights(polls, as_of, eam_by_pollster, median_eam) -> pd.DataFrame
def weighted_estimate(polls) -> pd.DataFrame
def simulate(estimate, sigma_margin, sigma_other, n_sims, rng) -> np.ndarray
def summarize(estimate, sims) -> tuple[pd.DataFrame, float]
def project_election(con, as_of=None, window_days=..., n_sims=..., data_dir=None) -> ProjectionResult
```

- [ ] **Step 1: Failing tests (`tests/test_project.py`)**

```python
from datetime import date
import numpy as np, pandas as pd, pytest
from pollster.stages import project as P

def _polls():
    rows = []
    def poll(pid, inst, disp, d, n, cands, turno=1, cen=0):
        for name, party, pct in cands:
            rows.append(dict(poll_id=pid, instituto=inst, pollster_display_name=disp, data=pd.Timestamp(d),
                             contratante="x", entrevistas=n, margem=2, registro="r", turno=turno, cenario_idx=cen,
                             nome_candidato=name, candidate_key=name.lower(), partido=party, percentual=pct,
                             is_valid_candidate=not name.startswith("brancos")))
    poll(1, "Datafolha", "Datafolha", "2026-09-16", 2000, [("Lula","PT",39),("Flávio Bolsonaro","PL",36),("Augusto Cury","Avante",6),("brancos","",9)])
    poll(2, "Nexus", "Nexus", "2026-09-20", 2000, [("Lula","PT",40),("Flávio Bolsonaro","PL",37),("Augusto Cury","Avante",6),("brancos","",6)])
    poll(3, "Nexus", "Nexus", "2026-09-13", 2000, [("Lula","PT",42),("Flávio Bolsonaro","PL",37),("brancos","",10)])  # older, same pollster -> dropped
    poll(4, "Old", "Old", "2026-08-01", 2000, [("Lula","PT",50),("Flávio Bolsonaro","PL",30),("brancos","",20)])  # outside window
    poll(5, "Datafolha", "Datafolha", "2026-09-16", 2000, [("Lula","PT",46),("Flávio Bolsonaro","PL",44),("brancos","",10)], turno=2, cen=0)
    poll(5, "Datafolha", "Datafolha", "2026-09-16", 2000, [("Lula","PT",49),("Romeu Zema","Novo",39),("brancos","",12)], turno=2, cen=1)
    return pd.DataFrame(rows)

def test_main_scenarios_round1_keeps_largest_scenario_and_round2_keeps_pair():
    df = _polls()
    r1 = P.main_scenarios(df, 1)
    assert set(r1["poll_id"]) == {1, 2, 3, 4}
    r2 = P.main_scenarios(df, 2)
    assert set(r2["nome_candidato"]) == {"Lula", "Flávio Bolsonaro", "brancos"}

def test_select_window_one_poll_per_pollster_most_recent():
    df = P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14)
    assert sorted(df["poll_id"].unique()) == [1, 2]

def test_add_weights_unknown_pollster_gets_median_and_recency_decays():
    df = P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14)
    w = P.add_weights(df, date(2026, 9, 23), {"Datafolha": 4.0}, median_eam=6.0)
    d = w[w.pollster_display_name == "Datafolha"].iloc[0]
    n = w[w.pollster_display_name == "Nexus"].iloc[0]
    assert d["w_acc"] == pytest.approx(6.0 / 4.0)
    assert n["w_acc"] == pytest.approx(1.0)
    assert n["w_rec"] > d["w_rec"]          # Nexus is more recent
    assert d["w_n"] == pytest.approx(1.0)   # 2000 / 2000

def test_weighted_estimate_rebases_and_sums_to_100():
    df = P.add_weights(P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14),
                       date(2026, 9, 23), {}, 6.0)
    est = P.weighted_estimate(df)
    assert est["weighted_pct"].sum() == pytest.approx(100.0)
    assert est.iloc[0]["candidate"] == "Lula"
    assert est.iloc[0]["weighted_pct"] > est.iloc[1]["weighted_pct"] > est.iloc[2]["weighted_pct"]

def test_simulate_and_summarize_probabilities_are_coherent():
    est = pd.DataFrame({"candidate": ["A", "B", "C"], "partido": ["", "", ""],
                        "weighted_pct": [55.0, 40.0, 5.0], "simple_pct": [55.0, 40.0, 5.0]})
    sims = P.simulate(est, sigma_margin=3.0, sigma_other=1.5, n_sims=4000, rng=np.random.default_rng(1))
    assert sims.shape == (4000, 3)
    assert np.allclose(sims.sum(axis=1), 100.0)
    summary, p_decided = P.summarize(est, sims)
    assert summary.iloc[0]["p_first"] > 0.99
    assert summary["p_top2"].sum() == pytest.approx(2.0)
    assert p_decided > 0.9
    assert summary.iloc[0]["ci_low"] < 55.0 < summary.iloc[0]["ci_high"]

def test_simulate_is_reproducible_with_seed():
    est = pd.DataFrame({"candidate": ["A", "B"], "partido": ["", ""], "weighted_pct": [51.0, 49.0], "simple_pct": [51.0, 49.0]})
    a = P.simulate(est, 3.0, 1.5, 100, np.random.default_rng(7))
    b = P.simulate(est, 3.0, 1.5, 100, np.random.default_rng(7))
    assert np.array_equal(a, b)

def test_historical_sigma_margin_uses_floor(tmp_db):
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 8.0, 5.0), (2022, 1, 'presidente', 'B', 6.0, 5.0),
        (2022, 2, 'presidente', 'A', 4.0, 2.0), (2022, 2, 'presidente', 'B', 2.0, 2.0))
        t(year, round, cargo, pollster_display_name, predicted_margin, actual_margin)""")
    assert P.historical_sigma_margin(tmp_db) == pytest.approx(3.0)   # RMSE(2, 1)=1.58 -> floor 3.0

def test_pollster_accuracy_uses_2022_presidential_mae(tmp_db):
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 2.0), (2022, 2, 'presidente', 'A', 4.0),
        (2022, 1, 'presidente', 'B', 6.0), (2022, 1, 'governador', 'B', 40.0), (2018, 1, 'presidente', 'C', 30.0))
        t(year, round, cargo, pollster_display_name, mae_top2)""")
    eam, median = P.pollster_accuracy(tmp_db)
    assert eam == {"A": 3.0, "B": 6.0}
    assert median == pytest.approx(4.5)
```

- [ ] **Step 2: Implement `src/pollster/stages/project.py`**

```python
import pathlib
from dataclasses import dataclass
from datetime import date

import click
import duckdb
import numpy as np
import pandas as pd

from pollster import config
from pollster.utils.poder360 import candidate_key


@dataclass
class RoundProjection:
    turno: int
    polls: pd.DataFrame
    estimate: pd.DataFrame
    sims: np.ndarray
    p_decided: float


@dataclass
class ProjectionResult:
    as_of: date
    window_days: int
    sigma_margin: float
    sigma_other: float
    n_sims: int
    eam_by_pollster: dict
    median_eam: float
    round1: RoundProjection
    round2: RoundProjection | None


def pollster_accuracy(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, float], float]:
    years = ", ".join(str(y) for y in config.PROJECTION_HISTORY_YEARS)
    df = con.execute(f"""
        SELECT pollster_display_name, AVG(mae_top2) AS eam
        FROM poll_level_metrics
        WHERE LOWER(cargo) = 'presidente' AND year IN ({years})
        GROUP BY pollster_display_name
    """).fetchdf()
    eam = dict(zip(df["pollster_display_name"], df["eam"].astype(float)))
    median = float(np.median(list(eam.values()))) if eam else 1.0
    return eam, median


def historical_sigma_margin(con: duckdb.DuckDBPyConnection) -> float:
    years = ", ".join(str(y) for y in config.PROJECTION_HISTORY_YEARS)
    df = con.execute(f"""
        SELECT year, round, AVG(predicted_margin) - AVG(actual_margin) AS err
        FROM poll_level_metrics
        WHERE LOWER(cargo) = 'presidente' AND year IN ({years})
        GROUP BY year, round
    """).fetchdf()
    rmse = float(np.sqrt(np.mean(np.square(df["err"].values)))) if len(df) else 0.0
    return max(rmse, config.PROJECTION_SIGMA_FLOOR)


def main_scenarios(polls: pd.DataFrame, turno: int) -> pd.DataFrame:
    df = polls[polls["turno"] == turno]
    if df.empty:
        return df
    if turno == 1:
        sizes = (df[df["is_valid_candidate"]].groupby(["poll_id", "cenario_idx"]).size()
                 .rename("n_valid").reset_index())
        best = sizes.sort_values(["poll_id", "n_valid", "cenario_idx"], ascending=[True, False, True]) \
                    .drop_duplicates("poll_id")[["poll_id", "cenario_idx"]]
    else:
        pair = {candidate_key(n) for n in config.PROJECTION_RUNOFF_PAIR}
        has = (df[df["candidate_key"].isin(pair)].groupby(["poll_id", "cenario_idx"])["candidate_key"]
               .nunique().rename("k").reset_index())
        best = has[has["k"] == len(pair)].drop_duplicates("poll_id")[["poll_id", "cenario_idx"]]
    return df.merge(best, on=["poll_id", "cenario_idx"], how="inner")


def select_window(polls: pd.DataFrame, as_of: date, window_days: int) -> pd.DataFrame:
    if polls.empty:
        return polls
    end = pd.Timestamp(as_of)
    start = end - pd.Timedelta(days=window_days)
    df = polls[(polls["data"] > start) & (polls["data"] <= end)]
    latest = (df.groupby("pollster_display_name")["data"].transform("max"))
    df = df[df["data"] == latest]
    # if a pollster released two polls on the same day keep the larger poll_id (later entry)
    keep = df.groupby("pollster_display_name")["poll_id"].transform("max")
    return df[df["poll_id"] == keep].copy()


def add_weights(polls: pd.DataFrame, as_of: date, eam_by_pollster: dict, median_eam: float) -> pd.DataFrame:
    df = polls.copy()
    eam = df["pollster_display_name"].map(eam_by_pollster).fillna(median_eam).astype(float)
    df["eam_hist"] = df["pollster_display_name"].map(eam_by_pollster)
    df["w_acc"] = median_eam / eam
    df["age_days"] = (pd.Timestamp(as_of) - df["data"]).dt.days.clip(lower=0)
    df["w_rec"] = np.exp(-df["age_days"] / config.PROJECTION_RECENCY_TAU_DAYS)
    n = df["entrevistas"].fillna(config.PROJECTION_REFERENCE_SAMPLE).astype(float)
    df["w_n"] = np.sqrt(n / config.PROJECTION_REFERENCE_SAMPLE).clip(upper=2.0)
    df["weight"] = df["w_acc"] * df["w_rec"] * df["w_n"]
    return df


def _rebase(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["is_valid_candidate"] & df["percentual"].notna()].copy()
    totals = valid.groupby("poll_id")["percentual"].transform("sum")
    valid["valid_pct"] = valid["percentual"] / totals * 100.0
    return valid


def weighted_estimate(polls: pd.DataFrame) -> pd.DataFrame:
    valid = _rebase(polls)
    rows = []
    for key, g in valid.groupby("candidate_key"):
        w = g["weight"].values
        rows.append({"candidate_key": key,
                     "candidate": g["nome_candidato"].mode().iloc[0],
                     "partido": g["partido"].dropna().mode().iloc[0] if g["partido"].notna().any() else "",
                     "n_polls": g["poll_id"].nunique(),
                     "weighted_pct": float(np.average(g["valid_pct"].values, weights=w)),
                     "simple_pct": float(g["valid_pct"].mean())})
    est = pd.DataFrame(rows)
    for col in ("weighted_pct", "simple_pct"):
        est[col] = est[col] / est[col].sum() * 100.0
    return est.sort_values("weighted_pct", ascending=False).reset_index(drop=True)


def simulate(estimate: pd.DataFrame, sigma_margin: float, sigma_other: float,
             n_sims: int, rng: np.random.Generator) -> np.ndarray:
    base = estimate["weighted_pct"].values.astype(float)
    k = len(base)
    sims = np.tile(base, (n_sims, 1))
    delta = rng.normal(0.0, sigma_margin, size=n_sims)
    sims[:, 0] += delta / 2.0
    if k > 1:
        sims[:, 1] -= delta / 2.0
    if k > 2:
        sims[:, 2:] += rng.normal(0.0, sigma_other, size=(n_sims, k - 2))
    sims = np.clip(sims, 0.0, None)
    sims = sims / sims.sum(axis=1, keepdims=True) * 100.0
    return sims


def summarize(estimate: pd.DataFrame, sims: np.ndarray) -> tuple[pd.DataFrame, float]:
    order = np.argsort(-sims, axis=1)
    first = order[:, 0]
    top2 = order[:, :2]
    out = estimate.copy()
    out["ci_low"] = np.percentile(sims, 5, axis=0)
    out["ci_high"] = np.percentile(sims, 95, axis=0)
    out["p_first"] = [float(np.mean(first == i)) for i in range(sims.shape[1])]
    out["p_top2"] = [float(np.mean(np.any(top2 == i, axis=1))) for i in range(sims.shape[1])]
    p_decided = float(np.mean(sims.max(axis=1) > 50.0))
    return out, p_decided


def project_round(polls_2026: pd.DataFrame, turno: int, as_of: date, window_days: int,
                  eam: dict, median_eam: float, sigma_margin: float, sigma_other: float,
                  n_sims: int, rng: np.random.Generator) -> RoundProjection | None:
    df = select_window(main_scenarios(polls_2026, turno), as_of, window_days)
    if df.empty:
        return None
    df = add_weights(df, as_of, eam, median_eam)
    est = weighted_estimate(df)
    sims = simulate(est, sigma_margin, sigma_other, n_sims, rng)
    summary, p_decided = summarize(est, sims)
    return RoundProjection(turno=turno, polls=df, estimate=summary, sims=sims, p_decided=p_decided)


def project_election(con: duckdb.DuckDBPyConnection, as_of: date | None = None,
                     window_days: int = config.PROJECTION_WINDOW_DAYS,
                     n_sims: int = config.PROJECTION_N_SIMS,
                     data_dir: pathlib.Path | None = None) -> ProjectionResult:
    as_of = as_of or date.today()
    polls = con.execute("SELECT * FROM polls_2026").fetchdf()
    polls["data"] = pd.to_datetime(polls["data"])
    eam, median_eam = pollster_accuracy(con)
    sigma_margin = historical_sigma_margin(con)
    sigma_other = config.PROJECTION_SIGMA_OTHER
    rng = np.random.default_rng(config.PROJECTION_SEED)
    click.echo(f"Projecting as of {as_of} (window {window_days}d, sigma_margin {sigma_margin:.2f}, {n_sims} sims)...")
    r1 = project_round(polls, 1, as_of, window_days, eam, median_eam, sigma_margin, sigma_other, n_sims, rng)
    if r1 is None:
        raise click.ClickException("No first-round polls in the window.")
    r2 = project_round(polls, 2, as_of, window_days, eam, median_eam, sigma_margin, sigma_other, n_sims, rng)
    result = ProjectionResult(as_of, window_days, sigma_margin, sigma_other, n_sims, eam, median_eam, r1, r2)
    _persist(con, result, data_dir)
    return result


def _persist(con, result: ProjectionResult, data_dir: pathlib.Path | None) -> None:
    summaries, used = [], []
    for rp in (result.round1, result.round2):
        if rp is None:
            continue
        s = rp.estimate.copy(); s.insert(0, "turno", rp.turno); s["as_of"] = pd.Timestamp(result.as_of)
        summaries.append(s)
        u = rp.polls.copy(); u["as_of"] = pd.Timestamp(result.as_of)
        used.append(u)
    summary_df = pd.concat(summaries, ignore_index=True)
    used_df = pd.concat(used, ignore_index=True)
    con.execute("CREATE OR REPLACE TABLE projection_2026_summary AS SELECT * FROM summary_df")
    con.execute("CREATE OR REPLACE TABLE projection_2026_polls AS SELECT * FROM used_df")
    if data_dir is not None:
        pq = data_dir / "parquet"; pq.mkdir(parents=True, exist_ok=True)
        summary_df.to_parquet(pq / "projection_2026_summary.parquet", index=False)
        used_df.to_parquet(pq / "projection_2026_polls.parquet", index=False)
```

- [ ] **Step 3: Run tests, commit** — `feat: 2026 projection core (weights, estimate, Monte Carlo)`

---

### Task 5: Projection HTML report + CLI `project`

**Files:** Create `src/pollster/stages/project_report.py`; Modify `src/pollster/cli.py`; Test `tests/test_project_report.py`.

- [ ] **Step 1: Failing test**

```python
from datetime import date
import numpy as np, pandas as pd
from pollster.stages import project as P
from pollster.stages.project_report import generate_projection_report

def test_generate_projection_report_writes_html(tmp_data_dir):
    est = pd.DataFrame({"candidate_key": ["lula", "flavio"], "candidate": ["Lula", "Flávio Bolsonaro"],
                        "partido": ["PT", "PL"], "n_polls": [2, 2], "weighted_pct": [52.0, 48.0], "simple_pct": [52.0, 48.0]})
    sims = P.simulate(est, 3.0, 1.5, 500, np.random.default_rng(0))
    summary, p_dec = P.summarize(est, sims)
    polls = pd.DataFrame({"poll_id": [1], "pollster_display_name": ["Datafolha"], "data": [pd.Timestamp("2026-09-16")],
                          "entrevistas": [2000], "nome_candidato": ["Lula"], "candidate_key": ["lula"], "partido": ["PT"],
                          "percentual": [46.0], "is_valid_candidate": [True], "weight": [1.0], "w_acc": [1.0],
                          "w_rec": [1.0], "w_n": [1.0], "eam_hist": [4.0], "age_days": [7], "turno": [1], "cenario_idx": [0]})
    rp = P.RoundProjection(1, polls, summary, sims, p_dec)
    res = P.ProjectionResult(date(2026, 9, 23), 14, 3.0, 1.5, 500, {"Datafolha": 4.0}, 4.0, rp, None)
    out = tmp_data_dir / "reports" / "projecao_2026.html"
    generate_projection_report(res, polls, out)
    html = out.read_text()
    assert "Projecao" in html or "Projeção" in html
    assert "Lula" in html and "Flávio Bolsonaro" in html
    assert "<svg" in html
```

- [ ] **Step 2: Implement `src/pollster/stages/project_report.py`** — sections per spec (resumo, barras com IC, histograma da margem, serie temporal, tabela de pesquisas, metodologia), reusing `CSS`, `_fig_to_svg`, `_render_table` from `report.py`. Signature: `generate_projection_report(result: ProjectionResult, all_polls: pd.DataFrame, output_path: pathlib.Path) -> None` (`all_polls` = full `polls_2026` frame for the time series; it may be the same as `result.round1.polls` in tests).

- [ ] **Step 3: CLI**

```python
@cli.command()
@click.option("--as-of", "as_of", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Reference date (default: today).")
@click.option("--window-days", default=config.PROJECTION_WINDOW_DAYS, type=int, show_default=True)
@click.option("--sims", default=config.PROJECTION_N_SIMS, type=int, show_default=True)
def project(as_of, window_days, sims):
    """Project the 2026 presidential election (1st and 2nd round) from recent polls."""
    from pollster.stages.project import project_election
    from pollster.stages.project_report import generate_projection_report
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    result = project_election(con, as_of=as_of.date() if as_of else None,
                              window_days=window_days, n_sims=sims, data_dir=data_dir)
    all_polls = con.execute("SELECT * FROM polls_2026").fetchdf()
    output_path = data_dir / "reports" / "projecao_2026.html"
    generate_projection_report(result, all_polls, output_path)
    con.close()
    click.echo(f"Projection report written to {output_path}")
```

- [ ] **Step 4: Run tests, run `pollster project` for real, open/inspect HTML, commit** — `feat: 2026 projection report and CLI`

---

### Task 6: README + memory

- [ ] Add a "Projecao 2026" section to `README.md` (commands `fetch-2026 --force` and `project`, where the report lands, one-paragraph method + caveats). Commit `docs: 2026 projection usage`.
- [ ] Update the memory file `project_pollster_tool.md` with the Poder360 backend endpoint and the 2026 workflow.

---

## Self-review

- Spec coverage: fetch (T3), parser quirks (T2), weights/estimate/sigma/MC/runoff/persist (T4), report (T5), CLI (T3, T5), tests (each task), README (T6). Rebase bug fix (T0) added beyond spec, flagged to the user.
- Names consistent: `polls_to_frame`, `candidate_key`, `main_scenarios`, `select_window`, `add_weights`, `weighted_estimate`, `simulate`, `summarize`, `project_election`, `generate_projection_report`.
