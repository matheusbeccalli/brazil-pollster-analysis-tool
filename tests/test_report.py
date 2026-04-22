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
