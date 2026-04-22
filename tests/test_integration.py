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
