from datetime import date

import numpy as np
import pandas as pd

from pollster.stages import project as P
from pollster.stages.project_report import generate_projection_report


def _round(turno, cands):
    est = pd.DataFrame({"candidate_key": [c.lower() for c, _, _ in cands],
                        "candidate": [c for c, _, _ in cands],
                        "partido": [p for _, p, _ in cands],
                        "n_polls": [2] * len(cands),
                        "weighted_pct": [v for _, _, v in cands],
                        "simple_pct": [v for _, _, v in cands]})
    sims = P.simulate(est, 3.0, 1.5, 500, np.random.default_rng(0))
    summary, p_dec = P.summarize(est, sims)
    polls = pd.DataFrame({
        "poll_id": [1, 1], "pollster_display_name": ["Datafolha", "Datafolha"],
        "data": [pd.Timestamp("2026-09-16")] * 2, "entrevistas": [2000, 2000],
        "nome_candidato": [c for c, _, _ in cands[:2]], "candidate_key": [c.lower() for c, _, _ in cands[:2]],
        "partido": [p for _, p, _ in cands[:2]], "percentual": [40.0, 36.0],
        "is_valid_candidate": [True, True], "weight": [1.0, 1.0], "w_acc": [1.0, 1.0],
        "w_rec": [1.0, 1.0], "w_n": [1.0, 1.0], "eam_hist": [4.0, 4.0], "age_days": [7, 7],
        "turno": [turno, turno], "cenario_idx": [0, 0], "instituto": ["Datafolha"] * 2,
    })
    return P.RoundProjection(turno, polls, summary, sims, p_dec)


def test_generate_projection_report_writes_html(tmp_data_dir):
    r1 = _round(1, [("Lula", "PT", 44.0), ("Flávio Bolsonaro", "PL", 41.0), ("Augusto Cury", "Avante", 15.0)])
    r2 = _round(2, [("Lula", "PT", 51.0), ("Flávio Bolsonaro", "PL", 49.0)])
    res = P.ProjectionResult(date(2026, 9, 23), 14, 3.0, 1.5, 500, {"Datafolha": 4.0}, 4.0, r1, r2)
    all_polls = pd.concat([r1.polls, r2.polls], ignore_index=True)
    out = tmp_data_dir / "reports" / "projecao_2026.html"
    generate_projection_report(res, all_polls, out)
    html = out.read_text()
    assert "Projecao" in html
    assert "Lula" in html and "Flávio Bolsonaro" in html
    assert "2o Turno" in html
    assert html.count("<svg") >= 3
    assert "Datafolha" in html


def test_generate_projection_report_without_runoff(tmp_data_dir):
    r1 = _round(1, [("Lula", "PT", 52.0), ("Flávio Bolsonaro", "PL", 48.0)])
    res = P.ProjectionResult(date(2026, 9, 23), 14, 3.0, 1.5, 500, {}, 1.0, r1, None)
    out = tmp_data_dir / "reports" / "projecao_2026.html"
    generate_projection_report(res, r1.polls, out)
    assert "Lula" in out.read_text()
