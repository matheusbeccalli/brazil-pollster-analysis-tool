"""Stage: project the 2026 presidential election from recent polls.

Weighted average of the most recent poll per pollster (accuracy x recency x
sample size), rebased to valid votes, plus a Monte Carlo simulation whose
top-2 margin error is calibrated on the historical poll-average error.
"""
import pathlib
from dataclasses import dataclass
from datetime import date

import click
import duckdb
import numpy as np
import pandas as pd

from pollster import config
from pollster.utils.poder360 import candidate_key


@dataclass
class RoundProjection:
    turno: int
    polls: pd.DataFrame       # one row per (poll, candidate) used, with weights
    estimate: pd.DataFrame    # candidate, partido, weighted_pct, simple_pct, ci, p_first, p_top2
    sims: np.ndarray          # (n_sims, n_candidates) valid-vote shares, estimate order
    p_decided: float          # P(someone > 50%)


@dataclass
class ProjectionResult:
    as_of: date
    window_days: int
    sigma_margin: float
    sigma_other: float
    n_sims: int
    eam_by_pollster: dict
    median_eam: float
    round1: RoundProjection
    round2: RoundProjection | None


def _history_years_sql() -> str:
    return ", ".join(str(y) for y in config.PROJECTION_HISTORY_YEARS)


def pollster_accuracy(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, float], float]:
    """Mean presidential EAM per pollster over the history years, plus the median."""
    df = con.execute(f"""
        SELECT pollster_display_name, AVG(mae_top2) AS eam
        FROM poll_level_metrics
        WHERE LOWER(cargo) = 'presidente' AND year IN ({_history_years_sql()})
        GROUP BY pollster_display_name
    """).fetchdf()
    eam = {str(k): float(v) for k, v in zip(df["pollster_display_name"], df["eam"])}
    median = float(np.median(list(eam.values()))) if eam else 1.0
    return eam, median


def historical_sigma_margin(con: duckdb.DuckDBPyConnection) -> float:
    """RMSE of the poll-average error on the top-2 margin, floored at the config value."""
    df = con.execute(f"""
        SELECT year, round, AVG(predicted_margin) - AVG(actual_margin) AS err
        FROM poll_level_metrics
        WHERE LOWER(cargo) = 'presidente' AND year IN ({_history_years_sql()})
        GROUP BY year, round
    """).fetchdf()
    rmse = float(np.sqrt(np.mean(np.square(df["err"].values)))) if len(df) else 0.0
    return max(rmse, config.PROJECTION_SIGMA_FLOOR)


def main_scenarios(polls: pd.DataFrame, turno: int) -> pd.DataFrame:
    """Round 1: scenario with most valid candidates. Round 2: the configured pair."""
    df = polls[polls["turno"] == turno]
    if df.empty:
        return df
    if turno == 1:
        sizes = (df[df["is_valid_candidate"]]
                 .groupby(["poll_id", "cenario_idx"]).size().rename("n_valid").reset_index())
        best = (sizes.sort_values(["poll_id", "n_valid", "cenario_idx"],
                                  ascending=[True, False, True])
                .drop_duplicates("poll_id")[["poll_id", "cenario_idx"]])
    else:
        pair = {candidate_key(n) for n in config.PROJECTION_RUNOFF_PAIR}
        has = (df[df["candidate_key"].isin(pair)]
               .groupby(["poll_id", "cenario_idx"])["candidate_key"].nunique()
               .rename("k").reset_index())
        best = has[has["k"] == len(pair)].drop_duplicates("poll_id")[["poll_id", "cenario_idx"]]
    return df.merge(best, on=["poll_id", "cenario_idx"], how="inner")


def select_window(polls: pd.DataFrame, as_of: date, window_days: int) -> pd.DataFrame:
    """Polls within (as_of - window, as_of]; most recent poll per pollster only."""
    if polls.empty:
        return polls
    end = pd.Timestamp(as_of)
    start = end - pd.Timedelta(days=window_days)
    df = polls[(polls["data"] > start) & (polls["data"] <= end)]
    if df.empty:
        return df
    latest = df.groupby("pollster_display_name")["data"].transform("max")
    df = df[df["data"] == latest]
    keep = df.groupby("pollster_display_name")["poll_id"].transform("max")
    return df[df["poll_id"] == keep].copy()


def add_weights(polls: pd.DataFrame, as_of: date, eam_by_pollster: dict,
                median_eam: float) -> pd.DataFrame:
    df = polls.copy()
    eam = df["pollster_display_name"].map(eam_by_pollster).astype(float)
    df["eam_hist"] = eam
    df["w_acc"] = median_eam / eam.fillna(median_eam)
    df["age_days"] = (pd.Timestamp(as_of) - df["data"]).dt.days.clip(lower=0)
    df["w_rec"] = np.exp(-df["age_days"] / config.PROJECTION_RECENCY_TAU_DAYS)
    n = df["entrevistas"].fillna(config.PROJECTION_REFERENCE_SAMPLE).astype(float)
    df["w_n"] = np.sqrt(n / config.PROJECTION_REFERENCE_SAMPLE).clip(upper=2.0)
    df["weight"] = df["w_acc"] * df["w_rec"] * df["w_n"]
    return df


def rebase_polls(df: pd.DataFrame) -> pd.DataFrame:
    """Keep valid candidates and add valid_pct (share of the named-candidate total)."""
    valid = df[df["is_valid_candidate"] & df["percentual"].notna()].copy()
    totals = valid.groupby("poll_id")["percentual"].transform("sum")
    valid["valid_pct"] = valid["percentual"] / totals * 100.0
    return valid


def weighted_estimate(polls: pd.DataFrame) -> pd.DataFrame:
    valid = rebase_polls(polls)
    rows = []
    for key, g in valid.groupby("candidate_key"):
        parties = g["partido"].dropna()
        rows.append({
            "candidate_key": key,
            "candidate": g["nome_candidato"].mode().iloc[0],
            "partido": parties.mode().iloc[0] if len(parties) else "",
            "n_polls": int(g["poll_id"].nunique()),
            "weighted_pct": float(np.average(g["valid_pct"].values, weights=g["weight"].values)),
            "simple_pct": float(g["valid_pct"].mean()),
        })
    est = pd.DataFrame(rows)
    for col in ("weighted_pct", "simple_pct"):
        est[col] = est[col] / est[col].sum() * 100.0
    return est.sort_values("weighted_pct", ascending=False).reset_index(drop=True)


def simulate(estimate: pd.DataFrame, sigma_margin: float, sigma_other: float,
             n_sims: int, rng: np.random.Generator) -> np.ndarray:
    """Top-2 share a margin shock +-delta/2; others get independent noise; renormalize."""
    base = estimate["weighted_pct"].values.astype(float)
    k = len(base)
    sims = np.tile(base, (n_sims, 1))
    delta = rng.normal(0.0, sigma_margin, size=n_sims)
    sims[:, 0] += delta / 2.0
    if k > 1:
        sims[:, 1] -= delta / 2.0
    if k > 2:
        sims[:, 2:] += rng.normal(0.0, sigma_other, size=(n_sims, k - 2))
    sims = np.clip(sims, 0.0, None)
    return sims / sims.sum(axis=1, keepdims=True) * 100.0


def summarize(estimate: pd.DataFrame, sims: np.ndarray) -> tuple[pd.DataFrame, float]:
    order = np.argsort(-sims, axis=1)
    first, top2 = order[:, 0], order[:, :2]
    out = estimate.copy()
    out["ci_low"] = np.percentile(sims, 5, axis=0)
    out["ci_high"] = np.percentile(sims, 95, axis=0)
    out["p_first"] = [float(np.mean(first == i)) for i in range(sims.shape[1])]
    out["p_top2"] = [float(np.mean(np.any(top2 == i, axis=1))) for i in range(sims.shape[1])]
    p_decided = float(np.mean(sims.max(axis=1) > 50.0))
    return out, p_decided


def project_round(polls_2026: pd.DataFrame, turno: int, as_of: date, window_days: int,
                  eam: dict, median_eam: float, sigma_margin: float, sigma_other: float,
                  n_sims: int, rng: np.random.Generator) -> RoundProjection | None:
    df = select_window(main_scenarios(polls_2026, turno), as_of, window_days)
    if df.empty:
        return None
    df = add_weights(df, as_of, eam, median_eam)
    est = weighted_estimate(df)
    sims = simulate(est, sigma_margin, sigma_other, n_sims, rng)
    summary, p_decided = summarize(est, sims)
    return RoundProjection(turno=turno, polls=df, estimate=summary, sims=sims, p_decided=p_decided)


def project_election(con: duckdb.DuckDBPyConnection, as_of: date | None = None,
                     window_days: int = config.PROJECTION_WINDOW_DAYS,
                     n_sims: int = config.PROJECTION_N_SIMS,
                     data_dir: pathlib.Path | None = None) -> ProjectionResult:
    as_of = as_of or date.today()
    polls = con.execute("SELECT * FROM polls_2026").fetchdf()
    polls["data"] = pd.to_datetime(polls["data"])
    eam, median_eam = pollster_accuracy(con)
    sigma_margin = historical_sigma_margin(con)
    sigma_other = config.PROJECTION_SIGMA_OTHER
    rng = np.random.default_rng(config.PROJECTION_SEED)
    click.echo(f"Projecting as of {as_of} (window {window_days}d, "
               f"sigma_margin {sigma_margin:.2f} pp, {n_sims} sims)...")
    r1 = project_round(polls, 1, as_of, window_days, eam, median_eam,
                       sigma_margin, sigma_other, n_sims, rng)
    if r1 is None:
        raise click.ClickException("No first-round polls in the window.")
    r2 = project_round(polls, 2, as_of, window_days, eam, median_eam,
                       sigma_margin, sigma_other, n_sims, rng)
    result = ProjectionResult(as_of, window_days, sigma_margin, sigma_other, n_sims,
                              eam, median_eam, r1, r2)
    _persist(con, result, data_dir)
    return result


def _persist(con: duckdb.DuckDBPyConnection, result: ProjectionResult,
             data_dir: pathlib.Path | None) -> None:
    summaries, used = [], []
    for rp in (result.round1, result.round2):
        if rp is None:
            continue
        s = rp.estimate.copy()
        s.insert(0, "turno", rp.turno)
        s["as_of"] = pd.Timestamp(result.as_of)
        summaries.append(s)
        u = rp.polls.copy()
        u["as_of"] = pd.Timestamp(result.as_of)
        used.append(u)
    summary_df = pd.concat(summaries, ignore_index=True)
    used_df = pd.concat(used, ignore_index=True)
    con.execute("CREATE OR REPLACE TABLE projection_2026_summary AS SELECT * FROM summary_df")
    con.execute("CREATE OR REPLACE TABLE projection_2026_polls AS SELECT * FROM used_df")
    if data_dir is not None:
        pq = data_dir / "parquet"
        pq.mkdir(parents=True, exist_ok=True)
        summary_df.to_parquet(pq / "projection_2026_summary.parquet", index=False)
        used_df.to_parquet(pq / "projection_2026_polls.parquet", index=False)
