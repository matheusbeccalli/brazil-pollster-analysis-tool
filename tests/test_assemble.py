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


def test_assemble_excludes_condicao_1_rows_from_rebase(tmp_data_dir):
    import pandas as pd
    parquet_dir = tmp_data_dir / "parquet"
    polls_df = make_polls_df()
    extra = polls_df.iloc[[0]].copy()
    extra["nome_candidato"] = "brancos / nulos"
    extra["sigla_partido"] = None
    extra["condicao"] = 1
    extra["percentual"] = 20.0
    polls_df = pd.concat([polls_df, extra], ignore_index=True)
    polls_df.to_parquet(parquet_dir / "poder360_pesquisas.parquet")
    make_results_df().to_parquet(parquet_dir / "tse_resultados_candidato.parquet")
    make_candidates_df().to_parquet(parquet_dir / "tse_candidatos.parquet")

    con = get_connection(tmp_data_dir)
    register_parquet(con, "poder360_polls", parquet_dir / "poder360_pesquisas.parquet")
    register_parquet(con, "tse_results", parquet_dir / "tse_resultados_candidato.parquet")
    register_parquet(con, "tse_candidates", parquet_dir / "tse_candidatos.parquet")
    assemble_data(con)
    row = con.execute(
        "SELECT candidate_1_poll_valid_pct FROM polls_vs_actual "
        "WHERE pollster_display_name = 'Datafolha'"
    ).fetchone()
    con.close()
    # 48 / (48 + 34 + 8 + 6) * 100 = 50.0 — the blank/null row must not be in the denominator
    assert abs(row[0] - 50.0) < 1e-6


def test_assemble_uses_backend_presidential_polls_and_drops_bdd_national_rows(loaded_db):
    import pandas as pd
    from pollster.utils.poder360 import polls_to_frame
    raw = [{"id": 5, "instituto": "Datafolha", "data": "2022-10-01", "contratante": "Folha",
            "entrevistas": 8000, "margem": 2, "registro": "BR-9",
            "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 50},
                           {"nome": "Jair Bolsonaro", "partido": "PL", "percentual": 36},
                           {"nome": "brancos / nulos", "partido": "N/A", "percentual": 14}]]}]
    long = polls_to_frame(raw, turno=1)
    long.insert(0, "ano", 2022)
    con = get_connection(loaded_db)
    con.execute("CREATE TABLE poder360_presidential AS SELECT * FROM long")
    assemble_data(con)
    rows = con.execute(
        "SELECT pollster_display_name, candidate_1_poll_raw_pct, sample_size FROM polls_vs_actual "
        "WHERE year=2022 AND round=1 ORDER BY 1").fetchdf()
    con.close()
    # Datafolha comes from the backend table (50%, n=8000), not from the Base dos Dados fixture (48%);
    # AtlasIntel exists only in Base dos Dados national rows and is therefore dropped.
    assert rows["pollster_display_name"].tolist() == ["Datafolha"]
    assert rows.iloc[0]["candidate_1_poll_raw_pct"] == 50.0
    assert rows.iloc[0]["sample_size"] == 8000


def test_assemble_ignores_final_polls_older_than_max_days(loaded_db, monkeypatch):
    import pandas as pd
    from pollster import config
    monkeypatch.setattr(config, "FINAL_POLL_MAX_DAYS", 30)
    parquet_dir = loaded_db / "parquet"
    polls = pd.read_parquet(parquet_dir / "poder360_pesquisas.parquet")
    # AtlasIntel's only poll becomes a February poll: too old to count as a "final" poll
    polls.loc[polls["instituto"] == "AtlasIntel", "data"] = pd.Timestamp("2022-02-01")
    polls.to_parquet(parquet_dir / "poder360_pesquisas.parquet")
    con = get_connection(loaded_db)
    register_parquet(con, "poder360_polls", parquet_dir / "poder360_pesquisas.parquet")
    assemble_data(con)
    names = con.execute("SELECT pollster_display_name FROM polls_vs_actual").fetchdf()["pollster_display_name"].tolist()
    con.close()
    assert names == ["Datafolha"]


def _reload(loaded_db, polls_df=None, results_df=None, candidates_df=None):
    import pandas as pd
    parquet_dir = loaded_db / "parquet"
    if polls_df is not None:
        polls_df.to_parquet(parquet_dir / "poder360_pesquisas.parquet")
    if results_df is not None:
        results_df.to_parquet(parquet_dir / "tse_resultados_candidato.parquet")
    if candidates_df is not None:
        candidates_df.to_parquet(parquet_dir / "tse_candidatos.parquet")
    con = get_connection(loaded_db)
    register_parquet(con, "poder360_polls", parquet_dir / "poder360_pesquisas.parquet")
    register_parquet(con, "tse_results", parquet_dir / "tse_resultados_candidato.parquet")
    register_parquet(con, "tse_candidates", parquet_dir / "tse_candidatos.parquet")
    return con


def test_assemble_ignores_spontaneous_and_rejection_scenarios(loaded_db):
    import pandas as pd
    polls = pd.read_parquet(loaded_db / "parquet" / "poder360_pesquisas.parquet")
    # AtlasIntel's only scenario becomes a rejection poll; Datafolha gets an extra spontaneous scenario
    polls.loc[polls["instituto"] == "AtlasIntel", "tipo"] = "rejeição"
    extra = polls[polls["instituto"] == "Datafolha"].copy()
    extra["tipo"] = "espontânea"; extra["id_cenario"] = "C9"; extra["percentual"] = extra["percentual"] / 3
    polls = pd.concat([polls, extra], ignore_index=True)
    con = _reload(loaded_db, polls_df=polls)
    assemble_data(con)
    rows = con.execute("SELECT pollster_display_name, candidate_1_poll_raw_pct FROM polls_vs_actual").fetchdf()
    con.close()
    assert rows["pollster_display_name"].tolist() == ["Datafolha"]
    assert rows.iloc[0]["candidate_1_poll_raw_pct"] == 48.0     # the stimulated scenario, not the spontaneous one


def test_assemble_skips_scenarios_whose_total_exceeds_100(loaded_db):
    import pandas as pd
    polls = pd.read_parquet(loaded_db / "parquet" / "poder360_pesquisas.parquet")
    # glue a second copy of Datafolha's rows into the same id_cenario -> total 192%
    dup = polls[polls["instituto"] == "Datafolha"].copy()
    polls = pd.concat([polls, dup], ignore_index=True)
    con = _reload(loaded_db, polls_df=polls)
    assemble_data(con)
    names = con.execute("SELECT pollster_display_name FROM polls_vs_actual").fetchdf()["pollster_display_name"].tolist()
    con.close()
    assert names == ["AtlasIntel"]


def test_assemble_actual_results_merge_by_uf_and_ignore_party_variants(loaded_db):
    import pandas as pd
    results = pd.read_parquet(loaded_db / "parquet" / "tse_resultados_candidato.parquet")
    cands = pd.read_parquet(loaded_db / "parquet" / "tse_candidatos.parquet")
    # 1. Bolsonaro's votes split across two party spellings -> must still be summed as one candidate
    split = results[results["sequencial_candidato"] == "seq2"].copy()
    results.loc[results["sequencial_candidato"] == "seq2", "votos"] //= 2
    split["votos"] = split["votos"] // 2; split["sigla_partido"] = "PL "
    results = pd.concat([results, split], ignore_index=True)
    # 2. a governor candidate in another state shares Lula's sequencial (TSE placeholder) -> must not duplicate Lula
    ghost = cands[cands["sequencial"] == "seq1"].copy()
    ghost["sigla_uf"] = "RR"; ghost["cargo"] = "governador"; ghost["nome_urna"] = "OTTOMAR"; ghost["nome"] = "OTTOMAR DE SOUSA PINTO"
    cands = pd.concat([cands, ghost], ignore_index=True)
    con = _reload(loaded_db, results_df=results, candidates_df=cands)
    assemble_data(con)
    rows = con.execute("SELECT candidate_1_name, candidate_2_name, candidate_1_actual_valid_pct, candidate_2_actual_valid_pct "
                       "FROM polls_vs_actual WHERE pollster_display_name='Datafolha'").fetchdf()
    con.close()
    assert set(rows.iloc[0][["candidate_1_name", "candidate_2_name"]]) == {"LULA", "BOLSONARO"}
    assert rows.iloc[0]["candidate_1_actual_valid_pct"] != rows.iloc[0]["candidate_2_actual_valid_pct"]
