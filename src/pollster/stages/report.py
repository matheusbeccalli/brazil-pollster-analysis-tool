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
    ax.barh(
        y_pos, rankings_sorted["mean_mae"],
        xerr=[
            rankings_sorted["mean_mae"] - rankings_sorted["mae_ci_low"],
            rankings_sorted["mae_ci_high"] - rankings_sorted["mean_mae"],
        ],
        color="#4a90d9", ecolor="#999", capsize=3, height=0.6,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rankings_sorted["pollster_display_name"])
    ax.set_xlabel("Erro Absoluto Medio (pp)")
    ax.set_title("Ranking de Precisao dos Institutos (com IC 95%)")
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
    ax.set_xlabel("Margem Real (pp)")
    ax.set_ylabel("Margem Prevista (pp)")
    ax.set_title("Margem Prevista vs. Margem Real")
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
    ax.set_title("EAM por Instituto x Ano Eleitoral")
    fig.colorbar(im, ax=ax, label="EAM (pp)")
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

    presidential_pollsters = set(
        metrics.loc[metrics["cargo"].str.lower() == "presidente", "pollster_display_name"]
    ) if "cargo" in metrics.columns else set()
    rankings = all_rankings[
        (all_rankings["n_races"] >= MIN_RACES)
        & (all_rankings["pollster_display_name"].isin(presidential_pollsters))
    ].copy() if presidential_pollsters else all_rankings[all_rankings["n_races"] >= MIN_RACES].copy()
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
    <h1>Relatorio de Precisao dos Institutos de Pesquisa Eleitoral</h1>
    <h2>Resumo Executivo</h2>
    <p>Analise de <strong>{n_polls}</strong> pesquisas finais pre-eleitorais de
    <strong>{n_pollsters_total}</strong> institutos de pesquisa.
    Este relatorio foca nos <strong>{n_pollsters_qualified}</strong> institutos
    que pesquisaram ao menos uma eleicao presidencial e possuem {MIN_RACES}+ observacoes totais
    (incluindo governadoriais) — dados suficientes para uma comparacao significativa.
    Os 5 mais precisos (por erro absoluto medio):</p>
    <ol>{"".join(f"<li><strong>{r['pollster_display_name']}</strong> — EAM {r['mean_mae']:.2f} pp ({int(r['n_races'])} disputas)</li>" for _, r in top5.iterrows())}</ol>
    <p class="footnote">Dados: Poder360 via Base dos Dados. Resultados oficiais: TSE.</p>
    """)

    sections.append("""
    <div class="methodology">
    <h2>Como Ler as Metricas</h2>
    <p>Todos os valores de erro sao em <strong>pontos percentuais (pp)</strong>. Por exemplo, se um instituto
    previu que um candidato obteria 45% e o resultado real foi 48%, o erro e de 3 pp.</p>
    <table class="ranking-table">
    <tr><th>Coluna</th><th>O que significa</th><th>Como interpretar</th></tr>
    <tr><td><strong>N</strong></td><td>Numero de disputas observadas</td>
        <td>Mais disputas = ranking mais confiavel. Um instituto com 50 disputas e muito mais confiavel que um com 5.</td></tr>
    <tr><td><strong>EAM</strong></td><td>Erro Absoluto Medio sobre os 2 candidatos mais votados</td>
        <td><strong>A principal metrica de precisao.</strong> Menor e melhor. Um EAM de 3 pp significa que as previsoes
        do instituto erraram em media 3 pontos percentuais por candidato. Abaixo de 5 pp e bom; acima de 10 pp e ruim.</td></tr>
    <tr><td><strong>Mediana EAM</strong></td><td>O valor central de todas as observacoes de EAM</td>
        <td>Menos sensivel a valores extremos que a media. Se a mediana for muito menor que a media, o instituto
        teve alguns erros muito grandes, mas geralmente e razoavel.</td></tr>
    <tr><td><strong>IC Inf / IC Sup</strong></td><td>Intervalo de confianca bootstrap de 95% para o EAM medio</td>
        <td>O erro medio verdadeiro provavelmente esta neste intervalo. Intervalos mais largos indicam menos certeza
        (geralmente porque o instituto tem menos observacoes).</td></tr>
    <tr><td><strong>Erro de Margem</strong></td><td>Erro medio na diferenca prevista entre os 2 candidatos mais votados</td>
        <td>Mede o quao bem o instituto captou a <em>dinamica competitiva</em> da disputa, nao apenas os votos individuais.
        Um instituto pode ter EAM baixo mas erro de margem alto se os erros em ambos os candidatos forem na mesma direcao.</td></tr>
    <tr><td><strong>Vies Esq.</strong></td><td>Erro medio com sinal para candidatos de esquerda (positivo = superestimou)</td>
        <td>Valores positivos significam que o instituto sistematicamente superestima candidatos de esquerda.
        Negativo significa subestimacao. Valores proximos de zero indicam ausencia de vies sistematico.</td></tr>
    <tr><td><strong>Vies Dir.</strong></td><td>Erro medio com sinal para candidatos de direita (positivo = superestimou)</td>
        <td>Mesma interpretacao do Vies de Esquerda, mas para candidatos de direita.
        Um instituto que superestima a esquerda tipicamente subestima a direita (e vice-versa).</td></tr>
    </table>
    </div>
    """)

    display_cols = ["pollster_display_name", "n_races", "mean_mae", "median_mae",
                    "mae_ci_low", "mae_ci_high", "mean_margin_error",
                    "mean_left_bias", "mean_right_bias"]
    display_rankings = rankings[[c for c in display_cols if c in rankings.columns]].copy()
    display_rankings.columns = ["Instituto", "N", "EAM", "Mediana EAM",
                                "IC Inf", "IC Sup", "Erro de Margem",
                                "Vies Esq.", "Vies Dir."][:len(display_rankings.columns)]
    sections.append(f"<h2>Ranking Geral dos Institutos</h2>"
                    f"<p>Institutos com {MIN_RACES}+ observacoes, ordenados por EAM (menor e melhor).</p>"
                    f"{_render_table(display_rankings)}")

    sections.append(f'<h2>EAM com Intervalos de Confianca de 95%</h2>'
                    f'<p>Barras horizontais mostram o EAM medio; bigodes mostram o intervalo de confianca de 95%. '
                    f'Barras menores e bigodes mais estreitos indicam um instituto mais preciso e consistente.</p>'
                    f'<div class="chart">{_mae_bar_chart(rankings)}</div>')

    if "predicted_margin" in metrics_filtered.columns and "actual_margin" in metrics_filtered.columns:
        sections.append(f'<h2>Margem Prevista vs. Margem Real</h2>'
                        f'<p>Cada ponto e uma observacao de pesquisa. A linha diagonal tracejada representa previsao perfeita — '
                        f'pontos acima da linha significam que o instituto superestimou a margem do lider, pontos abaixo significam subestimacao.</p>'
                        f'<div class="chart">{_margin_scatter(metrics_filtered)}</div>')

    if not rankings_by_year_f.empty and "year" in rankings_by_year_f.columns:
        sections.append(f'<h2>Mapa de Calor do EAM por Ano</h2>'
                        f'<p>Desempenho de cada instituto em cada ano eleitoral. '
                        f'Celulas verdes indicam menor erro (mais preciso); celulas vermelhas indicam maior erro. '
                        f'Celulas vazias significam que o instituto nao pesquisou aquela eleicao.</p>'
                        f'<div class="chart">{_heatmap(rankings_by_year_f)}</div>')

    for year_val in sorted(rankings_by_year_f["year"].unique()) if "year" in rankings_by_year_f.columns else []:
        yr_df = rankings_by_year_f[rankings_by_year_f["year"] == year_val].sort_values("mean_mae")
        sections.append(f"<h2>Ranking — {int(year_val)}</h2>{_render_table(yr_df.drop(columns=['year'], errors='ignore'))}")

    if not rankings_by_race_f.empty:
        sections.append(f"<h2>Presidente vs. Governador</h2>"
                        f"<p>Desempenho por tipo de disputa. Eleicoes para governador sao frequentemente mais dificeis de pesquisar "
                        f"devido a amostras menores e dinamicas locais mais volateis.</p>"
                        f"{_render_table(rankings_by_race_f.sort_values(['cargo', 'mean_mae']))}")

    if not rankings_by_round_f.empty:
        sections.append(f"<h2>1o Turno vs. 2o Turno</h2>"
                        f"<p>Desempenho por turno eleitoral. Pesquisas de 2o turno sao tipicamente mais precisas porque "
                        f"restam apenas dois candidatos, reduzindo a complexidade dos cenarios.</p>"
                        f"{_render_table(rankings_by_round_f.sort_values(['round', 'mean_mae']))}")

    sections.append(f"""
    <div class="methodology">
    <h2>Metodologia</h2>

    <h3>Fontes de Dados</h3>
    <p>Os dados de pesquisas vem do banco de dados do <strong>Poder360</strong>, acessado via
    <a href="https://basedosdados.org/">Base dos Dados</a> (uma iniciativa brasileira de dados abertos que
    espelha conjuntos de dados publicos no Google BigQuery). Os resultados oficiais das eleicoes vem do
    <strong>TSE</strong> (Tribunal Superior Eleitoral), tambem acessados via Base dos Dados.</p>

    <h3>Selecao de Pesquisas</h3>
    <p>Para cada combinacao de instituto x disputa (definida por ano, turno, cargo e estado), selecionamos a
    <strong>ultima pesquisa publicada antes do dia da eleicao</strong> — aquela com a data de campo/publicacao
    mais recente. Se uma pesquisa contiver multiplos cenarios (diferentes composicoes de candidatos),
    selecionamos o cenario que inclui os dois candidatos mais votados no resultado oficial e que possui
    o maior numero de candidatos (composicao mais completa).</p>

    <h3>Rebase para Votos Validos</h3>
    <p>Os percentuais brutos das pesquisas incluem indecisos, brancos e nulos no denominador.
    Os resultados oficiais sao reportados como proporcao dos votos validos apenas. Para torna-los
    comparaveis, rebaseamos os percentuais das pesquisas:</p>
    <p><code>pct_valido = pct_bruto / soma(pcts_brutos_todos_candidatos) x 100</code></p>
    <p>Isso remove indecisos/brancos/nulos da base. Apenas os percentuais rebaseados dos 2 candidatos
    mais votados sao usados nos calculos de erro.</p>

    <h3>Metricas de Erro</h3>
    <p>A metrica principal e o <strong>EAM (Erro Absoluto Medio)</strong> sobre os 2 candidatos mais votados,
    tambem conhecido como Medida de Mosteller 3. Para cada pesquisa:
    <code>EAM = (|erro_candidato_1| + |erro_candidato_2|) / 2</code>.
    O EAM e entao calculado como media de todas as disputas para cada instituto.</p>
    <p><strong>Erro de margem</strong> mede o quao bem o instituto previu a diferenca entre os dois
    candidatos lideres: <code>|margem_prevista - margem_real|</code>.</p>
    <p><strong>Vies partidario</strong> e calculado como o erro medio com sinal para candidatos classificados
    como de esquerda ou de direita (baseado na filiacao partidaria). Um vies de esquerda positivo significa que
    o instituto sistematicamente superestimou candidatos de esquerda.</p>

    <h3>Intervalos de Confianca</h3>
    <p>Os intervalos de confianca de 95% sao calculados via <strong>reamostragem bootstrap</strong>
    (10.000 iteracoes, reamostrando os valores de EAM por disputa do instituto com reposicao).
    O intervalo representa a faixa em que o erro medio verdadeiro do instituto provavelmente se encontra.</p>

    <h3>Identidade dos Institutos</h3>
    <p>O <strong>IBOPE</strong> (que encerrou operacoes em janeiro de 2021) e o <strong>Ipec</strong>
    (fundado por ex-funcionarios do IBOPE) sao tratados como uma unica entidade ("IBOPE/Ipec") para
    manter a continuidade entre ciclos eleitorais.</p>

    <h3>Limiar Minimo de Observacoes</h3>
    <p>Apenas institutos com <strong>{MIN_RACES} ou mais</strong> observacoes de disputas sao incluidos
    neste relatorio. Institutos com menos observacoes sao excluidos porque seus rankings seriam
    pouco confiaveis — uma unica disputa com sorte ou azar dominaria sua media.</p>

    <h3>Cobertura</h3>
    <p>Esta analise abrange eleicoes <strong>presidenciais e para governador</strong>, ambos os turnos,
    para os anos cobertos pela janela de analise. A janela padrao e 2014–2022 (tres ciclos eleitorais).
    Todos os dados a partir de 2000 estao disponiveis para analise estendida.</p>
    </div>
    """)

    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Relatorio de Precisao dos Institutos de Pesquisa</title>{CSS}</head><body>{''.join(sections)}</body></html>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    click.echo(f"Report written to {output_path}")
