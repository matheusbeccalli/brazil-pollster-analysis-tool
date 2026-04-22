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
