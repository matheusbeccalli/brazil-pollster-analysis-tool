import pathlib

import click
import duckdb
import numpy as np
import pandas as pd


def _compute_poll_level_metrics(con: duckdb.DuckDBPyConnection, since: int) -> None:
    con.execute(f"""
        CREATE OR REPLACE TABLE poll_level_metrics AS
        SELECT *,
            candidate_1_poll_valid_pct - candidate_1_actual_valid_pct AS error_1,
            candidate_2_poll_valid_pct - candidate_2_actual_valid_pct AS error_2,
            ABS(candidate_1_poll_valid_pct - candidate_1_actual_valid_pct) AS abs_error_1,
            ABS(candidate_2_poll_valid_pct - candidate_2_actual_valid_pct) AS abs_error_2,
            (ABS(candidate_1_poll_valid_pct - candidate_1_actual_valid_pct)
             + ABS(candidate_2_poll_valid_pct - candidate_2_actual_valid_pct)) / 2.0 AS mae_top2,
            (candidate_1_poll_valid_pct - candidate_2_poll_valid_pct) AS predicted_margin,
            (candidate_1_actual_valid_pct - candidate_2_actual_valid_pct) AS actual_margin,
            ABS((candidate_1_poll_valid_pct - candidate_2_poll_valid_pct)
                - (candidate_1_actual_valid_pct - candidate_2_actual_valid_pct)) AS margin_error,
            CASE WHEN candidate_1_leaning = 'left'
                 THEN candidate_1_poll_valid_pct - candidate_1_actual_valid_pct
                 WHEN candidate_2_leaning = 'left'
                 THEN candidate_2_poll_valid_pct - candidate_2_actual_valid_pct
                 ELSE NULL END AS left_signed_error,
            CASE WHEN candidate_1_leaning = 'right'
                 THEN candidate_1_poll_valid_pct - candidate_1_actual_valid_pct
                 WHEN candidate_2_leaning = 'right'
                 THEN candidate_2_poll_valid_pct - candidate_2_actual_valid_pct
                 ELSE NULL END AS right_signed_error
        FROM polls_vs_actual
        WHERE year >= {since}
    """)


def _bootstrap_ci(values: np.ndarray, n_boot: int = 10000, ci: float = 0.95) -> tuple[float, float]:
    if len(values) < 2:
        return (float(values[0]) if len(values) == 1 else 0.0, float(values[0]) if len(values) == 1 else 0.0)
    rng = np.random.default_rng(42)
    boot_means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    return (float(np.percentile(boot_means, alpha * 100)),
            float(np.percentile(boot_means, (1 - alpha) * 100)))


def _compute_rankings(con: duckdb.DuckDBPyConnection, table_suffix: str = "",
                      group_cols: list[str] | None = None) -> None:
    base_groups = ["pollster_display_name"]
    if group_cols:
        base_groups = group_cols + base_groups

    group_sql = ", ".join(base_groups)
    table_name = f"pollster_rankings{table_suffix}"

    agg_df = con.execute(f"""
        SELECT {group_sql},
            COUNT(*) AS n_races,
            AVG(mae_top2) AS mean_mae,
            MEDIAN(mae_top2) AS median_mae,
            AVG(margin_error) AS mean_margin_error,
            AVG(left_signed_error) AS mean_left_bias,
            AVG(right_signed_error) AS mean_right_bias
        FROM poll_level_metrics
        GROUP BY {group_sql}
    """).fetchdf()

    maes_by_pollster = con.execute(f"""
        SELECT {group_sql}, mae_top2
        FROM poll_level_metrics
    """).fetchdf()

    ci_rows = []
    for _, row in agg_df.iterrows():
        mask = pd.Series([True] * len(maes_by_pollster))
        for col in base_groups:
            mask = mask & (maes_by_pollster[col] == row[col])
        values = maes_by_pollster.loc[mask, "mae_top2"].values
        ci_low, ci_high = _bootstrap_ci(values)
        ci_rows.append({"mae_ci_low": ci_low, "mae_ci_high": ci_high})

    ci_df = pd.DataFrame(ci_rows)
    result = pd.concat([agg_df.reset_index(drop=True), ci_df], axis=1)
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM result")


def analyze_data(con: duckdb.DuckDBPyConnection, since: int = 2014, data_dir: pathlib.Path = None) -> None:
    click.echo(f"Computing poll-level metrics (since {since})...")
    _compute_poll_level_metrics(con, since)
    count = con.execute("SELECT COUNT(*) FROM poll_level_metrics").fetchone()[0]
    click.echo(f"  → {count} poll observations.")

    click.echo("Computing overall pollster rankings...")
    _compute_rankings(con)

    click.echo("Computing rankings by year...")
    _compute_rankings(con, "_by_year", ["year"])

    click.echo("Computing rankings by round...")
    _compute_rankings(con, "_by_round", ["round"])

    click.echo("Computing rankings by race type...")
    _compute_rankings(con, "_by_race_type", ["cargo"])

    if data_dir is not None:
        parquet_dir = data_dir / "parquet"
        parquet_dir.mkdir(parents=True, exist_ok=True)
        for table_name in ["poll_level_metrics", "pollster_rankings",
                           "pollster_rankings_by_year", "pollster_rankings_by_round",
                           "pollster_rankings_by_race_type"]:
            df = con.execute(f"SELECT * FROM {table_name}").fetchdf()
            df.to_parquet(parquet_dir / f"{table_name}.parquet", index=False)

    click.echo("Analysis complete.")
