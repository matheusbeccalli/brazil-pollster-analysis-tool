import pathlib

import click
import duckdb
import pandas as pd

from pollster import config
from pollster.config import ELECTIONS, PARTY_LEANING
from pollster.utils.normalize import normalize_pollster_name
from pollster.utils.rebase import rebase_to_valid_votes
from pollster.utils.candidates import match_candidate_name
from pollster.utils.poder360 import backend_to_polls_schema


def _normalize_uf(df: pd.DataFrame) -> pd.DataFrame:
    df["sigla_uf"] = df["sigla_uf"].fillna("BR")
    return df


def _build_actual_results(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute("""
        WITH aggregated AS (
            SELECT ano, turno, cargo,
                   COALESCE(sigla_uf, 'BR') AS sigla_uf,
                   sequencial_candidato, sigla_partido,
                   SUM(votos) AS votos
            FROM tse_results
            WHERE votos IS NOT NULL
            GROUP BY ano, turno, cargo, COALESCE(sigla_uf, 'BR'), sequencial_candidato, sigla_partido
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
        candidates[["ano", "sequencial", "nome", "nome_urna", "sigla_partido"]].rename(
            columns={"sigla_partido": "cand_partido", "sequencial": "sequencial_candidato"}
        ),
        on=["ano", "sequencial_candidato"],
        how="left",
    )
    top2["nome_candidato"] = top2["nome_urna"].fillna(top2["nome"])
    return top2


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()[0] > 0


def _load_polls(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Base dos Dados polls, with national presidential rows replaced by the Poder360
    backend table (`poder360_presidential`) when it is available."""
    polls = con.execute("SELECT * FROM poder360_polls").fetchdf()
    if not _table_exists(con, "poder360_presidential"):
        return polls
    backend = con.execute("SELECT * FROM poder360_presidential").fetchdf()
    if backend.empty:
        return polls
    national = (polls["cargo"].str.lower().eq("presidente")
                & (polls["sigla_uf"].isna() | polls["sigla_uf"].eq("BR")))
    polls = polls[~national]
    converted = backend_to_polls_schema(backend)
    converted = converted[[c for c in polls.columns if c in converted.columns]]
    return pd.concat([polls, converted], ignore_index=True)


def _select_final_polls(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    polls = _load_polls(con)
    polls["data"] = pd.to_datetime(polls["data"])
    # condicao = 1 marks non-candidate rows (undecided, blank/null, "others");
    # they must not enter scenario selection nor the valid-vote rebase.
    if "condicao" in polls.columns:
        polls = polls[polls["condicao"].isna() | (polls["condicao"] == 0)]
    _normalize_uf(polls)

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

        earliest = election_day - pd.Timedelta(days=config.FINAL_POLL_MAX_DAYS)
        before = group[(group["data"].dt.date <= election_day) & (group["data"].dt.date >= earliest)]
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
                poll_party=top2_parties.get(official_name),
                official_parties=parties_in_scenario,
            )
            if m is not None:
                matched += 1
        if matched == 2 and len(scenario_df) > best_count:
            best = scenario_df
            best_count = len(scenario_df)
    return best


def assemble_data(con: duckdb.DuckDBPyConnection, data_dir: pathlib.Path = None) -> None:
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

    if data_dir is not None:
        parquet_path = data_dir / "parquet" / "polls_vs_actual.parquet"
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_parquet(parquet_path, index=False)

    click.echo(f"Assembled {len(result_df)} poll observations into polls_vs_actual.")
