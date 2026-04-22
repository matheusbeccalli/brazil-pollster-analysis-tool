import io
import base64
import pathlib

import click
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _fig_to_svg(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")


def _render_table(df: pd.DataFrame, float_fmt: str = ".2f") -> str:
    formatters = {}
    for col in df.columns:
        if df[col].dtype in ("float64", "float32"):
            formatters[col] = lambda x, f=float_fmt: f"{{:{f}}}".format(x) if pd.notna(x) else ""
    return df.to_html(index=False, formatters=formatters, classes="ranking-table", border=0)


def _mae_bar_chart(rankings: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(12, max(4, len(rankings) * 0.4)))
    rankings_sorted = rankings.sort_values("mean_mae")
    y_pos = range(len(rankings_sorted))
    bars = ax.barh(
        y_pos, rankings_sorted["mean_mae"],
        xerr=[
            rankings_sorted["mean_mae"] - rankings_sorted["mae_ci_low"],
            rankings_sorted["mae_ci_high"] - rankings_sorted["mean_mae"],
        ],
        color="#4a90d9", ecolor="#999", capsize=3, height=0.6,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rankings_sorted["pollster_display_name"])
    ax.set_xlabel("Mean Absolute Error (pp)")
    ax.set_title("Pollster Accuracy Ranking (with 95% CI)")
    ax.invert_yaxis()
    return _fig_to_svg(fig)


def _margin_scatter(metrics: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 8))
    pollsters = metrics["pollster_display_name"].unique()
    colors = plt.cm.tab20(np.linspace(0, 1, len(pollsters)))
    for pollster, color in zip(pollsters, colors):
        subset = metrics[metrics["pollster_display_name"] == pollster]
        ax.scatter(
            subset["actual_margin"], subset["predicted_margin"],
            label=pollster, color=color, s=40, alpha=0.7,
        )
    lims = [
        min(ax.get_xlim()[0], ax.get_ylim()[0]),
        max(ax.get_xlim()[1], ax.get_ylim()[1]),
    ]
    ax.plot(lims, lims, "k--", alpha=0.3, linewidth=1)
    ax.set_xlabel("Actual Margin (pp)")
    ax.set_ylabel("Predicted Margin (pp)")
    ax.set_title("Predicted vs. Actual Margin")
    if len(pollsters) <= 15:
        ax.legend(fontsize=7, loc="best")
    return _fig_to_svg(fig)


def _heatmap(rankings_by_year: pd.DataFrame) -> str:
    pivot = rankings_by_year.pivot_table(
        index="pollster_display_name", columns="year", values="mean_mae"
    )
    fig, ax = plt.subplots(figsize=(max(6, len(pivot.columns) * 1.5), max(4, len(pivot) * 0.4)))
    im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(int))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=8)
    ax.set_title("Mean MAE by Pollster × Election Year")
    fig.colorbar(im, ax=ax, label="MAE (pp)")
    return _fig_to_svg(fig)


CSS = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       max-width: 1100px; margin: 0 auto; padding: 20px; color: #333; }
h1 { border-bottom: 2px solid #333; padding-bottom: 10px; }
h2 { color: #555; margin-top: 40px; }
.ranking-table { border-collapse: collapse; width: 100%; margin: 15px 0; }
.ranking-table th { background: #f5f5f5; padding: 8px 12px; text-align: left;
                    border-bottom: 2px solid #ddd; font-size: 0.9em; }
.ranking-table td { padding: 6px 12px; border-bottom: 1px solid #eee; font-size: 0.9em; }
.ranking-table tr:hover { background: #f9f9f9; }
.chart { margin: 20px 0; text-align: center; }
.methodology { background: #f9f9f9; padding: 15px; border-left: 3px solid #ccc;
               margin-top: 40px; font-size: 0.9em; }
.footnote { font-size: 0.8em; color: #777; }
</style>
"""


def generate_report(con: duckdb.DuckDBPyConnection, output_path: pathlib.Path) -> None:
    rankings = con.execute("SELECT * FROM pollster_rankings ORDER BY mean_mae").fetchdf()
    metrics = con.execute("SELECT * FROM poll_level_metrics").fetchdf()

    rankings_by_year = con.execute("SELECT * FROM pollster_rankings_by_year").fetchdf()
    rankings_by_round = con.execute("SELECT * FROM pollster_rankings_by_round").fetchdf()
    rankings_by_race = con.execute("SELECT * FROM pollster_rankings_by_race_type").fetchdf()

    top5 = rankings.head(5)
    n_polls = len(metrics)
    n_pollsters = len(rankings)

    sections = []

    sections.append(f"""
    <h1>Brazilian Election Pollster Accuracy Report</h1>
    <h2>Executive Summary</h2>
    <p>Analysis of <strong>{n_polls}</strong> final pre-election polls from
    <strong>{n_pollsters}</strong> polling institutes. Top 5 most accurate
    (by mean absolute error):</p>
    <ol>{"".join(f"<li><strong>{r['pollster_display_name']}</strong> — MAE {r['mean_mae']:.2f} pp ({int(r['n_races'])} races)</li>" for _, r in top5.iterrows())}</ol>
    <p class="footnote">Data: Poder360 via Base dos Dados. Official results: TSE.</p>
    """)

    display_cols = ["pollster_display_name", "n_races", "mean_mae", "median_mae",
                    "mae_ci_low", "mae_ci_high", "mean_margin_error",
                    "mean_left_bias", "mean_right_bias"]
    display_rankings = rankings[[c for c in display_cols if c in rankings.columns]].copy()
    display_rankings.columns = ["Pollster", "N", "Mean MAE", "Median MAE",
                                "CI Low", "CI High", "Margin Error",
                                "Left Bias", "Right Bias"][:len(display_rankings.columns)]
    sections.append(f"<h2>Overall Pollster Rankings</h2>{_render_table(display_rankings)}")

    sections.append(f'<h2>MAE with 95% Confidence Intervals</h2><div class="chart">{_mae_bar_chart(rankings)}</div>')

    if "predicted_margin" in metrics.columns and "actual_margin" in metrics.columns:
        sections.append(f'<h2>Predicted vs. Actual Margin</h2><div class="chart">{_margin_scatter(metrics)}</div>')

    if not rankings_by_year.empty and "year" in rankings_by_year.columns:
        sections.append(f'<h2>MAE Heatmap by Year</h2><div class="chart">{_heatmap(rankings_by_year)}</div>')

    for year_val in sorted(rankings_by_year["year"].unique()) if "year" in rankings_by_year.columns else []:
        yr_df = rankings_by_year[rankings_by_year["year"] == year_val].sort_values("mean_mae")
        sections.append(f"<h2>Rankings — {int(year_val)}</h2>{_render_table(yr_df.drop(columns=['year'], errors='ignore'))}")

    if not rankings_by_race.empty:
        sections.append(f"<h2>Presidential vs. Gubernatorial</h2>{_render_table(rankings_by_race.sort_values(['cargo', 'mean_mae']))}")

    if not rankings_by_round.empty:
        sections.append(f"<h2>Round 1 vs. Round 2</h2>{_render_table(rankings_by_round.sort_values(['round', 'mean_mae']))}")

    sections.append("""
    <div class="methodology">
    <h2>Methodology</h2>
    <ul>
    <li><strong>Poll selection:</strong> Final poll per pollster per race (latest before election day).</li>
    <li><strong>Rebasing:</strong> Poll percentages rebased to valid votes: <code>poll_valid = raw / sum(all_raw) × 100</code>.</li>
    <li><strong>MAE:</strong> Mean of absolute errors for the top-2 candidates (Mosteller Measure 3).</li>
    <li><strong>Bias:</strong> Signed error averaged by candidate leaning (party-based classification).</li>
    <li><strong>Confidence intervals:</strong> Bootstrap 95% CI (10,000 resamples).</li>
    <li><strong>Pollster lineage:</strong> IBOPE and Ipec treated as one entity.</li>
    <li><strong>Data sources:</strong> Poll data from Poder360 via Base dos Dados. Official results from TSE via Base dos Dados.</li>
    </ul>
    </div>
    """)

    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Pollster Accuracy Report</title>{CSS}</head><body>{''.join(sections)}</body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    click.echo(f"Report written to {output_path}")
