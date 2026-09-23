"""Stage: download 2026 presidential polls from the Poder360 aggregator backend."""
import pathlib

import click
import pandas as pd
import requests

from pollster.config import (PODER360_AGREGADOR_URL, PODER360_CARGO_PRESIDENTE,
                             PODER360_UF_BRASIL, PROJECTION_YEAR)
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
    resp = requests.post(PODER360_AGREGADOR_URL, json=payload, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise click.ClickException(
            f"Unexpected response from Poder360 for turno {turno}: {str(data)[:200]}")
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
        click.echo(f"Downloading 2026 presidential polls (turno {turno}) from Poder360...")
        raw = download_polls(turno)
        df = polls_to_frame(raw, turno=turno)
        click.echo(f"  → {df['poll_id'].nunique()} polls, {len(df)} rows.")
        frames.append(df)

    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_parquet(path, index=False)
    register_parquet(con, "polls_2026", path)
    con.close()
    click.echo("Fetch 2026 complete.")
