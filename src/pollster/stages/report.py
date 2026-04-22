import io
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


MIN_RACES = 5


def generate_report(con: duckdb.DuckDBPyConnection, output_path: pathlib.Path) -> None:
    all_rankings = con.execute("SELECT * FROM pollster_rankings ORDER BY mean_mae").fetchdf()
    metrics = con.execute("SELECT * FROM poll_level_metrics").fetchdf()

    rankings_by_year = con.execute("SELECT * FROM pollster_rankings_by_year").fetchdf()
    rankings_by_round = con.execute("SELECT * FROM pollster_rankings_by_round").fetchdf()
    rankings_by_race = con.execute("SELECT * FROM pollster_rankings_by_race_type").fetchdf()

    rankings = all_rankings[all_rankings["n_races"] >= MIN_RACES].copy()
    qualified_pollsters = set(rankings["pollster_display_name"])
    metrics_filtered = metrics[metrics["pollster_display_name"].isin(qualified_pollsters)]
    rankings_by_year_f = rankings_by_year[rankings_by_year["pollster_display_name"].isin(qualified_pollsters)]
    rankings_by_round_f = rankings_by_round[rankings_by_round["pollster_display_name"].isin(qualified_pollsters)]
    rankings_by_race_f = rankings_by_race[rankings_by_race["pollster_display_name"].isin(qualified_pollsters)]

    top5 = rankings.head(5)
    n_polls = len(metrics)
    n_pollsters_total = len(all_rankings)
    n_pollsters_qualified = len(rankings)

    sections = []

    sections.append(f"""
    <h1>Brazilian Election Pollster Accuracy Report</h1>
    <h2>Executive Summary</h2>
    <p>Analysis of <strong>{n_polls}</strong> final pre-election polls from
    <strong>{n_pollsters_total}</strong> polling institutes.
    This report focuses on the <strong>{n_pollsters_qualified}</strong> pollsters
    with at least {MIN_RACES} race observations — enough data for meaningful comparison.
    Top 5 most accurate (by mean absolute error):</p>
    <ol>{"".join(f"<li><strong>{r['pollster_display_name']}</strong> — MAE {r['mean_mae']:.2f} pp ({int(r['n_races'])} races)</li>" for _, r in top5.iterrows())}</ol>
    <p class="footnote">Data: Poder360 via Base dos Dados. Official results: TSE.</p>
    """)

    sections.append("""
    <div class="methodology">
    <h2>How to Read the Metrics</h2>
    <p>All error values are in <strong>percentage points (pp)</strong>. For example, if a pollster predicted
    a candidate would get 45% and the actual result was 48%, the error is 3 pp.</p>
    <table class="ranking-table">
    <tr><th>Column</th><th>What it means</th><th>How to interpret</th></tr>
    <tr><td><strong>N</strong></td><td>Number of races observed</td>
        <td>More races = more reliable ranking. A pollster with 50 races is much more trustworthy than one with 5.</td></tr>
    <tr><td><strong>Mean MAE</strong></td><td>Mean Absolute Error averaged over the top-2 candidates</td>
        <td><strong>The primary accuracy metric.</strong> Lower is better. A MAE of 3 pp means the pollster's predictions
        were off by an average of 3 percentage points per candidate. Under 5 pp is good; over 10 pp is poor.</td></tr>
    <tr><td><strong>Median MAE</strong></td><td>The middle value of all MAE observations</td>
        <td>Less sensitive to outliers than the mean. If median is much lower than mean, the pollster had a few very bad misses
        but is usually decent.</td></tr>
    <tr><td><strong>CI Low / CI High</strong></td><td>95% bootstrap confidence interval for the mean MAE</td>
        <td>The true average error likely falls in this range. Wider intervals mean less certainty
        (usually because the pollster has fewer observations).</td></tr>
    <tr><td><strong>Margin Error</strong></td><td>Average error in the predicted gap between the top-2 candidates</td>
        <td>Measures how well the pollster captured the <em>competitive dynamic</em> of the race, not just individual vote shares.
        A pollster can have low MAE but high margin error if errors on both candidates go in the same direction.</td></tr>
    <tr><td><strong>Left Bias</strong></td><td>Average signed error for left-leaning candidates (positive = overestimated)</td>
        <td>Positive values mean the pollster systematically overestimates left-leaning candidates.
        Negative means underestimation. Values near zero indicate no systematic bias.</td></tr>
    <tr><td><strong>Right Bias</strong></td><td>Average signed error for right-leaning candidates (positive = overestimated)</td>
        <td>Same interpretation as Left Bias but for right-leaning candidates.
        A pollster that overestimates the left will typically underestimate the right (and vice versa).</td></tr>
    </table>
    </div>
    """)

    display_cols = ["pollster_display_name", "n_races", "mean_mae", "median_mae",
                    "mae_ci_low", "mae_ci_high", "mean_margin_error",
                    "mean_left_bias", "mean_right_bias"]
    display_rankings = rankings[[c for c in display_cols if c in rankings.columns]].copy()
    display_rankings.columns = ["Pollster", "N", "Mean MAE", "Median MAE",
                                "CI Low", "CI High", "Margin Error",
                                "Left Bias", "Right Bias"][:len(display_rankings.columns)]
    sections.append(f"<h2>Overall Pollster Rankings</h2>"
                    f"<p>Pollsters with {MIN_RACES}+ race observations, sorted by Mean MAE (lower is better).</p>"
                    f"{_render_table(display_rankings)}")

    sections.append(f'<h2>MAE with 95% Confidence Intervals</h2>'
                    f'<p>Horizontal bars show mean MAE; whiskers show 95% confidence interval. '
                    f'Shorter bars and tighter whiskers indicate a more accurate and consistent pollster.</p>'
                    f'<div class="chart">{_mae_bar_chart(rankings)}</div>')

    if "predicted_margin" in metrics_filtered.columns and "actual_margin" in metrics_filtered.columns:
        sections.append(f'<h2>Predicted vs. Actual Margin</h2>'
                        f'<p>Each dot is one poll observation. The dashed diagonal line represents perfect prediction — '
                        f'dots above the line mean the pollster overestimated the leader\'s margin, dots below mean underestimation.</p>'
                        f'<div class="chart">{_margin_scatter(metrics_filtered)}</div>')

    if not rankings_by_year_f.empty and "year" in rankings_by_year_f.columns:
        sections.append(f'<h2>MAE Heatmap by Year</h2>'
                        f'<p>How each pollster performed in each election year. '
                        f'Green cells indicate lower error (more accurate); red cells indicate higher error. '
                        f'Empty cells mean the pollster did not poll that election.</p>'
                        f'<div class="chart">{_heatmap(rankings_by_year_f)}</div>')

    for year_val in sorted(rankings_by_year_f["year"].unique()) if "year" in rankings_by_year_f.columns else []:
        yr_df = rankings_by_year_f[rankings_by_year_f["year"] == year_val].sort_values("mean_mae")
        sections.append(f"<h2>Rankings — {int(year_val)}</h2>{_render_table(yr_df.drop(columns=['year'], errors='ignore'))}")

    if not rankings_by_race_f.empty:
        sections.append(f"<h2>Presidential vs. Gubernatorial</h2>"
                        f"<p>Performance split by race type. Gubernatorial races are often harder to poll due to "
                        f"smaller sample sizes and more volatile local dynamics.</p>"
                        f"{_render_table(rankings_by_race_f.sort_values(['cargo', 'mean_mae']))}")

    if not rankings_by_round_f.empty:
        sections.append(f"<h2>Round 1 vs. Round 2</h2>"
                        f"<p>Performance split by election round. Round 2 polls are typically more accurate because "
                        f"only two candidates remain, reducing the scenario complexity.</p>"
                        f"{_render_table(rankings_by_round_f.sort_values(['round', 'mean_mae']))}")

    sections.append(f"""
    <div class="methodology">
    <h2>Methodology</h2>

    <h3>Data Sources</h3>
    <p>Poll data comes from <strong>Poder360</strong>'s polling database, accessed via
    <a href="https://basedosdados.org/">Base dos Dados</a> (a Brazilian open data initiative that mirrors
    public datasets on Google BigQuery). Official election results come from the <strong>TSE</strong>
    (Tribunal Superior Eleitoral), also accessed via Base dos Dados.</p>

    <h3>Poll Selection</h3>
    <p>For each combination of pollster × race (defined by year, round, office, and state), we select the
    <strong>final poll published before election day</strong> — the one with the latest fieldwork/publication date.
    If a poll contains multiple scenarios (different candidate lineups), we select the scenario that includes
    both top-2 finishers from the official results and has the most candidates (most complete lineup).</p>

    <h3>Rebasing to Valid Votes</h3>
    <p>Raw poll percentages include undecided voters, blank votes, and abstentions baked into the denominator.
    Official results are reported as a share of valid votes only. To make them comparable, we rebase poll
    percentages:</p>
    <p><code>poll_valid_pct = raw_pct / sum(all_candidate_raw_pcts) × 100</code></p>
    <p>This removes undecided/blank/null from the base. Only the rebased percentages for the top-2 finishers
    are used in error calculations.</p>

    <h3>Error Metrics</h3>
    <p>The primary metric is <strong>MAE (Mean Absolute Error)</strong> over the top-2 candidates, also known as
    Mosteller Measure 3. For each poll: <code>MAE = (|error_candidate_1| + |error_candidate_2|) / 2</code>.
    This is then averaged across all races for each pollster.</p>
    <p><strong>Margin error</strong> measures how well the pollster predicted the gap between the two leading
    candidates: <code>|predicted_margin - actual_margin|</code>.</p>
    <p><strong>Partisan bias</strong> is computed as the average signed error for candidates classified as
    left-leaning or right-leaning (based on party affiliation). A positive left bias means the pollster
    systematically overestimated left-leaning candidates.</p>

    <h3>Confidence Intervals</h3>
    <p>The 95% confidence intervals are computed via <strong>bootstrap resampling</strong> (10,000 iterations,
    resampling the pollster's race-level MAE values with replacement). The interval represents the range
    in which the pollster's true average error likely falls.</p>

    <h3>Pollster Identity</h3>
    <p><strong>IBOPE</strong> (which ceased operations in January 2021) and <strong>Ipec</strong> (founded by
    former IBOPE staff) are treated as one entity ("IBOPE/Ipec") to maintain continuity across election cycles.</p>

    <h3>Minimum Observation Threshold</h3>
    <p>Only pollsters with <strong>{MIN_RACES} or more</strong> race observations are included in this report.
    Pollsters with fewer observations are excluded because their rankings would be unreliable — a single
    lucky or unlucky race would dominate their average.</p>

    <h3>Coverage</h3>
    <p>This analysis covers <strong>presidential and gubernatorial</strong> elections, both rounds,
    for the years covered by the analysis window. The default window is 2014–2022 (three election cycles).
    All data from 2000 onward is available for extended analysis.</p>
    </div>
    """)

    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Pollster Accuracy Report</title>{CSS}</head><body>{''.join(sections)}</body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    click.echo(f"Report written to {output_path}")
