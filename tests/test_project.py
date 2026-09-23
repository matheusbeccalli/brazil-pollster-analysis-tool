from datetime import date

import numpy as np
import pandas as pd
import pytest

from pollster.stages import project as P
from pollster.utils.poder360 import candidate_key


def _polls():
    rows = []

    def poll(pid, inst, disp, d, n, cands, turno=1, cen=0):
        for name, party, pct in cands:
            rows.append(dict(poll_id=pid, instituto=inst, pollster_display_name=disp,
                             data=pd.Timestamp(d), contratante="x", entrevistas=n, margem=2,
                             registro="r", turno=turno, cenario_idx=cen, nome_candidato=name,
                             candidate_key=candidate_key(name), partido=party, percentual=pct,
                             is_valid_candidate=not name.startswith("brancos")))

    poll(1, "Datafolha", "Datafolha", "2026-09-16", 2000,
         [("Lula", "PT", 39), ("Flávio Bolsonaro", "PL", 36), ("Augusto Cury", "Avante", 6), ("brancos", "", 9)])
    poll(2, "Nexus", "Nexus", "2026-09-20", 2000,
         [("Lula", "PT", 40), ("Flávio Bolsonaro", "PL", 37), ("Augusto Cury", "Avante", 6), ("brancos", "", 6)])
    # older poll from same pollster -> dropped by select_window
    poll(3, "Nexus", "Nexus", "2026-09-13", 2000,
         [("Lula", "PT", 42), ("Flávio Bolsonaro", "PL", 37), ("brancos", "", 10)])
    # outside the window
    poll(4, "Old", "Old", "2026-08-01", 2000,
         [("Lula", "PT", 50), ("Flávio Bolsonaro", "PL", 30), ("brancos", "", 20)])
    # runoff poll with two scenarios
    poll(5, "Datafolha", "Datafolha", "2026-09-16", 2000,
         [("Lula", "PT", 46), ("Flávio Bolsonaro", "PL", 44), ("brancos", "", 10)], turno=2, cen=0)
    poll(5, "Datafolha", "Datafolha", "2026-09-16", 2000,
         [("Lula", "PT", 49), ("Romeu Zema", "Novo", 39), ("brancos", "", 12)], turno=2, cen=1)
    return pd.DataFrame(rows)


def test_main_scenarios_round1_keeps_largest_scenario_and_round2_keeps_pair():
    df = _polls()
    r1 = P.main_scenarios(df, 1)
    assert set(r1["poll_id"]) == {1, 2, 3, 4}
    r2 = P.main_scenarios(df, 2)
    assert set(r2["nome_candidato"]) == {"Lula", "Flávio Bolsonaro", "brancos"}
    assert r2["cenario_idx"].unique().tolist() == [0]


def test_select_window_one_poll_per_pollster_most_recent():
    df = P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14)
    assert sorted(df["poll_id"].unique()) == [1, 2]


def test_add_weights_unknown_pollster_gets_median_and_recency_decays():
    df = P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14)
    w = P.add_weights(df, date(2026, 9, 23), {"Datafolha": 4.0}, median_eam=6.0)
    d = w[w.pollster_display_name == "Datafolha"].iloc[0]
    n = w[w.pollster_display_name == "Nexus"].iloc[0]
    assert d["w_acc"] == pytest.approx(6.0 / 4.0)
    assert n["w_acc"] == pytest.approx(1.0)
    assert n["w_rec"] > d["w_rec"]
    assert d["w_n"] == pytest.approx(1.0)
    assert d["weight"] == pytest.approx(d["w_acc"] * d["w_rec"] * d["w_n"])


def test_weighted_estimate_rebases_and_sums_to_100():
    df = P.add_weights(P.select_window(P.main_scenarios(_polls(), 1), date(2026, 9, 23), 14),
                       date(2026, 9, 23), {}, 6.0)
    est = P.weighted_estimate(df)
    assert est["weighted_pct"].sum() == pytest.approx(100.0)
    assert est["simple_pct"].sum() == pytest.approx(100.0)
    assert est.iloc[0]["candidate"] == "Lula"
    assert est.iloc[0]["weighted_pct"] > est.iloc[1]["weighted_pct"] > est.iloc[2]["weighted_pct"]
    # Datafolha valid: Lula 39/81 = 48.15 ; Nexus: 40/83 = 48.19 -> between
    assert 48.0 < est.iloc[0]["weighted_pct"] < 48.3


def test_simulate_and_summarize_probabilities_are_coherent():
    est = pd.DataFrame({"candidate": ["A", "B", "C"], "partido": ["", "", ""],
                        "weighted_pct": [55.0, 40.0, 5.0], "simple_pct": [55.0, 40.0, 5.0]})
    sims = P.simulate(est, sigma_margin=3.0, sigma_other=1.5, n_sims=4000,
                      rng=np.random.default_rng(1))
    assert sims.shape == (4000, 3)
    assert np.allclose(sims.sum(axis=1), 100.0)
    summary, p_decided = P.summarize(est, sims)
    assert summary.iloc[0]["p_first"] > 0.99
    assert summary["p_top2"].sum() == pytest.approx(2.0)
    assert p_decided > 0.9
    assert summary.iloc[0]["ci_low"] < 55.0 < summary.iloc[0]["ci_high"]


def test_simulate_is_reproducible_with_seed():
    est = pd.DataFrame({"candidate": ["A", "B"], "partido": ["", ""],
                        "weighted_pct": [51.0, 49.0], "simple_pct": [51.0, 49.0]})
    a = P.simulate(est, 3.0, 1.5, 100, np.random.default_rng(7))
    b = P.simulate(est, 3.0, 1.5, 100, np.random.default_rng(7))
    assert np.array_equal(a, b)


def test_history_weight_halves_every_two_elections():
    assert P.history_weight(2022) == pytest.approx(1.0)
    assert P.history_weight(2014) == pytest.approx(0.5)
    assert P.history_weight(2006) == pytest.approx(0.25)


def test_historical_sigma_margin_uses_floor(tmp_db):
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 8.0, 5.0, 'left', 'right'), (2022, 1, 'presidente', 'B', 6.0, 5.0, 'left', 'right'),
        (2022, 2, 'presidente', 'A', 4.0, 2.0, 'left', 'right'), (2022, 2, 'presidente', 'B', 2.0, 2.0, 'left', 'right'))
        t(year, round, cargo, pollster_display_name, predicted_margin, actual_margin, candidate_1_leaning, candidate_2_leaning)""")
    # errors: R1 = 7-5 = 2, R2 = 3-2 = 1 -> RMSE 1.58 -> floor 3.0
    assert P.historical_sigma_margin(tmp_db) == pytest.approx(3.0)


def test_historical_sigma_margin_is_per_round_with_overall_fallback(tmp_db):
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 10.0, 5.0, 'left', 'right'), (2018, 1, 'presidente', 'A', 6.0, 2.0, 'right', 'left'),
        (2022, 2, 'presidente', 'A', 5.0, 4.0, 'left', 'right'))
        t(year, round, cargo, pollster_display_name, predicted_margin, actual_margin, candidate_1_leaning, candidate_2_leaning)""")
    assert P.historical_sigma_margin(tmp_db, turno=1) == pytest.approx(np.sqrt((25 + 16) / 2))
    assert P.historical_sigma_margin(tmp_db, turno=2) == pytest.approx(3.0)        # RMSE 1 -> floor
    assert P.historical_sigma_margin(tmp_db) == pytest.approx(np.sqrt((25 + 16 + 1) / 3))


def test_pollster_accuracy_is_recency_weighted_over_presidential_races(tmp_db):
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 2.0), (2022, 2, 'presidente', 'A', 4.0),
        (2014, 1, 'presidente', 'A', 10.0),
        (2022, 1, 'presidente', 'B', 6.0), (2022, 1, 'governador', 'B', 40.0))
        t(year, round, cargo, pollster_display_name, mae_top2)""")
    eam, median = P.pollster_accuracy(tmp_db)
    # A: 2022 mean 3.0 (weight 1) and 2014 10.0 (weight 0.5) -> (3 + 5) / 1.5
    assert eam["A"] == pytest.approx((3.0 + 0.5 * 10.0) / 1.5)
    assert eam["B"] == pytest.approx(6.0)
    assert median == pytest.approx((eam["A"] + 6.0) / 2)


def test_historical_margin_bias_is_left_minus_right_and_recency_weighted(tmp_db):
    # 2022: polls said left +7, actual +5 -> bias +2 (weight 1)
    # 2018: candidate 1 is right; polls said right +11, actual right +17 -> left-right error = -11 - (-17) = +6 (weight 0.707)
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'A', 8.0, 5.0, 'left', 'right'), (2022, 1, 'presidente', 'B', 6.0, 5.0, 'left', 'right'),
        (2018, 1, 'presidente', 'A', 11.0, 17.0, 'right', 'left'),
        (2014, 1, 'presidente', 'A', 3.0, 1.0, 'center', 'right'))
        t(year, round, cargo, pollster_display_name, predicted_margin, actual_margin, candidate_1_leaning, candidate_2_leaning)""")
    w18 = P.history_weight(2018)
    bias, table = P.historical_margin_bias(tmp_db)
    assert bias == pytest.approx((2.0 * 1.0 + 6.0 * w18) / (1.0 + w18))
    assert len(table) == 2 and set(table["year"]) == {2022, 2018}   # center/right race skipped


def test_adjust_estimate_moves_margin_from_left_to_right():
    est = pd.DataFrame({"candidate_key": ["lula", "flavio bolsonaro", "augusto cury"],
                        "candidate": ["Lula", "Flávio Bolsonaro", "Augusto Cury"],
                        "partido": ["PT", "PL", "Avante"], "n_polls": [1, 1, 1],
                        "weighted_pct": [42.0, 38.0, 20.0], "simple_pct": [42.0, 38.0, 20.0]})
    adj = P.adjust_estimate(est, bias=3.0)
    assert adj["weighted_pct"].tolist() == pytest.approx([40.5, 39.5, 20.0])
    assert adj["weighted_pct"].sum() == pytest.approx(100.0)
    assert P.adjust_estimate(est, bias=0.0)["weighted_pct"].tolist() == [42.0, 38.0, 20.0]


def test_project_election_end_to_end(tmp_db, tmp_data_dir):
    polls = _polls()
    tmp_db.execute("CREATE TABLE polls_2026 AS SELECT * FROM polls")
    tmp_db.execute("""CREATE TABLE poll_level_metrics AS SELECT * FROM (VALUES
        (2022, 1, 'presidente', 'Datafolha', 3.0, 8.0, 5.0, 'left', 'right'),
        (2022, 2, 'presidente', 'Datafolha', 2.0, 4.0, 2.0, 'left', 'right'))
        t(year, round, cargo, pollster_display_name, mae_top2, predicted_margin, actual_margin,
          candidate_1_leaning, candidate_2_leaning)""")
    res = P.project_election(tmp_db, as_of=date(2026, 9, 23), n_sims=500, data_dir=tmp_data_dir)
    assert res.round1.estimate.iloc[0]["candidate"] == "Lula"
    assert res.round2 is not None
    assert res.round2.estimate["candidate"].tolist() == ["Lula", "Flávio Bolsonaro"]
    assert 0.0 < res.round2.estimate.iloc[0]["p_first"] < 1.0
    assert res.bias_margin == pytest.approx(2.5)   # (3 + 2) / 2, both 2022
    assert res.round1_adj is not None and res.round2_adj is not None
    assert res.round2_adj.estimate.iloc[0]["p_first"] < res.round2.estimate.iloc[0]["p_first"]
    summary = tmp_db.execute("SELECT variant, COUNT(*) FROM projection_2026_summary GROUP BY 1 ORDER BY 1").fetchall()
    assert summary == [("bias_adjusted", 5), ("raw", 5)]
    assert (tmp_data_dir / "parquet" / "projection_2026_polls.parquet").exists()


def test_main_scenarios_round2_drops_third_candidate_and_prefers_pure_pair():
    rows = []
    for cen, cands in [(0, [("Lula", 44), ("Flávio Bolsonaro", 46), ("Augusto Cury", 45), ("brancos", 8)]),
                       (1, [("Lula", 47), ("Flávio Bolsonaro", 45), ("brancos", 8)])]:
        for name, pct in cands:
            rows.append(dict(poll_id=9, instituto="X", pollster_display_name="X", data=pd.Timestamp("2026-09-20"),
                             contratante="x", entrevistas=2000, margem=2, registro="r", turno=2, cenario_idx=cen,
                             nome_candidato=name, candidate_key=candidate_key(name), partido=None, percentual=pct,
                             is_valid_candidate=not name.startswith("brancos")))
    r2 = P.main_scenarios(pd.DataFrame(rows), 2)
    assert r2["cenario_idx"].unique().tolist() == [1]
    assert set(r2[r2["is_valid_candidate"]]["nome_candidato"]) == {"Lula", "Flávio Bolsonaro"}


def _scenario_rows(pid, cen, cands, turno=1):
    return [dict(poll_id=pid, instituto="X", pollster_display_name="X", data=pd.Timestamp("2026-09-20"),
                 contratante="x", entrevistas=2000, margem=2, registro="r", turno=turno, cenario_idx=cen,
                 nome_candidato=name, candidate_key=candidate_key(name), partido=None, percentual=pct,
                 is_valid_candidate=not name.startswith("brancos")) for name, pct in cands]


def test_main_scenarios_round1_requires_both_leaders_and_a_complete_scenario():
    rows = (_scenario_rows(1, 0, [("Lula", 43), ("Romeu Zema", 3), ("brancos", 2)])            # Flávio missing
            + _scenario_rows(2, 0, [("Lula", 40), ("Flávio Bolsonaro", 28)])                   # sums to 68
            + _scenario_rows(3, 0, [("Lula", 40), ("Flávio Bolsonaro", 36), ("Augusto Cury", 6), ("brancos", 10)])
            + _scenario_rows(3, 1, [("Lula", 41), ("Michelle Bolsonaro", 35), ("Augusto Cury", 6), ("Romeu Zema", 5), ("brancos", 10)]))
    r1 = P.main_scenarios(pd.DataFrame(rows), 1)
    assert r1["poll_id"].unique().tolist() == [3]
    assert r1["cenario_idx"].unique().tolist() == [0]
