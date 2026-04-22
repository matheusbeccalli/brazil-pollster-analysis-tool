# Pollster Accuracy Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that ranks Brazilian polling institutes by prediction accuracy against official election results, using pre-parsed data from Base dos Dados stored locally in DuckDB.

**Architecture:** 4-stage pipeline (fetch → assemble → analyze → report) with DuckDB + Parquet local storage. Data sourced from Google BigQuery public datasets via the `basedosdados` Python package. CLI built with Click. All domain knowledge centralized in `config.py`.

**Tech Stack:** Python 3.10+, click, duckdb, basedosdados, google-cloud-bigquery, pandas, pyarrow, numpy, matplotlib, rapidfuzz

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/pollster/__init__.py`
- Create: `src/pollster/cli.py`
- Create: `src/pollster/stages/__init__.py`
- Create: `src/pollster/utils/__init__.py`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pollster"
version = "0.1.0"
description = "Brazilian election pollster accuracy analysis tool"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "duckdb>=1.0",
    "basedosdados>=2.0",
    "google-cloud-bigquery>=3.0",
    "pandas>=2.0",
    "pyarrow>=14.0",
    "numpy>=1.24",
    "matplotlib>=3.7",
    "rapidfuzz>=3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-tmp-files>=0.0.2",
]

[project.scripts]
pollster = "pollster.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/pollster"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create package structure**

Create these empty `__init__.py` files:
- `src/pollster/__init__.py`
- `src/pollster/stages/__init__.py`
- `src/pollster/utils/__init__.py`
- `tests/__init__.py`

Create `tests/conftest.py`:
```python
import pathlib
import duckdb
import pandas as pd
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    (tmp_path / "parquet").mkdir()
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture
def tmp_db(tmp_data_dir):
    db_path = tmp_data_dir / "pollster.duckdb"
    con = duckdb.connect(str(db_path))
    yield con
    con.close()
```

- [ ] **Step 3: Create `.gitignore`**

```gitignore
data/
__pycache__/
*.egg-info/
dist/
.eggs/
*.pyc
.venv/
```

- [ ] **Step 4: Create CLI skeleton `src/pollster/cli.py`**

```python
import click


@click.group()
def cli():
    """Brazilian election pollster accuracy analysis tool."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch(force):
    """Download poll and results data from Base dos Dados."""
    click.echo("Fetch not yet implemented.")


@cli.command()
def assemble():
    """Build unified polls-vs-actual dataset."""
    click.echo("Assemble not yet implemented.")


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
def analyze(since):
    """Compute accuracy metrics and pollster rankings."""
    click.echo("Analyze not yet implemented.")


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
def report(since):
    """Generate HTML accuracy report."""
    click.echo("Report not yet implemented.")


@cli.command()
@click.option("--since", default=2014, type=int, help="Start year for analysis window.")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def run(since, force):
    """Run full pipeline: fetch → assemble → analyze → report."""
    click.echo("Run not yet implemented.")


@cli.command()
@click.argument("sql")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "csv", "json"]))
def query(sql, fmt):
    """Run ad-hoc SQL against the local DuckDB database."""
    click.echo("Query not yet implemented.")
```

- [ ] **Step 5: Install in development mode and verify**

Run: `cd /home/mathe/programming/brazil-pollster-analysis-tool && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: Installation succeeds.

Run: `pollster --help`
Expected: Shows help with subcommands: fetch, assemble, analyze, report, run, query.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/ .gitignore
git commit -m "feat: project scaffolding with CLI skeleton"
```

---

### Task 2: Configuration

**Files:**
- Create: `src/pollster/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write test for config**

```python
# tests/test_config.py
from pollster.config import ELECTIONS, PARTY_LEANING, POLLSTER_MERGES


def test_elections_have_both_rounds():
    for year, dates in ELECTIONS.items():
        assert "round_1" in dates, f"{year} missing round_1"
        assert "round_2" in dates, f"{year} missing round_2"


def test_elections_cover_required_years():
    for year in [2014, 2018, 2022]:
        assert year in ELECTIONS, f"Missing election year {year}"


def test_party_leaning_has_major_parties():
    assert PARTY_LEANING["PT"] == "left"
    assert PARTY_LEANING["PL"] == "right"
    assert PARTY_LEANING["MDB"] == "center"


def test_pollster_merges_ibope_ipec():
    assert POLLSTER_MERGES.get("Ibope") == POLLSTER_MERGES.get("Ipec")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Implement `src/pollster/config.py`**

```python
from datetime import date

ELECTIONS: dict[int, dict[str, date]] = {
    2002: {"round_1": date(2002, 10, 6), "round_2": date(2002, 10, 27)},
    2006: {"round_1": date(2006, 10, 1), "round_2": date(2006, 10, 29)},
    2010: {"round_1": date(2010, 10, 3), "round_2": date(2010, 10, 31)},
    2014: {"round_1": date(2014, 10, 5), "round_2": date(2014, 10, 26)},
    2018: {"round_1": date(2018, 10, 7), "round_2": date(2018, 10, 28)},
    2022: {"round_1": date(2022, 10, 2), "round_2": date(2022, 10, 30)},
}

DEFAULT_SINCE_YEAR = 2014

PARTY_LEANING: dict[str, str] = {
    # Left
    "PT": "left",
    "PSOL": "left",
    "PCdoB": "left",
    "PDT": "left",
    "PCB": "left",
    "PCO": "left",
    "PSTU": "left",
    "UP": "left",
    "REDE": "left",
    "PV": "left",
    "PSB": "left",
    # Center
    "MDB": "center",
    "PMDB": "center",
    "PSD": "center",
    "CIDADANIA": "center",
    "PPS": "center",
    "PODE": "center",
    "SOLIDARIEDADE": "center",
    "SD": "center",
    "AVANTE": "center",
    "PMN": "center",
    "PROS": "center",
    # Right
    "PSDB": "right",
    "PL": "right",
    "PP": "right",
    "DEM": "right",
    "PFL": "right",
    "REPUBLICANOS": "right",
    "PRB": "right",
    "PTB": "right",
    "PSC": "right",
    "PATRIOTA": "right",
    "PSL": "right",
    "NOVO": "right",
    "UNIÃO": "right",
    "UNIÃO BRASIL": "right",
}

POLLSTER_MERGES: dict[str, str] = {
    "Ibope": "IBOPE/Ipec",
    "IBOPE": "IBOPE/Ipec",
    "Ibope Inteligência": "IBOPE/Ipec",
    "Ipec": "IBOPE/Ipec",
    "IPEC": "IBOPE/Ipec",
}

POLLSTER_ALIASES: dict[str, str] = {
    "Instituto Datafolha": "Datafolha",
    "Datafolha Instituto de Pesquisas": "Datafolha",
}

BIGQUERY_BILLING_PROJECT: str | None = None

BIGQUERY_TABLES = {
    "polls": "basedosdados.br_poder360_pesquisas.microdados",
    "results": "basedosdados.br_tse_eleicoes.resultados_candidato",
    "candidates": "basedosdados.br_tse_eleicoes.candidatos",
}

DATA_DIR_NAME = "data"
DB_FILENAME = "pollster.duckdb"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pollster/config.py tests/test_config.py
git commit -m "feat: add config with election dates, party leanings, pollster merges"
```

---

### Task 3: DuckDB Helper

**Files:**
- Create: `src/pollster/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write test for db helper**

```python
# tests/test_db.py
import duckdb
import pandas as pd

from pollster.db import get_connection, register_parquet, query_to_df


def test_get_connection(tmp_data_dir):
    con = get_connection(tmp_data_dir)
    result = con.execute("SELECT 1 AS x").fetchone()
    assert result == (1,)
    con.close()


def test_register_parquet(tmp_data_dir):
    parquet_dir = tmp_data_dir / "parquet"
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    path = parquet_dir / "test.parquet"
    df.to_parquet(path)

    con = get_connection(tmp_data_dir)
    register_parquet(con, "test_table", path)
    result = con.execute("SELECT COUNT(*) FROM test_table").fetchone()
    assert result == (2,)
    con.close()


def test_query_to_df(tmp_data_dir):
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE t AS SELECT 1 AS x, 'hello' AS y")
    df = query_to_df(con, "SELECT * FROM t")
    assert len(df) == 1
    assert df.iloc[0]["y"] == "hello"
    con.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/pollster/db.py`**

```python
import pathlib
import duckdb
import pandas as pd

from pollster.config import DB_FILENAME


def get_connection(data_dir: pathlib.Path) -> duckdb.DuckDBPyConnection:
    db_path = data_dir / DB_FILENAME
    return duckdb.connect(str(db_path))


def register_parquet(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    parquet_path: pathlib.Path,
) -> None:
    con.execute(
        f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{parquet_path}'"
    )


def query_to_df(
    con: duckdb.DuckDBPyConnection, sql: str
) -> pd.DataFrame:
    return con.execute(sql).fetchdf()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pollster/db.py tests/test_db.py
git commit -m "feat: add DuckDB connection helper"
```

---

### Task 4: Utility Functions

**Files:**
- Create: `src/pollster/utils/normalize.py`
- Create: `src/pollster/utils/rebase.py`
- Create: `src/pollster/utils/candidates.py`
- Create: `tests/test_normalize.py`
- Create: `tests/test_rebase.py`
- Create: `tests/test_candidates.py`

- [ ] **Step 1: Write test for pollster normalization**

```python
# tests/test_normalize.py
from pollster.utils.normalize import normalize_pollster_name


def test_merge_ibope_ipec():
    assert normalize_pollster_name("Ibope") == "IBOPE/Ipec"
    assert normalize_pollster_name("Ipec") == "IBOPE/Ipec"
    assert normalize_pollster_name("IBOPE") == "IBOPE/Ipec"


def test_alias_datafolha():
    assert normalize_pollster_name("Instituto Datafolha") == "Datafolha"
    assert normalize_pollster_name("Datafolha Instituto de Pesquisas") == "Datafolha"


def test_unknown_pollster_passes_through():
    assert normalize_pollster_name("AtlasIntel") == "AtlasIntel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/pollster/utils/normalize.py`**

```python
from pollster.config import POLLSTER_MERGES, POLLSTER_ALIASES


def normalize_pollster_name(raw_name: str) -> str:
    if raw_name in POLLSTER_MERGES:
        return POLLSTER_MERGES[raw_name]
    if raw_name in POLLSTER_ALIASES:
        return POLLSTER_ALIASES[raw_name]
    return raw_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_normalize.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Write test for rebase**

```python
# tests/test_rebase.py
import pytest
from pollster.utils.rebase import rebase_to_valid_votes


def test_rebase_basic():
    raw_pcts = {"Lula": 45.0, "Bolsonaro": 35.0, "Tebet": 8.0, "Ciro": 6.0}
    result = rebase_to_valid_votes(raw_pcts)
    total = sum(result.values())
    assert abs(total - 100.0) < 0.01
    assert result["Lula"] == pytest.approx(47.87, abs=0.01)
    assert result["Bolsonaro"] == pytest.approx(37.23, abs=0.01)


def test_rebase_already_sums_to_100():
    raw_pcts = {"A": 60.0, "B": 40.0}
    result = rebase_to_valid_votes(raw_pcts)
    assert result["A"] == pytest.approx(60.0)
    assert result["B"] == pytest.approx(40.0)


def test_rebase_with_undecided_gap():
    raw_pcts = {"A": 40.0, "B": 30.0}
    result = rebase_to_valid_votes(raw_pcts)
    assert result["A"] == pytest.approx(57.14, abs=0.01)
    assert result["B"] == pytest.approx(42.86, abs=0.01)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_rebase.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 7: Implement `src/pollster/utils/rebase.py`**

```python
def rebase_to_valid_votes(raw_pcts: dict[str, float]) -> dict[str, float]:
    total = sum(raw_pcts.values())
    if total == 0:
        return raw_pcts
    return {name: (pct / total) * 100.0 for name, pct in raw_pcts.items()}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_rebase.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 9: Write test for candidate matching**

```python
# tests/test_candidates.py
from pollster.utils.candidates import match_candidate_name


def test_exact_match_after_normalization():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("Luiz Inácio Lula da Silva", officials) == "LUIZ INACIO LULA DA SILVA"


def test_fuzzy_match_partial_name():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("LULA", officials) is None  # too short for fuzzy


def test_fuzzy_match_close_name():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("JAIR BOLSONARO", officials) == "JAIR MESSIAS BOLSONARO"


def test_no_match():
    officials = ["LUIZ INACIO LULA DA SILVA"]
    assert match_candidate_name("SIMONE TEBET", officials) is None


def test_party_fallback():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    parties = {"LUIZ INACIO LULA DA SILVA": "PT", "JAIR MESSIAS BOLSONARO": "PL"}
    assert match_candidate_name("LULA", officials, poll_party="PT", official_parties=parties) == "LUIZ INACIO LULA DA SILVA"
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_candidates.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 11: Implement `src/pollster/utils/candidates.py`**

```python
import unicodedata
from rapidfuzz import fuzz


def _normalize_name(name: str) -> str:
    name = name.upper().strip()
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def match_candidate_name(
    poll_name: str,
    official_names: list[str],
    poll_party: str | None = None,
    official_parties: dict[str, str] | None = None,
    fuzzy_threshold: float = 92.0,
) -> str | None:
    norm_poll = _normalize_name(poll_name)

    for official in official_names:
        if _normalize_name(official) == norm_poll:
            return official

    best_score = 0.0
    best_match = None
    for official in official_names:
        score = fuzz.WRatio(norm_poll, _normalize_name(official))
        if score > best_score:
            best_score = score
            best_match = official
    if best_score >= fuzzy_threshold and best_match is not None:
        return best_match

    if poll_party and official_parties:
        matches = [name for name, party in official_parties.items() if party == poll_party]
        if len(matches) == 1:
            return matches[0]

    return None
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_candidates.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 13: Commit**

```bash
git add src/pollster/utils/ tests/test_normalize.py tests/test_rebase.py tests/test_candidates.py
git commit -m "feat: add utility functions for normalization, rebasing, candidate matching"
```

---

### Task 5: Fetch Stage

**Files:**
- Create: `src/pollster/stages/fetch.py`
- Modify: `src/pollster/cli.py` — wire up fetch command
- Create: `tests/test_fetch.py`

- [ ] **Step 1: Write test for fetch**

The fetch stage hits BigQuery in production. Tests mock the BigQuery call and verify the Parquet + DuckDB registration logic.

```python
# tests/test_fetch.py
import pandas as pd
import pytest
from unittest.mock import patch

from pollster.stages.fetch import fetch_data, _save_and_register


@pytest.fixture
def sample_polls_df():
    return pd.DataFrame({
        "id_pesquisa": ["P1", "P1", "P2", "P2"],
        "id_cenario": ["C1", "C1", "C1", "C1"],
        "id_candidato_poder360": ["1", "2", "1", "2"],
        "ano": [2022, 2022, 2022, 2022],
        "data": pd.to_datetime(["2022-09-30", "2022-09-30", "2022-09-28", "2022-09-28"]),
        "data_referencia": ["2022-10", "2022-10", "2022-10", "2022-10"],
        "turno": [1, 1, 1, 1],
        "cargo": ["PRESIDENTE", "PRESIDENTE", "PRESIDENTE", "PRESIDENTE"],
        "sigla_uf": ["BR", "BR", "BR", "BR"],
        "nome_municipio": [None, None, None, None],
        "instituto": ["Datafolha", "Datafolha", "AtlasIntel", "AtlasIntel"],
        "contratante": ["Folha", "Folha", "proprio", "proprio"],
        "orgao_registro": ["TSE", "TSE", "TSE", "TSE"],
        "numero_registro": ["BR-001/2022", "BR-001/2022", "BR-002/2022", "BR-002/2022"],
        "quantidade_entrevistas": [2000.0, 2000.0, 3000.0, 3000.0],
        "margem_mais": [2.0, 2.0, 1.5, 1.5],
        "margem_menos": [2.0, 2.0, 1.5, 1.5],
        "tipo": ["estimulada", "estimulada", "estimulada", "estimulada"],
        "tipo_voto": [None, None, None, None],
        "descricao_cenario": ["cenario 1", "cenario 1", "cenario 1", "cenario 1"],
        "nome_candidato": ["LULA", "BOLSONARO", "LULA", "BOLSONARO"],
        "sigla_partido": ["PT", "PL", "PT", "PL"],
        "condicao": [1, 1, 1, 1],
        "percentual": [48.0, 34.0, 50.5, 36.2],
    })


def test_save_and_register(tmp_data_dir, sample_polls_df):
    from pollster.db import get_connection

    parquet_path = tmp_data_dir / "parquet" / "test.parquet"
    con = get_connection(tmp_data_dir)

    _save_and_register(con, sample_polls_df, "test_table", parquet_path)

    assert parquet_path.exists()
    result = con.execute("SELECT COUNT(*) FROM test_table").fetchone()
    assert result == (4,)
    con.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetch.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/pollster/stages/fetch.py`**

```python
import pathlib
import click
import duckdb
import pandas as pd

from pollster.config import BIGQUERY_BILLING_PROJECT, BIGQUERY_TABLES
from pollster.db import get_connection, register_parquet


POLLS_QUERY = f"""
SELECT *
FROM `{BIGQUERY_TABLES['polls']}`
WHERE LOWER(cargo) IN ('presidente', 'governador')
"""

RESULTS_QUERY = f"""
SELECT *
FROM `{BIGQUERY_TABLES['results']}`
WHERE LOWER(cargo) IN ('presidente', 'governador')
"""

CANDIDATES_QUERY = f"""
SELECT ano, tipo_eleicao, sigla_uf, cargo, numero_candidato,
       sequencial_candidato, id_candidato_bd, nome, nome_urna, sigla_partido
FROM `{BIGQUERY_TABLES['candidates']}`
WHERE LOWER(cargo) IN ('presidente', 'governador')
"""


def _resolve_billing_project() -> str:
    import os
    project = BIGQUERY_BILLING_PROJECT or os.environ.get("BIGQUERY_PROJECT")
    if not project:
        raise click.ClickException(
            "Set BIGQUERY_PROJECT env var or BIGQUERY_BILLING_PROJECT in config.py. "
            "This is your Google Cloud project ID for billing (free tier, no cost)."
        )
    return project


def _download_from_bigquery(query: str, billing_project: str) -> pd.DataFrame:
    import basedosdados as bd
    return bd.read_sql(query, billing_project_id=billing_project)


def _save_and_register(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table_name: str,
    parquet_path: pathlib.Path,
) -> None:
    df.to_parquet(parquet_path, index=False)
    register_parquet(con, table_name, parquet_path)


def fetch_data(data_dir: pathlib.Path, force: bool = False) -> None:
    parquet_dir = data_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)

    polls_path = parquet_dir / "poder360_pesquisas.parquet"
    results_path = parquet_dir / "tse_resultados_candidato.parquet"
    candidates_path = parquet_dir / "tse_candidatos.parquet"

    con = get_connection(data_dir)

    if polls_path.exists() and not force:
        click.echo(f"Polls data already exists at {polls_path}. Use --force to re-download.")
        register_parquet(con, "poder360_polls", polls_path)
    else:
        billing = _resolve_billing_project()
        click.echo("Downloading poll data from Base dos Dados...")
        polls_df = _download_from_bigquery(POLLS_QUERY, billing)
        click.echo(f"  → {len(polls_df)} rows downloaded.")
        _save_and_register(con, polls_df, "poder360_polls", polls_path)

    if results_path.exists() and not force:
        click.echo(f"Results data already exists at {results_path}. Use --force to re-download.")
        register_parquet(con, "tse_results", results_path)
    else:
        billing = _resolve_billing_project()
        click.echo("Downloading election results from Base dos Dados...")
        results_df = _download_from_bigquery(RESULTS_QUERY, billing)
        click.echo(f"  → {len(results_df)} rows downloaded.")
        _save_and_register(con, results_df, "tse_results", results_path)

    if candidates_path.exists() and not force:
        click.echo(f"Candidates data already exists at {candidates_path}. Use --force to re-download.")
        register_parquet(con, "tse_candidates", candidates_path)
    else:
        billing = _resolve_billing_project()
        click.echo("Downloading candidate data from Base dos Dados...")
        candidates_df = _download_from_bigquery(CANDIDATES_QUERY, billing)
        click.echo(f"  → {len(candidates_df)} rows downloaded.")
        _save_and_register(con, candidates_df, "tse_candidates", candidates_path)

    con.close()
    click.echo("Fetch complete.")
```

- [ ] **Step 4: Wire up CLI — update `src/pollster/cli.py`**

Replace the `fetch` command body:

```python
@cli.command()
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch(force):
    """Download poll and results data from Base dos Dados."""
    from pollster.stages.fetch import fetch_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    fetch_data(data_dir, force=force)
```

Add at the top of `cli.py`:
```python
import pathlib
from pollster import config
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_fetch.py -v`
Expected: All tests PASS (the test only exercises `_save_and_register`, not BigQuery).

- [ ] **Step 6: Commit**

```bash
git add src/pollster/stages/fetch.py src/pollster/cli.py tests/test_fetch.py
git commit -m "feat: implement fetch stage (download from Base dos Dados)"
```

---

### Task 6: Assemble Stage

**Files:**
- Create: `src/pollster/stages/assemble.py`
- Modify: `src/pollster/cli.py` — wire up assemble command
- Create: `tests/test_assemble.py`

- [ ] **Step 1: Write test fixture data**

Create a shared fixture module with realistic test data:

```python
# tests/fixtures.py
import pandas as pd
import numpy as np


def make_polls_df():
    """Minimal realistic poll data for 2022 presidential round 1."""
    rows = []
    # Datafolha poll - 2022-09-30 (final before R1 on Oct 2)
    for cand, party, pct in [("LULA", "PT", 48.0), ("BOLSONARO", "PL", 34.0),
                              ("TEBET", "MDB", 8.0), ("CIRO", "PDT", 6.0)]:
        rows.append({
            "id_pesquisa": "P1", "id_cenario": "C1",
            "id_candidato_poder360": f"cand_{cand}",
            "ano": 2022, "data": pd.Timestamp("2022-09-30"),
            "data_referencia": "2022-10", "turno": 1,
            "cargo": "Presidente", "sigla_uf": "BR", "nome_municipio": None,
            "instituto": "Datafolha", "contratante": "Folha",
            "orgao_registro": "TSE", "numero_registro": "BR-001/2022",
            "quantidade_entrevistas": 2000.0,
            "margem_mais": 2.0, "margem_menos": 2.0,
            "tipo": "estimulada", "tipo_voto": None,
            "descricao_cenario": "cenario 1",
            "nome_candidato": cand, "sigla_partido": party,
            "condicao": 1, "percentual": pct,
        })
    # AtlasIntel poll - 2022-10-01 (also before R1)
    for cand, party, pct in [("LULA", "PT", 50.5), ("BOLSONARO", "PL", 36.2),
                              ("TEBET", "MDB", 5.5), ("CIRO", "PDT", 4.8)]:
        rows.append({
            "id_pesquisa": "P2", "id_cenario": "C1",
            "id_candidato_poder360": f"cand_{cand}",
            "ano": 2022, "data": pd.Timestamp("2022-10-01"),
            "data_referencia": "2022-10", "turno": 1,
            "cargo": "Presidente", "sigla_uf": "BR", "nome_municipio": None,
            "instituto": "AtlasIntel", "contratante": "proprio",
            "orgao_registro": "TSE", "numero_registro": "BR-002/2022",
            "quantidade_entrevistas": 3000.0,
            "margem_mais": 1.5, "margem_menos": 1.5,
            "tipo": "estimulada", "tipo_voto": None,
            "descricao_cenario": "cenario 1",
            "nome_candidato": cand, "sigla_partido": party,
            "condicao": 1, "percentual": pct,
        })
    return pd.DataFrame(rows)


def make_results_df():
    """Official results for 2022 presidential round 1."""
    rows = []
    # Actual 2022 R1 results (simplified — total valid votes)
    for cand_num, seq, name, party, votes, resultado in [
        ("13", "seq1", "LUIZ INACIO LULA DA SILVA", "PT", 57259504, "2o turno"),
        ("22", "seq2", "JAIR MESSIAS BOLSONARO", "PL", 51072345, "2o turno"),
        ("15", "seq3", "SIMONE NASSAR TEBET", "MDB", 4915423, "nao eleito"),
        ("12", "seq4", "CIRO FERREIRA GOMES", "PDT", 3599287, "nao eleito"),
    ]:
        rows.append({
            "ano": 2022, "turno": 1, "tipo_eleicao": "eleicao ordinaria",
            "sigla_uf": "BR", "id_municipio": None, "id_municipio_tse": None,
            "cargo": "presidente",
            "numero_partido": cand_num[:2], "sigla_partido": party,
            "numero_candidato": cand_num, "sequencial_candidato": seq,
            "id_candidato_bd": f"bd_{seq}",
            "resultado": resultado, "votos": votes,
        })
    return pd.DataFrame(rows)


def make_candidates_df():
    """Candidate details for resolving names."""
    rows = [
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero_candidato": "13", "sequencial_candidato": "seq1",
         "id_candidato_bd": "bd_seq1", "nome": "LUIZ INACIO LULA DA SILVA",
         "nome_urna": "LULA", "sigla_partido": "PT"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero_candidato": "22", "sequencial_candidato": "seq2",
         "id_candidato_bd": "bd_seq2", "nome": "JAIR MESSIAS BOLSONARO",
         "nome_urna": "BOLSONARO", "sigla_partido": "PL"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero_candidato": "15", "sequencial_candidato": "seq3",
         "id_candidato_bd": "bd_seq3", "nome": "SIMONE NASSAR TEBET",
         "nome_urna": "TEBET", "sigla_partido": "MDB"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero_candidato": "12", "sequencial_candidato": "seq4",
         "id_candidato_bd": "bd_seq4", "nome": "CIRO FERREIRA GOMES",
         "nome_urna": "CIRO", "sigla_partido": "PDT"},
    ]
    return pd.DataFrame(rows)
```

- [ ] **Step 2: Write test for assemble stage**

```python
# tests/test_assemble.py
import pytest
from tests.fixtures import make_polls_df, make_results_df, make_candidates_df
from pollster.db import get_connection, register_parquet
from pollster.stages.assemble import assemble_data


@pytest.fixture
def loaded_db(tmp_data_dir):
    parquet_dir = tmp_data_dir / "parquet"

    polls_df = make_polls_df()
    results_df = make_results_df()
    candidates_df = make_candidates_df()

    polls_df.to_parquet(parquet_dir / "poder360_pesquisas.parquet")
    results_df.to_parquet(parquet_dir / "tse_resultados_candidato.parquet")
    candidates_df.to_parquet(parquet_dir / "tse_candidatos.parquet")

    con = get_connection(tmp_data_dir)
    register_parquet(con, "poder360_polls", parquet_dir / "poder360_pesquisas.parquet")
    register_parquet(con, "tse_results", parquet_dir / "tse_resultados_candidato.parquet")
    register_parquet(con, "tse_candidates", parquet_dir / "tse_candidatos.parquet")
    con.close()
    return tmp_data_dir


def test_assemble_produces_polls_vs_actual(loaded_db):
    con = get_connection(loaded_db)
    assemble_data(con)

    result = con.execute("SELECT COUNT(*) FROM polls_vs_actual").fetchone()
    assert result[0] == 2  # one row per pollster (Datafolha, AtlasIntel)

    cols = [desc[0] for desc in con.execute("SELECT * FROM polls_vs_actual LIMIT 0").description]
    assert "pollster_display_name" in cols
    assert "candidate_1_poll_valid_pct" in cols
    assert "candidate_1_actual_valid_pct" in cols
    con.close()


def test_assemble_rebase_valid_votes(loaded_db):
    con = get_connection(loaded_db)
    assemble_data(con)

    row = con.execute(
        "SELECT candidate_1_poll_valid_pct, candidate_2_poll_valid_pct "
        "FROM polls_vs_actual WHERE pollster_display_name = 'Datafolha'"
    ).fetchone()
    # Datafolha: Lula 48%, Bolsonaro 34%, total named = 96%
    # Rebased: Lula = 48/96*100 = 50.0, Bolsonaro = 34/96*100 = 35.42
    assert abs(row[0] - 50.0) < 0.1
    assert abs(row[1] - 35.42) < 0.1
    con.close()


def test_assemble_candidate_matching(loaded_db):
    con = get_connection(loaded_db)
    assemble_data(con)

    row = con.execute(
        "SELECT candidate_1_name, candidate_2_name "
        "FROM polls_vs_actual WHERE pollster_display_name = 'Datafolha'"
    ).fetchone()
    assert "LULA" in row[0].upper() or "LUIZ" in row[0].upper()
    assert "BOLSONARO" in row[1].upper() or "JAIR" in row[1].upper()
    con.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_assemble.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement `src/pollster/stages/assemble.py`**

```python
import click
import duckdb
import pandas as pd

from pollster.config import ELECTIONS, PARTY_LEANING
from pollster.utils.normalize import normalize_pollster_name
from pollster.utils.rebase import rebase_to_valid_votes
from pollster.utils.candidates import match_candidate_name


def _build_actual_results(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        WITH aggregated AS (
            SELECT ano, turno, cargo, sigla_uf,
                   sequencial_candidato, sigla_partido,
                   SUM(votos) AS votos
            FROM tse_results
            WHERE votos IS NOT NULL
            GROUP BY ano, turno, cargo, sigla_uf, sequencial_candidato, sigla_partido
        )
        SELECT *,
               SUM(votos) OVER (PARTITION BY ano, turno, cargo, sigla_uf) AS total_votos,
               ROW_NUMBER() OVER (
                   PARTITION BY ano, turno, cargo, sigla_uf ORDER BY votos DESC
               ) AS rank
        FROM aggregated
    """).fetchdf()

    df["votos_validos_pct"] = df["votos"] / df["total_votos"] * 100.0
    top2 = df[df["rank"] <= 2].copy()

    candidates = con.execute("SELECT * FROM tse_candidates").fetchdf()
    top2 = top2.merge(
        candidates[["ano", "sequencial_candidato", "nome", "nome_urna", "sigla_partido"]].rename(
            columns={"sigla_partido": "cand_partido"}
        ),
        on=["ano", "sequencial_candidato"],
        how="left",
    )
    top2["nome_candidato"] = top2["nome_urna"].fillna(top2["nome"])
    return top2


def _select_final_polls(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    polls = con.execute("SELECT * FROM poder360_polls").fetchdf()
    polls["data"] = pd.to_datetime(polls["data"])

    rows = []
    for (ano, turno, cargo, uf, instituto), group in polls.groupby(
        ["ano", "turno", "cargo", "sigla_uf", "instituto"]
    ):
        election_dates = ELECTIONS.get(ano)
        if election_dates is None:
            continue
        round_key = f"round_{turno}"
        election_day = election_dates.get(round_key)
        if election_day is None:
            continue

        before = group[group["data"].dt.date <= election_day]
        if before.empty:
            continue

        latest_date = before["data"].max()
        latest_polls = before[before["data"] == latest_date]
        rows.append(latest_polls)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _select_scenario(poll_group: pd.DataFrame, top2_names: list[str],
                     top2_parties: dict[str, str]) -> pd.DataFrame | None:
    best = None
    best_count = -1
    for cenario, scenario_df in poll_group.groupby("id_cenario"):
        cands_in_scenario = scenario_df["nome_candidato"].tolist()
        parties_in_scenario = dict(zip(scenario_df["nome_candidato"], scenario_df["sigla_partido"]))
        matched = 0
        for official_name in top2_names:
            m = match_candidate_name(
                official_name, cands_in_scenario,
                official_parties=parties_in_scenario,
            )
            if m is not None:
                matched += 1
        if matched == 2 and len(scenario_df) > best_count:
            best = scenario_df
            best_count = len(scenario_df)
    return best


def assemble_data(con: duckdb.DuckDBPyConnection) -> None:
    click.echo("Building actual results from TSE data...")
    actual = _build_actual_results(con)

    click.echo("Selecting final polls per pollster per race...")
    final_polls = _select_final_polls(con)
    if final_polls.empty:
        click.echo("No matching polls found.")
        return

    output_rows = []

    for (ano, turno, cargo, uf), race_actual in actual.groupby(["ano", "turno", "cargo", "sigla_uf"]):
        if len(race_actual) < 2:
            continue
        top2 = race_actual.sort_values("votos", ascending=False).head(2)
        top2_names = top2["nome_candidato"].tolist()
        top2_parties = dict(zip(top2["nome_candidato"], top2["cand_partido"]))
        top2_actual_pcts = dict(zip(top2["nome_candidato"], top2["votos_validos_pct"]))
        top2_sigla_partidos = dict(zip(top2["nome_candidato"], top2["cand_partido"]))

        cargo_lower = cargo.lower() if isinstance(cargo, str) else str(cargo).lower()
        race_polls = final_polls[
            (final_polls["ano"] == ano) &
            (final_polls["turno"] == turno) &
            (final_polls["cargo"].str.lower() == cargo_lower) &
            (final_polls["sigla_uf"] == uf)
        ]

        for instituto, pollster_polls in race_polls.groupby("instituto"):
            scenario = _select_scenario(pollster_polls, top2_names, top2_parties)
            if scenario is None:
                continue

            raw_pcts = dict(zip(scenario["nome_candidato"], scenario["percentual"]))
            rebased = rebase_to_valid_votes(raw_pcts)

            matched_1 = match_candidate_name(
                top2_names[0], list(raw_pcts.keys()),
                poll_party=top2_sigla_partidos.get(top2_names[0]),
                official_parties=dict(zip(scenario["nome_candidato"], scenario["sigla_partido"])),
            )
            matched_2 = match_candidate_name(
                top2_names[1], list(raw_pcts.keys()),
                poll_party=top2_sigla_partidos.get(top2_names[1]),
                official_parties=dict(zip(scenario["nome_candidato"], scenario["sigla_partido"])),
            )
            if matched_1 is None or matched_2 is None:
                continue

            party_1 = top2_sigla_partidos.get(top2_names[0], "")
            party_2 = top2_sigla_partidos.get(top2_names[1], "")

            meta = scenario.iloc[0]
            output_rows.append({
                "year": ano,
                "round": turno,
                "cargo": cargo,
                "sigla_uf": uf,
                "pollster_display_name": normalize_pollster_name(instituto),
                "instituto_raw": instituto,
                "numero_registro": meta.get("numero_registro"),
                "poll_date": meta["data"],
                "sample_size": meta.get("quantidade_entrevistas"),
                "margin_plus": meta.get("margem_mais"),
                "margin_minus": meta.get("margem_menos"),
                "cenario_descricao": meta.get("descricao_cenario"),
                "candidate_1_name": top2_names[0],
                "candidate_1_party": party_1,
                "candidate_1_leaning": PARTY_LEANING.get(party_1, "unknown"),
                "candidate_1_poll_raw_pct": raw_pcts.get(matched_1, 0),
                "candidate_1_poll_valid_pct": rebased.get(matched_1, 0),
                "candidate_1_actual_valid_pct": top2_actual_pcts[top2_names[0]],
                "candidate_2_name": top2_names[1],
                "candidate_2_party": party_2,
                "candidate_2_leaning": PARTY_LEANING.get(party_2, "unknown"),
                "candidate_2_poll_raw_pct": raw_pcts.get(matched_2, 0),
                "candidate_2_poll_valid_pct": rebased.get(matched_2, 0),
                "candidate_2_actual_valid_pct": top2_actual_pcts[top2_names[1]],
            })

    if not output_rows:
        click.echo("No polls matched official results.")
        return

    result_df = pd.DataFrame(output_rows)
    con.execute("CREATE OR REPLACE TABLE polls_vs_actual AS SELECT * FROM result_df")
    click.echo(f"Assembled {len(result_df)} poll observations into polls_vs_actual.")
```

- [ ] **Step 5: Wire up CLI — update `src/pollster/cli.py`**

Replace the `assemble` command body:

```python
@cli.command()
def assemble():
    """Build unified polls-vs-actual dataset."""
    from pollster.stages.assemble import assemble_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    assemble_data(con)
    con.close()
```

Add at the top of `cli.py`:
```python
from pollster import db as db_module
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_assemble.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/pollster/stages/assemble.py src/pollster/cli.py tests/test_assemble.py tests/fixtures.py
git commit -m "feat: implement assemble stage (filter, rebase, join polls with results)"
```

---

### Task 7: Analyze Stage

**Files:**
- Create: `src/pollster/stages/analyze.py`
- Modify: `src/pollster/cli.py` — wire up analyze command
- Create: `tests/test_analyze.py`

- [ ] **Step 1: Write test for analyze stage**

```python
# tests/test_analyze.py
import pytest
import pandas as pd
import duckdb

from pollster.stages.analyze import analyze_data


@pytest.fixture
def db_with_assembled(tmp_data_dir):
    from pollster.db import get_connection
    con = get_connection(tmp_data_dir)
    assembled = pd.DataFrame([
        {
            "year": 2022, "round": 1, "cargo": "Presidente", "sigla_uf": "BR",
            "pollster_display_name": "Datafolha", "instituto_raw": "Datafolha",
            "numero_registro": "BR-001/2022",
            "poll_date": pd.Timestamp("2022-09-30"),
            "sample_size": 2000, "margin_plus": 2.0, "margin_minus": 2.0,
            "cenario_descricao": "cenario 1",
            "candidate_1_name": "LULA", "candidate_1_party": "PT",
            "candidate_1_leaning": "left",
            "candidate_1_poll_raw_pct": 48.0, "candidate_1_poll_valid_pct": 50.0,
            "candidate_1_actual_valid_pct": 48.43,
            "candidate_2_name": "BOLSONARO", "candidate_2_party": "PL",
            "candidate_2_leaning": "right",
            "candidate_2_poll_raw_pct": 34.0, "candidate_2_poll_valid_pct": 35.42,
            "candidate_2_actual_valid_pct": 43.20,
        },
        {
            "year": 2022, "round": 1, "cargo": "Presidente", "sigla_uf": "BR",
            "pollster_display_name": "AtlasIntel", "instituto_raw": "AtlasIntel",
            "numero_registro": "BR-002/2022",
            "poll_date": pd.Timestamp("2022-10-01"),
            "sample_size": 3000, "margin_plus": 1.5, "margin_minus": 1.5,
            "cenario_descricao": "cenario 1",
            "candidate_1_name": "LULA", "candidate_1_party": "PT",
            "candidate_1_leaning": "left",
            "candidate_1_poll_raw_pct": 50.5, "candidate_1_poll_valid_pct": 52.06,
            "candidate_1_actual_valid_pct": 48.43,
            "candidate_2_name": "BOLSONARO", "candidate_2_party": "PL",
            "candidate_2_leaning": "right",
            "candidate_2_poll_raw_pct": 36.2, "candidate_2_poll_valid_pct": 37.32,
            "candidate_2_actual_valid_pct": 43.20,
        },
    ])
    con.execute("CREATE TABLE polls_vs_actual AS SELECT * FROM assembled")
    yield con
    con.close()


def test_analyze_creates_poll_level_metrics(db_with_assembled):
    analyze_data(db_with_assembled, since=2014)
    result = db_with_assembled.execute("SELECT COUNT(*) FROM poll_level_metrics").fetchone()
    assert result[0] == 2


def test_analyze_mae_computation(db_with_assembled):
    analyze_data(db_with_assembled, since=2014)
    row = db_with_assembled.execute(
        "SELECT mae_top2 FROM poll_level_metrics WHERE pollster_display_name = 'Datafolha'"
    ).fetchone()
    # |50.0 - 48.43| = 1.57, |35.42 - 43.20| = 7.78, MAE = (1.57 + 7.78) / 2 = 4.675
    assert abs(row[0] - 4.675) < 0.01


def test_analyze_creates_rankings(db_with_assembled):
    analyze_data(db_with_assembled, since=2014)
    rankings = db_with_assembled.execute(
        "SELECT * FROM pollster_rankings ORDER BY mean_mae"
    ).fetchdf()
    assert len(rankings) == 2
    assert "n_races" in rankings.columns
    assert "mae_ci_low" in rankings.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analyze.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/pollster/stages/analyze.py`**

```python
import click
import duckdb
import numpy as np
import pandas as pd


def _compute_poll_level_metrics(con: duckdb.DuckDBPyConnection, since: int) -> None:
    con.execute(f"""
        CREATE OR REPLACE TABLE poll_level_metrics AS
        SELECT *,
            candidate_1_poll_valid_pct - candidate_1_actual_valid_pct AS error_1,
            candidate_2_poll_valid_pct - candidate_2_actual_valid_pct AS error_2,
            ABS(candidate_1_poll_valid_pct - candidate_1_actual_valid_pct) AS abs_error_1,
            ABS(candidate_2_poll_valid_pct - candidate_2_actual_valid_pct) AS abs_error_2,
            (ABS(candidate_1_poll_valid_pct - candidate_1_actual_valid_pct)
             + ABS(candidate_2_poll_valid_pct - candidate_2_actual_valid_pct)) / 2.0 AS mae_top2,
            (candidate_1_poll_valid_pct - candidate_2_poll_valid_pct) AS predicted_margin,
            (candidate_1_actual_valid_pct - candidate_2_actual_valid_pct) AS actual_margin,
            ABS((candidate_1_poll_valid_pct - candidate_2_poll_valid_pct)
                - (candidate_1_actual_valid_pct - candidate_2_actual_valid_pct)) AS margin_error,
            CASE WHEN candidate_1_leaning = 'left'
                 THEN candidate_1_poll_valid_pct - candidate_1_actual_valid_pct
                 WHEN candidate_2_leaning = 'left'
                 THEN candidate_2_poll_valid_pct - candidate_2_actual_valid_pct
                 ELSE NULL END AS left_signed_error,
            CASE WHEN candidate_1_leaning = 'right'
                 THEN candidate_1_poll_valid_pct - candidate_1_actual_valid_pct
                 WHEN candidate_2_leaning = 'right'
                 THEN candidate_2_poll_valid_pct - candidate_2_actual_valid_pct
                 ELSE NULL END AS right_signed_error
        FROM polls_vs_actual
        WHERE year >= {since}
    """)


def _bootstrap_ci(values: np.ndarray, n_boot: int = 10000, ci: float = 0.95) -> tuple[float, float]:
    if len(values) < 2:
        return (float(values[0]) if len(values) == 1 else 0.0, float(values[0]) if len(values) == 1 else 0.0)
    rng = np.random.default_rng(42)
    boot_means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    return (float(np.percentile(boot_means, alpha * 100)),
            float(np.percentile(boot_means, (1 - alpha) * 100)))


def _compute_rankings(con: duckdb.DuckDBPyConnection, table_suffix: str = "",
                      group_cols: list[str] | None = None) -> None:
    base_groups = ["pollster_display_name"]
    if group_cols:
        base_groups = group_cols + base_groups

    group_sql = ", ".join(base_groups)
    table_name = f"pollster_rankings{table_suffix}"

    agg_df = con.execute(f"""
        SELECT {group_sql},
            COUNT(*) AS n_races,
            AVG(mae_top2) AS mean_mae,
            MEDIAN(mae_top2) AS median_mae,
            AVG(margin_error) AS mean_margin_error,
            AVG(left_signed_error) AS mean_left_bias,
            AVG(right_signed_error) AS mean_right_bias
        FROM poll_level_metrics
        GROUP BY {group_sql}
    """).fetchdf()

    maes_by_pollster = con.execute(f"""
        SELECT {group_sql}, mae_top2
        FROM poll_level_metrics
    """).fetchdf()

    ci_rows = []
    for _, row in agg_df.iterrows():
        key_filter = " AND ".join(
            f"pollster_display_name = '{row['pollster_display_name']}'"
            if col == "pollster_display_name"
            else f"{col} = {repr(row[col])}"
            for col in base_groups
        )
        mask = pd.Series([True] * len(maes_by_pollster))
        for col in base_groups:
            mask = mask & (maes_by_pollster[col] == row[col])
        values = maes_by_pollster.loc[mask, "mae_top2"].values
        ci_low, ci_high = _bootstrap_ci(values)
        ci_rows.append({"mae_ci_low": ci_low, "mae_ci_high": ci_high})

    ci_df = pd.DataFrame(ci_rows)
    result = pd.concat([agg_df.reset_index(drop=True), ci_df], axis=1)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM result")


def analyze_data(con: duckdb.DuckDBPyConnection, since: int = 2014) -> None:
    click.echo(f"Computing poll-level metrics (since {since})...")
    _compute_poll_level_metrics(con, since)
    count = con.execute("SELECT COUNT(*) FROM poll_level_metrics").fetchone()[0]
    click.echo(f"  → {count} poll observations.")

    click.echo("Computing overall pollster rankings...")
    _compute_rankings(con)

    click.echo("Computing rankings by year...")
    _compute_rankings(con, "_by_year", ["year"])

    click.echo("Computing rankings by round...")
    _compute_rankings(con, "_by_round", ["round"])

    click.echo("Computing rankings by race type...")
    _compute_rankings(con, "_by_race_type", ["cargo"])

    click.echo("Analysis complete.")
```

- [ ] **Step 4: Wire up CLI — update `src/pollster/cli.py`**

Replace the `analyze` command body:

```python
@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def analyze(since):
    """Compute accuracy metrics and pollster rankings."""
    from pollster.stages.analyze import analyze_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    analyze_data(con, since=since)
    con.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_analyze.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pollster/stages/analyze.py src/pollster/cli.py tests/test_analyze.py
git commit -m "feat: implement analyze stage (metrics, rankings, bootstrap CIs)"
```

---

### Task 8: Report Stage

**Files:**
- Create: `src/pollster/stages/report.py`
- Modify: `src/pollster/cli.py` — wire up report command
- Create: `tests/test_report.py`

- [ ] **Step 1: Write test for report**

```python
# tests/test_report.py
import pandas as pd
import pytest
from pollster.db import get_connection
from pollster.stages.report import generate_report


@pytest.fixture
def db_with_analysis(tmp_data_dir):
    con = get_connection(tmp_data_dir)
    metrics = pd.DataFrame([
        {"year": 2022, "round": 1, "cargo": "Presidente", "sigla_uf": "BR",
         "pollster_display_name": "Datafolha",
         "mae_top2": 4.67, "margin_error": 9.35,
         "predicted_margin": 14.58, "actual_margin": 5.23,
         "left_signed_error": 1.57, "right_signed_error": -7.78,
         "candidate_1_name": "LULA", "candidate_1_poll_valid_pct": 50.0,
         "candidate_1_actual_valid_pct": 48.43,
         "candidate_2_name": "BOLSONARO", "candidate_2_poll_valid_pct": 35.42,
         "candidate_2_actual_valid_pct": 43.20},
    ])
    rankings = pd.DataFrame([
        {"pollster_display_name": "Datafolha", "n_races": 1,
         "mean_mae": 4.67, "median_mae": 4.67,
         "mean_margin_error": 9.35,
         "mean_left_bias": 1.57, "mean_right_bias": -7.78,
         "mae_ci_low": 4.67, "mae_ci_high": 4.67},
    ])
    con.execute("CREATE TABLE poll_level_metrics AS SELECT * FROM metrics")
    con.execute("CREATE TABLE pollster_rankings AS SELECT * FROM rankings")
    con.execute("CREATE TABLE pollster_rankings_by_year AS SELECT 2022 AS year, * FROM rankings")
    con.execute("CREATE TABLE pollster_rankings_by_round AS SELECT 1 AS round, * FROM rankings")
    con.execute("CREATE TABLE pollster_rankings_by_race_type AS SELECT 'Presidente' AS cargo, * FROM rankings")
    yield con, tmp_data_dir
    con.close()


def test_report_generates_html(db_with_analysis):
    con, data_dir = db_with_analysis
    report_dir = data_dir / "reports"
    report_dir.mkdir(exist_ok=True)
    output_path = report_dir / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    assert output_path.exists()
    html = output_path.read_text()
    assert "Datafolha" in html
    assert "<table" in html
    assert "<svg" in html or "<img" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `src/pollster/stages/report.py`**

```python
import io
import base64
import pathlib
import click
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _fig_to_svg(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")


def _render_table(df: pd.DataFrame, float_fmt: str = ".2f") -> str:
    formatters = {}
    for col in df.columns:
        if df[col].dtype in ("float64", "float32"):
            formatters[col] = lambda x, f=float_fmt: f"{{:{f}}}".format(x) if pd.notna(x) else ""
    return df.to_html(index=False, formatters=formatters, classes="ranking-table", border=0)


def _mae_bar_chart(rankings: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(12, max(4, len(rankings) * 0.4)))
    rankings_sorted = rankings.sort_values("mean_mae")
    y_pos = range(len(rankings_sorted))
    bars = ax.barh(
        y_pos, rankings_sorted["mean_mae"],
        xerr=[
            rankings_sorted["mean_mae"] - rankings_sorted["mae_ci_low"],
            rankings_sorted["mae_ci_high"] - rankings_sorted["mean_mae"],
        ],
        color="#4a90d9", ecolor="#999", capsize=3, height=0.6,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rankings_sorted["pollster_display_name"])
    ax.set_xlabel("Mean Absolute Error (pp)")
    ax.set_title("Pollster Accuracy Ranking (with 95% CI)")
    ax.invert_yaxis()
    return _fig_to_svg(fig)


def _margin_scatter(metrics: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 8))
    pollsters = metrics["pollster_display_name"].unique()
    colors = plt.cm.tab20(np.linspace(0, 1, len(pollsters)))
    for pollster, color in zip(pollsters, colors):
        subset = metrics[metrics["pollster_display_name"] == pollster]
        ax.scatter(
            subset["actual_margin"], subset["predicted_margin"],
            label=pollster, color=color, s=40, alpha=0.7,
        )
    lims = [
        min(ax.get_xlim()[0], ax.get_ylim()[0]),
        max(ax.get_xlim()[1], ax.get_ylim()[1]),
    ]
    ax.plot(lims, lims, "k--", alpha=0.3, linewidth=1)
    ax.set_xlabel("Actual Margin (pp)")
    ax.set_ylabel("Predicted Margin (pp)")
    ax.set_title("Predicted vs. Actual Margin")
    if len(pollsters) <= 15:
        ax.legend(fontsize=7, loc="best")
    return _fig_to_svg(fig)


def _heatmap(rankings_by_year: pd.DataFrame) -> str:
    pivot = rankings_by_year.pivot_table(
        index="pollster_display_name", columns="year", values="mean_mae"
    )
    fig, ax = plt.subplots(figsize=(max(6, len(pivot.columns) * 1.5), max(4, len(pivot) * 0.4)))
    im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(int))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8)
    ax.set_title("Mean MAE by Pollster × Election Year")
    fig.colorbar(im, ax=ax, label="MAE (pp)")
    return _fig_to_svg(fig)


CSS = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       max-width: 1100px; margin: 0 auto; padding: 20px; color: #333; }
h1 { border-bottom: 2px solid #333; padding-bottom: 10px; }
h2 { color: #555; margin-top: 40px; }
.ranking-table { border-collapse: collapse; width: 100%; margin: 15px 0; }
.ranking-table th { background: #f5f5f5; padding: 8px 12px; text-align: left;
                    border-bottom: 2px solid #ddd; font-size: 0.9em; }
.ranking-table td { padding: 6px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }
.ranking-table tr:hover { background: #f9f9f9; }
.chart { margin: 20px 0; text-align: center; }
.methodology { background: #f9f9f9; padding: 15px; border-left: 3px solid #ccc;
               margin-top: 40px; font-size: 0.9em; }
.footnote { font-size: 0.8em; color: #777; }
</style>
"""


def generate_report(con: duckdb.DuckDBPyConnection, output_path: pathlib.Path) -> None:
    rankings = con.execute("SELECT * FROM pollster_rankings ORDER BY mean_mae").fetchdf()
    metrics = con.execute("SELECT * FROM poll_level_metrics").fetchdf()

    rankings_by_year = con.execute("SELECT * FROM pollster_rankings_by_year").fetchdf()
    rankings_by_round = con.execute("SELECT * FROM pollster_rankings_by_round").fetchdf()
    rankings_by_race = con.execute("SELECT * FROM pollster_rankings_by_race_type").fetchdf()

    top5 = rankings.head(5)
    n_polls = len(metrics)
    n_pollsters = len(rankings)

    sections = []

    sections.append(f"""
    <h1>Brazilian Election Pollster Accuracy Report</h1>
    <h2>Executive Summary</h2>
    <p>Analysis of <strong>{n_polls}</strong> final pre-election polls from
    <strong>{n_pollsters}</strong> polling institutes. Top 5 most accurate
    (by mean absolute error):</p>
    <ol>{"".join(f"<li><strong>{r['pollster_display_name']}</strong> — MAE {r['mean_mae']:.2f} pp ({int(r['n_races'])} races)</li>" for _, r in top5.iterrows())}</ol>
    <p class="footnote">Data: Poder360 via Base dos Dados. Official results: TSE.</p>
    """)

    display_cols = ["pollster_display_name", "n_races", "mean_mae", "median_mae",
                    "mae_ci_low", "mae_ci_high", "mean_margin_error",
                    "mean_left_bias", "mean_right_bias"]
    display_rankings = rankings[[c for c in display_cols if c in rankings.columns]].copy()
    display_rankings.columns = ["Pollster", "N", "Mean MAE", "Median MAE",
                                "CI Low", "CI High", "Margin Error",
                                "Left Bias", "Right Bias"][:len(display_rankings.columns)]
    sections.append(f"<h2>Overall Pollster Rankings</h2>{_render_table(display_rankings)}")

    sections.append(f'<h2>MAE with 95% Confidence Intervals</h2><div class="chart">{_mae_bar_chart(rankings)}</div>')

    if "predicted_margin" in metrics.columns and "actual_margin" in metrics.columns:
        sections.append(f'<h2>Predicted vs. Actual Margin</h2><div class="chart">{_margin_scatter(metrics)}</div>')

    if not rankings_by_year.empty and "year" in rankings_by_year.columns:
        sections.append(f'<h2>MAE Heatmap by Year</h2><div class="chart">{_heatmap(rankings_by_year)}</div>')

    for year_val in sorted(rankings_by_year["year"].unique()) if "year" in rankings_by_year.columns else []:
        yr_df = rankings_by_year[rankings_by_year["year"] == year_val].sort_values("mean_mae")
        sections.append(f"<h2>Rankings — {int(year_val)}</h2>{_render_table(yr_df.drop(columns=['year'], errors='ignore'))}")

    if not rankings_by_race.empty:
        sections.append(f"<h2>Presidential vs. Gubernatorial</h2>{_render_table(rankings_by_race.sort_values(['cargo', 'mean_mae']))}")

    if not rankings_by_round.empty:
        sections.append(f"<h2>Round 1 vs. Round 2</h2>{_render_table(rankings_by_round.sort_values(['round', 'mean_mae']))}")

    sections.append("""
    <div class="methodology">
    <h2>Methodology</h2>
    <ul>
    <li><strong>Poll selection:</strong> Final poll per pollster per race (latest before election day).</li>
    <li><strong>Rebasing:</strong> Poll percentages rebased to valid votes: <code>poll_valid = raw / sum(all_raw) × 100</code>.</li>
    <li><strong>MAE:</strong> Mean of absolute errors for the top-2 candidates (Mosteller Measure 3).</li>
    <li><strong>Bias:</strong> Signed error averaged by candidate leaning (party-based classification).</li>
    <li><strong>Confidence intervals:</strong> Bootstrap 95% CI (10,000 resamples).</li>
    <li><strong>Pollster lineage:</strong> IBOPE and Ipec treated as one entity.</li>
    <li><strong>Data sources:</strong> Poll data from Poder360 via Base dos Dados. Official results from TSE via Base dos Dados.</li>
    </ul>
    </div>
    """)

    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Pollster Accuracy Report</title>{CSS}</head><body>{''.join(sections)}</body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    click.echo(f"Report written to {output_path}")
```

- [ ] **Step 4: Wire up CLI — update `src/pollster/cli.py`**

Replace the `report` command body:

```python
@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def report(since):
    """Generate HTML accuracy report."""
    from pollster.stages.report import generate_report
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    output_path = data_dir / "reports" / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    con.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pollster/stages/report.py src/pollster/cli.py tests/test_report.py
git commit -m "feat: implement report stage (HTML generation with charts)"
```

---

### Task 9: Query Subcommand and Run Command

**Files:**
- Modify: `src/pollster/cli.py` — implement query and run commands
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write test for query and run**

```python
# tests/test_cli.py
import pandas as pd
from click.testing import CliRunner
from pollster.cli import cli
from pollster.db import get_connection


def test_query_command(tmp_data_dir, monkeypatch):
    monkeypatch.setattr("pollster.config.DATA_DIR_NAME", str(tmp_data_dir))
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE test_t AS SELECT 1 AS x, 'hello' AS y")
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT * FROM test_t"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_query_csv_format(tmp_data_dir, monkeypatch):
    monkeypatch.setattr("pollster.config.DATA_DIR_NAME", str(tmp_data_dir))
    con = get_connection(tmp_data_dir)
    con.execute("CREATE TABLE test_t AS SELECT 1 AS x, 'hello' AS y")
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "--format", "csv", "SELECT * FROM test_t"])
    assert result.exit_code == 0
    assert "x,y" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL (query command just prints "not yet implemented").

- [ ] **Step 3: Implement query and run commands in `src/pollster/cli.py`**

Complete `src/pollster/cli.py`:

```python
import pathlib
import click
from pollster import config
from pollster import db as db_module


@click.group()
def cli():
    """Brazilian election pollster accuracy analysis tool."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def fetch(force):
    """Download poll and results data from Base dos Dados."""
    from pollster.stages.fetch import fetch_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    fetch_data(data_dir, force=force)


@cli.command()
def assemble():
    """Build unified polls-vs-actual dataset."""
    from pollster.stages.assemble import assemble_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    assemble_data(con)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def analyze(since):
    """Compute accuracy metrics and pollster rankings."""
    from pollster.stages.analyze import analyze_data
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    analyze_data(con, since=since)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
def report(since):
    """Generate HTML accuracy report."""
    from pollster.stages.report import generate_report
    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    output_path = data_dir / "reports" / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    con.close()


@cli.command()
@click.option("--since", default=config.DEFAULT_SINCE_YEAR, type=int,
              help="Start year for analysis window.")
@click.option("--force", is_flag=True, help="Re-download even if data exists.")
def run(since, force):
    """Run full pipeline: fetch -> assemble -> analyze -> report."""
    from pollster.stages.fetch import fetch_data
    from pollster.stages.assemble import assemble_data
    from pollster.stages.analyze import analyze_data
    from pollster.stages.report import generate_report

    data_dir = pathlib.Path(config.DATA_DIR_NAME)

    fetch_data(data_dir, force=force)

    con = db_module.get_connection(data_dir)
    assemble_data(con)
    analyze_data(con, since=since)

    output_path = data_dir / "reports" / "pollster_accuracy_report.html"
    generate_report(con, output_path)
    con.close()

    click.echo("Full pipeline complete.")


@cli.command()
@click.argument("sql", required=False)
@click.option("--sql-file", type=click.Path(exists=True), help="Read SQL from a file.")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "csv", "json", "parquet"]))
@click.option("--output", "-o", type=click.Path(), help="Output file path (required for parquet).")
def query(sql, sql_file, fmt, output):
    """Run ad-hoc SQL against the local DuckDB database."""
    if sql_file:
        sql = pathlib.Path(sql_file).read_text()
    if not sql:
        raise click.ClickException("Provide SQL as an argument or via --sql-file.")

    data_dir = pathlib.Path(config.DATA_DIR_NAME)
    con = db_module.get_connection(data_dir)
    try:
        df = db_module.query_to_df(con, sql)
    except Exception as e:
        raise click.ClickException(str(e))
    finally:
        con.close()

    if fmt == "parquet":
        if not output:
            raise click.ClickException("--output is required for parquet format.")
        df.to_parquet(output, index=False)
        click.echo(f"Written {len(df)} rows to {output}")
    elif fmt == "csv":
        click.echo(df.to_csv(index=False))
    elif fmt == "json":
        click.echo(df.to_json(orient="records", indent=2))
    else:
        click.echo(df.to_string(index=False))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pollster/cli.py tests/test_cli.py
git commit -m "feat: implement query subcommand and run pipeline command"
```

---

### Task 10: Parquet Export and Final Integration

**Files:**
- Modify: `src/pollster/stages/analyze.py` — add Parquet export
- Modify: `src/pollster/stages/assemble.py` — add Parquet export
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import pandas as pd
import pytest
from pollster.db import get_connection, register_parquet
from pollster.stages.assemble import assemble_data
from pollster.stages.analyze import analyze_data
from pollster.stages.report import generate_report
from tests.fixtures import make_polls_df, make_results_df, make_candidates_df


@pytest.fixture
def full_pipeline_db(tmp_data_dir):
    parquet_dir = tmp_data_dir / "parquet"

    make_polls_df().to_parquet(parquet_dir / "poder360_pesquisas.parquet")
    make_results_df().to_parquet(parquet_dir / "tse_resultados_candidato.parquet")
    make_candidates_df().to_parquet(parquet_dir / "tse_candidatos.parquet")

    con = get_connection(tmp_data_dir)
    register_parquet(con, "poder360_polls", parquet_dir / "poder360_pesquisas.parquet")
    register_parquet(con, "tse_results", parquet_dir / "tse_resultados_candidato.parquet")
    register_parquet(con, "tse_candidates", parquet_dir / "tse_candidatos.parquet")
    return con, tmp_data_dir


def test_full_pipeline(full_pipeline_db):
    con, data_dir = full_pipeline_db

    assemble_data(con)
    n_assembled = con.execute("SELECT COUNT(*) FROM polls_vs_actual").fetchone()[0]
    assert n_assembled > 0

    analyze_data(con, since=2014)
    n_metrics = con.execute("SELECT COUNT(*) FROM poll_level_metrics").fetchone()[0]
    assert n_metrics == n_assembled

    rankings = con.execute("SELECT * FROM pollster_rankings ORDER BY mean_mae").fetchdf()
    assert len(rankings) > 0
    assert rankings.iloc[0]["mean_mae"] >= 0

    report_path = data_dir / "reports" / "pollster_accuracy_report.html"
    report_path.parent.mkdir(exist_ok=True)
    generate_report(con, report_path)
    assert report_path.exists()
    html = report_path.read_text()
    assert "Pollster Accuracy Report" in html

    con.close()
```

- [ ] **Step 2: Add Parquet export to assemble stage**

Modify `assemble_data` to accept `data_dir` parameter. Add at the end, before the final echo:

```python
    parquet_path = data_dir / "parquet" / "polls_vs_actual.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_parquet(parquet_path, index=False)
```

Update the function signature to `def assemble_data(con, data_dir: pathlib.Path = None)` and add `import pathlib` at the top. The CLI passes `data_dir` from its own resolution.

- [ ] **Step 3: Add Parquet export to analyze stage**

Modify `analyze_data` to accept `data_dir` parameter. Add at the end, before the final echo:

```python
    if data_dir is not None:
        parquet_dir = data_dir / "parquet"
        parquet_dir.mkdir(parents=True, exist_ok=True)
        for table_name in ["poll_level_metrics", "pollster_rankings",
                           "pollster_rankings_by_year", "pollster_rankings_by_round",
                           "pollster_rankings_by_race_type"]:
            df = con.execute(f"SELECT * FROM {table_name}").fetchdf()
            df.to_parquet(parquet_dir / f"{table_name}.parquet", index=False)
```

Update signature to `def analyze_data(con, since=2014, data_dir: pathlib.Path = None)`. CLI passes `data_dir`.

- [ ] **Step 4: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/pollster/stages/assemble.py src/pollster/stages/analyze.py tests/test_integration.py
git commit -m "feat: add Parquet exports and full integration test"
```

---

### Task 11: Data Validation and Sanity Checks

**Files:**
- Create: `tests/test_validation.py`

This task adds tests that verify the pipeline handles edge cases correctly.

- [ ] **Step 1: Write edge case tests**

```python
# tests/test_validation.py
import pandas as pd
import pytest
from pollster.utils.rebase import rebase_to_valid_votes
from pollster.utils.candidates import match_candidate_name
from pollster.utils.normalize import normalize_pollster_name


def test_rebase_handles_zero_sum():
    result = rebase_to_valid_votes({"A": 0.0, "B": 0.0})
    assert result == {"A": 0.0, "B": 0.0}


def test_rebase_single_candidate():
    result = rebase_to_valid_votes({"A": 75.0})
    assert result["A"] == pytest.approx(100.0)


def test_candidate_match_accented_names():
    officials = ["CIRO FERREIRA GOMES"]
    assert match_candidate_name("CIRO FERREIRA GOMES", officials) == "CIRO FERREIRA GOMES"
    assert match_candidate_name("Ciro Ferreira Gomes", officials) == "CIRO FERREIRA GOMES"


def test_candidate_match_with_cedilla():
    officials = ["MARCIO FRANCA"]
    assert match_candidate_name("Márcio França", officials) == "MARCIO FRANCA"


def test_normalize_unknown_pollster_preserves_case():
    assert normalize_pollster_name("Quaest") == "Quaest"


def test_normalize_case_sensitive_merge():
    assert normalize_pollster_name("Ibope") == "IBOPE/Ipec"
    assert normalize_pollster_name("IBOPE") == "IBOPE/Ipec"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_validation.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_validation.py
git commit -m "test: add edge case validation tests"
```

---

### Post-Implementation: First Real Run

After all tasks are complete, run the actual pipeline against real data:

```bash
# Set your GCP project ID (free tier, no cost for our data size)
export BIGQUERY_PROJECT="your-gcp-project-id"

# Run full pipeline
pollster run

# Explore the data
pollster query "SELECT instituto, COUNT(*) FROM poder360_polls GROUP BY 1 ORDER BY 2 DESC LIMIT 20"
pollster query "SELECT * FROM pollster_rankings ORDER BY mean_mae LIMIT 10"

# Open the report
open data/reports/pollster_accuracy_report.html
```

Verify against known facts:
- AtlasIntel should show as more accurate for 2022 (they famously nailed the Bolsonaro vote share)
- Datafolha and Ipec should show a left-leaning bias for 2022 (overestimated Lula's lead)
- Total observation count should be in the hundreds (governor races expand the sample)
