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
SELECT ano, tipo_eleicao, sigla_uf, cargo, numero,
       sequencial, nome, nome_urna, sigla_partido
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
