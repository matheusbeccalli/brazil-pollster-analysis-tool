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
