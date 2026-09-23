"""Stage: download national presidential polls (2002-2026) from the Poder360 aggregator backend."""
import pathlib

import click
import pandas as pd
import requests

from pollster.config import (PODER360_AGREGADOR_URL, PODER360_CARGO_PRESIDENTE,
                             PODER360_UF_BRASIL, PODER360_YEARS, PROJECTION_YEAR)
from pollster.db import get_connection, register_parquet
from pollster.utils.poder360 import polls_to_frame

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pollster-tool",
    "Origin": "https://drive.poder360.com.br",
    "Referer": "https://drive.poder360.com.br/",
    "Content-Type": "application/json",
}


def download_polls(turno: int, year: int = PROJECTION_YEAR) -> list[dict]:
    payload = {"cargosId": PODER360_CARGO_PRESIDENTE, "ano": year, "turno": str(turno),
               "unidadesFederativasId": PODER360_UF_BRASIL, "cidade": "", "pagina": 1}
    resp = requests.post(PODER360_AGREGADOR_URL, json=payload, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise click.ClickException(
            f"Unexpected response from Poder360 for {year} turno {turno}: {str(data)[:200]}")
    return data


def _register_2026(con, parquet_dir: pathlib.Path) -> None:
    con.execute(f"CREATE OR REPLACE TABLE polls_2026 AS "
                f"SELECT * FROM poder360_presidential WHERE ano = {PROJECTION_YEAR}")
    con.execute("SELECT * FROM polls_2026").fetchdf().to_parquet(
        parquet_dir / "polls_2026.parquet", index=False)


def fetch_poder360(data_dir: pathlib.Path, years: list[int] | None = None,
                   force: bool = False) -> None:
    years = sorted(years or PODER360_YEARS)
    parquet_dir = data_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    path = parquet_dir / "poder360_presidential.parquet"
    con = get_connection(data_dir)

    existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if not existing.empty and not force:
        missing = [y for y in years if y not in set(existing["ano"])]
        if not missing:
            click.echo(f"Poder360 presidential polls already exist at {path}. Use --force to re-download.")
            register_parquet(con, "poder360_presidential", path)
            _register_2026(con, parquet_dir)
            con.close()
            return
        years = missing

    frames = []
    for year in years:
        for turno in (1, 2):
            click.echo(f"Downloading presidential polls {year} turno {turno} from Poder360...")
            df = polls_to_frame(download_polls(turno, year), turno=turno)
            df.insert(0, "ano", year)
            click.echo(f"  → {df['poll_id'].nunique()} polls, {len(df)} rows.")
            frames.append(df)
    new_df = pd.concat(frames, ignore_index=True)
    if not existing.empty and not force:
        keep = existing[~existing["ano"].isin(years)]
        new_df = pd.concat([keep, new_df], ignore_index=True)
    elif not existing.empty and force:
        # force re-downloads the requested years only; other years are kept
        keep = existing[~existing["ano"].isin(years)]
        new_df = pd.concat([keep, new_df], ignore_index=True)
    new_df = new_df.sort_values(["ano", "turno", "data", "poll_id"]).reset_index(drop=True)
    new_df.to_parquet(path, index=False)
    register_parquet(con, "poder360_presidential", path)
    _register_2026(con, parquet_dir)
    con.close()
    click.echo(f"Fetch Poder360 complete: {new_df['ano'].nunique()} election years, "
               f"{new_df['poll_id'].nunique()} polls.")
