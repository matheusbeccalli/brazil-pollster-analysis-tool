"""Stage: HTML report for the 2026 projection (Portuguese)."""
import pathlib
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pollster import config
from pollster.stages.project import (ProjectionResult, RoundProjection, add_weights,
                                     main_scenarios, rebase_polls, select_window,
                                     weighted_estimate)
from pollster.stages.report import CSS, _fig_to_svg, _render_table
from pollster.utils.poder360 import candidate_key

# Fixed categorical palette (validated, see dataviz skill); color follows the candidate.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CANDIDATE_COLORS = {
    "lula": "#e34948",
    "flavio bolsonaro": "#2a78d6",
    "augusto cury": "#eb6834",
    "ronaldo caiado": "#1baf7a",
    "renan santos": "#4a3aa7",
    "romeu zema": "#eda100",
    "samara martins": "#e87ba4",
}
NEUTRAL = "#8a8a86"
TIMELINE_START = pd.Timestamp("2026-07-01")


def _color(key: str, fallback_idx: int = 0) -> str:
    return CANDIDATE_COLORS.get(key, PALETTE[fallback_idx % len(PALETTE)])


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(colors="#52514e", labelsize=9)
    ax.grid(axis="x", color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)


def _fmt_pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def _fmt_prob(p: float) -> str:
    return f"{100 * p:.0f}%"


def _bar_chart(rp: RoundProjection, title: str) -> str:
    est = rp.estimate
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(est) + 1.5))
    y = np.arange(len(est))
    colors = [_color(k, i) for i, k in enumerate(est["candidate_key"])]
    ax.barh(y, est["weighted_pct"], color=colors, height=0.55)
    ax.errorbar(est["weighted_pct"], y,
                xerr=[est["weighted_pct"] - est["ci_low"], est["ci_high"] - est["weighted_pct"]],
                fmt="none", ecolor="#0b0b0b", elinewidth=1.2, capsize=4)
    for yi, (v, hi) in enumerate(zip(est["weighted_pct"], est["ci_high"])):
        ax.text(hi + 0.6, yi, _fmt_pct(v), va="center", fontsize=9, color="#0b0b0b")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{c} ({p})" if p else c for c, p in zip(est["candidate"], est["partido"])])
    ax.invert_yaxis()
    ax.set_xlim(0, max(55, float(est["ci_high"].max()) + 8))
    ax.axvline(50, color="#52514e", linestyle="--", linewidth=1)
    ax.set_xlabel("% dos votos validos (barra = media ponderada; bigode = intervalo de 90%)")
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
    _style(ax)
    return _fig_to_svg(fig)


def _margin_hist(rp: RoundProjection, title: str) -> str:
    a, b = rp.estimate.iloc[0], rp.estimate.iloc[1]
    margin = rp.sims[:, 0] - rp.sims[:, 1]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    bins = np.arange(np.floor(margin.min()) - 1, np.ceil(margin.max()) + 2, 1.0)
    ax.hist(margin[margin >= 0], bins=bins, color=_color(a["candidate_key"], 0), alpha=0.85,
            label=f"{a['candidate']} na frente ({_fmt_prob(float(np.mean(margin > 0)))})")
    ax.hist(margin[margin < 0], bins=bins, color=_color(b["candidate_key"], 1), alpha=0.85,
            label=f"{b['candidate']} na frente ({_fmt_prob(float(np.mean(margin < 0)))})")
    ax.axvline(0, color="#0b0b0b", linewidth=1)
    ax.set_xlabel(f"Margem simulada {a['candidate']} - {b['candidate']} (pontos percentuais dos validos)")
    ax.set_ylabel("simulacoes")
    ax.legend(frameon=False, fontsize=9)
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
    _style(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color="#eeeeee", linewidth=0.8)
    return _fig_to_svg(fig)


def _timeline(all_polls: pd.DataFrame, result: ProjectionResult, turno: int,
              keys: list[str], title: str) -> str:
    df = all_polls[all_polls["turno"] == turno].copy()
    df["data"] = pd.to_datetime(df["data"])
    df = main_scenarios(df, turno)
    df = df[df["data"] >= TIMELINE_START]
    if df.empty:
        return ""
    valid = rebase_polls(df)
    valid = valid[valid["candidate_key"].isin(keys)]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    dates = sorted(df["data"].unique())
    trend = {k: [] for k in keys}
    for d in dates:
        win = select_window(df, pd.Timestamp(d).date(), result.window_days)
        if win.empty:
            for k in keys:
                trend[k].append(np.nan)
            continue
        est = weighted_estimate(add_weights(win, pd.Timestamp(d).date(),
                                            result.eam_by_pollster, result.median_eam))
        lookup = dict(zip(est["candidate_key"], est["weighted_pct"]))
        for k in keys:
            trend[k].append(lookup.get(k, np.nan))
    names = valid.groupby("candidate_key")["nome_candidato"].agg(lambda s: s.mode().iloc[0])
    lasts = {}
    for i, k in enumerate(keys):
        sub = valid[valid["candidate_key"] == k]
        ax.scatter(sub["data"], sub["valid_pct"], s=22, color=_color(k, i), alpha=0.45,
                   edgecolors="white", linewidths=0.8)
        ax.plot(dates, trend[k], color=_color(k, i), linewidth=2.2, label=names.get(k, k))
        last = next((v for v in reversed(trend[k]) if not np.isnan(v)), None)
        if last is not None:
            lasts[k] = last
    # end labels, pushed apart so they never overlap
    y_span = ax.get_ylim()[1] - ax.get_ylim()[0]
    min_gap = 0.06 * y_span
    placed = []
    for k, v in sorted(lasts.items(), key=lambda kv: kv[1]):
        y = v if not placed else max(v, placed[-1] + min_gap)
        placed.append(y)
        ax.text(dates[-1] + pd.Timedelta(days=1), y, _fmt_pct(v), va="center",
                fontsize=9, color="#0b0b0b")
    ax.axhline(50, color="#52514e", linestyle="--", linewidth=1)
    ax.set_ylabel("% dos votos validos")
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _style(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color="#eeeeee", linewidth=0.8)
    fig.autofmt_xdate()
    return _fig_to_svg(fig)


def _polls_table(rp: RoundProjection) -> str:
    valid = rebase_polls(rp.polls)
    top = rp.estimate["candidate_key"].tolist()[:4]
    names = dict(zip(rp.estimate["candidate_key"], rp.estimate["candidate"]))
    meta = (rp.polls.groupby("poll_id")
            .agg(Instituto=("pollster_display_name", "first"), Data=("data", "first"),
                 Amostra=("entrevistas", "first"), EAM_2022=("eam_hist", "first"),
                 w_acc=("w_acc", "first"), w_rec=("w_rec", "first"), w_n=("w_n", "first"),
                 Peso=("weight", "first")))
    pivot = valid.pivot_table(index="poll_id", columns="candidate_key", values="valid_pct")
    for k in top:
        meta[names[k]] = pivot[k].round(1) if k in pivot.columns else np.nan
    meta["Data"] = meta["Data"].dt.strftime("%d/%m")
    meta = meta.sort_values("Peso", ascending=False).reset_index(drop=True)
    meta = meta.rename(columns={"EAM_2022": "EAM 2022", "w_acc": "Peso precisao",
                                "w_rec": "Peso recencia", "w_n": "Peso amostra"})
    meta["Amostra"] = meta["Amostra"].map(lambda v: f"{int(v):,}".replace(",", ".") if pd.notna(v) else "")
    meta["EAM 2022"] = meta["EAM 2022"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "")
    return _render_table(meta)


def _summary_table(rp: RoundProjection, adj: RoundProjection | None = None) -> str:
    frames = []
    for label, r in (("sem correcao", rp), ("com correcao de vies", adj)):
        if r is None:
            continue
        est = r.estimate
        frames.append(pd.DataFrame({
            "Variante": label, "Candidato": est["candidate"], "Partido": est["partido"],
            "Media ponderada": est["weighted_pct"], "Media simples": est["simple_pct"],
            "IC 90% inf": est["ci_low"], "IC 90% sup": est["ci_high"],
            "P(1o lugar)": est["p_first"].map(_fmt_prob), "P(top 2)": est["p_top2"].map(_fmt_prob),
            "Pesquisas": est["n_polls"],
        }))
    out = pd.concat(frames, ignore_index=True)
    if adj is None:
        out = out.drop(columns=["Variante"])
    return _render_table(out, float_fmt=".1f")


def _bias_table(result: ProjectionResult) -> str:
    t = result.bias_table
    if t is None or t.empty:
        return "<p>Sem disputas historicas com um candidato de esquerda e um de direita.</p>"
    out = pd.DataFrame({
        "Eleicao": t["year"].astype(int), "Turno": t["round"].astype(int),
        "Institutos": t["n_polls"].astype(int),
        "Margem prevista (media)": t["predicted_margin"], "Margem real": t["actual_margin"],
        "Erro esq. - dir. (pp)": t["error_left_minus_right"], "Peso": t["weight"],
    })
    return _render_table(out, float_fmt=".1f")


def generate_projection_report(result: ProjectionResult, all_polls: pd.DataFrame,
                               output_path: pathlib.Path) -> None:
    r1, r2 = result.round1, result.round2
    lead = r1.estimate.iloc[0]
    second = r1.estimate.iloc[1]
    election_r1 = config.ELECTIONS[config.PROJECTION_YEAR]["round_1"]
    days_left = (election_r1 - result.as_of).days
    n_r1 = r1.polls["poll_id"].nunique()
    pair_keys = [candidate_key(n) for n in config.PROJECTION_RUNOFF_PAIR]
    pair_names = list(config.PROJECTION_RUNOFF_PAIR)
    p_pair = float(np.mean(np.all(np.isin(np.argsort(-r1.sims, axis=1)[:, :2],
                                          [i for i, k in enumerate(r1.estimate["candidate_key"])
                                           if k in pair_keys]), axis=1)))

    sections = [f"""
    <h1>Projecao da Eleicao Presidencial de 2026</h1>
    <p class="footnote">Gerado em {result.as_of.strftime('%d/%m/%Y')}, {days_left} dias antes do 1o turno
    ({election_r1.strftime('%d/%m/%Y')}). Uso pessoal; nao e previsao profissional.</p>
    <h2>Resumo</h2>
    <ul>
      <li><strong>1o turno:</strong> {lead['candidate']} {_fmt_pct(lead['weighted_pct'])} x
          {second['candidate']} {_fmt_pct(second['weighted_pct'])} dos votos validos
          (media ponderada de {n_r1} pesquisas dos ultimos {result.window_days} dias).</li>
      <li><strong>Chance de {lead['candidate']} terminar em 1o no 1o turno:</strong> {_fmt_prob(lead['p_first'])}.</li>
      <li><strong>Chance de a eleicao ser decidida no 1o turno</strong> (alguem acima de 50% dos validos): {_fmt_prob(r1.p_decided)}.</li>
      <li><strong>Chance de o 2o turno ser {pair_names[0]} x {pair_names[1]}:</strong> {_fmt_prob(p_pair)}.</li>
    """]
    if r2 is not None:
        a, b = r2.estimate.iloc[0], r2.estimate.iloc[1]
        sections.append(f"""
      <li><strong>2o turno ({a['candidate']} x {b['candidate']}):</strong> {_fmt_pct(a['weighted_pct'])} x
          {_fmt_pct(b['weighted_pct'])} dos validos; chance de vitoria de {a['candidate']}:
          <strong>{_fmt_prob(a['p_first'])}</strong> ({r2.polls['poll_id'].nunique()} pesquisas).</li>
        """)
    sections.append("</ul>")
    if result.round1_adj is not None:
        la, sa = result.round1_adj.estimate.iloc[0], result.round1_adj.estimate.iloc[1]
        bias_txt = f"{result.bias_margin:+.1f} pp".replace(".", ",")
        sections.append(f"""
    <p><strong>Variante com correcao de vies historico.</strong> Desde 2002, a media dos institutos errou a margem
    esquerda - direita em <strong>{bias_txt}</strong> (media ponderada por recencia; positivo = superestimou a esquerda).
    Aplicando esse deslocamento:</p>
    <ul>
      <li><strong>1o turno:</strong> {la['candidate']} {_fmt_pct(la['weighted_pct'])} x {sa['candidate']}
          {_fmt_pct(sa['weighted_pct'])}; chance de {la['candidate']} terminar em 1o: {_fmt_prob(la['p_first'])}.</li>
        """)
        if result.round2_adj is not None:
            a2, b2 = result.round2_adj.estimate.iloc[0], result.round2_adj.estimate.iloc[1]
            sections.append(f"""
      <li><strong>2o turno:</strong> {a2['candidate']} {_fmt_pct(a2['weighted_pct'])} x {b2['candidate']}
          {_fmt_pct(b2['weighted_pct'])}; chance de vitoria de {a2['candidate']}: <strong>{_fmt_prob(a2['p_first'])}</strong>.</li>
            """)
        sections.append("</ul>")

    sections.append(f"""
    <h2>1o Turno</h2>
    {_summary_table(r1, result.round1_adj)}
    <div class="chart">{_bar_chart(r1, '1o turno: votos validos projetados (sem correcao)')}</div>
    {f'<div class="chart">{_bar_chart(result.round1_adj, "1o turno: votos validos projetados (com correcao de vies)")}</div>' if result.round1_adj is not None else ''}
    <div class="chart">{_margin_hist(r1, '1o turno: distribuicao da margem entre os dois lideres')}</div>
    <div class="chart">{_timeline(all_polls, result, 1, r1.estimate['candidate_key'].tolist()[:2],
                                  '1o turno: pesquisas (pontos) e media ponderada movel (linha), desde julho')}</div>
    <h3>Pesquisas usadas no 1o turno</h3>
    <p class="footnote">Uma pesquisa por instituto (a mais recente na janela). Peso = precisao x recencia x amostra.
    "EAM 2022" e o erro absoluto medio do instituto nas disputas presidenciais de 2022 (vazio = sem historico, recebe a mediana).</p>
    {_polls_table(r1)}
    """)

    if r2 is not None:
        a, b = r2.estimate.iloc[0], r2.estimate.iloc[1]
        sections.append(f"""
        <h2>2o Turno</h2>
        {_summary_table(r2, result.round2_adj)}
        <div class="chart">{_bar_chart(r2, f"2o turno: {a['candidate']} x {b['candidate']} (sem correcao)")}</div>
        {f'<div class="chart">{_bar_chart(result.round2_adj, "2o turno: com correcao de vies")}</div>' if result.round2_adj is not None else ''}
        <div class="chart">{_margin_hist(r2, '2o turno: distribuicao da margem simulada')}</div>
        <div class="chart">{_timeline(all_polls, result, 2, r2.estimate['candidate_key'].tolist()[:2],
                                      '2o turno: pesquisas (pontos) e media ponderada movel (linha), desde julho')}</div>
        <h3>Pesquisas usadas no 2o turno</h3>
        {_polls_table(r2)}
        """)

    known = sorted(result.eam_by_pollster.items(), key=lambda kv: kv[1])
    known_html = ", ".join(f"{k} ({v:.1f})" for k, v in known)
    sections.append(f"""
    <div class="methodology">
    <h2>Metodologia</h2>
    <h3>Dados</h3>
    <p>Pesquisas presidenciais de 2002 a 2026 do agregador do <strong>Poder360</strong> (backend aberto
    <code>monitor-agregador.poder360.com.br</code>), turnos 1 e 2, ambito nacional. As eleicoes passadas alimentam
    a precisao por instituto, o sigma e o vies; a de 2026 alimenta a projecao. Para cada pesquisa e usado
    o cenario principal: no 1o turno, o cenario com mais candidatos; no 2o turno, o confronto
    {pair_names[0]} x {pair_names[1]}.</p>
    <h3>Selecao e pesos</h3>
    <p>Janela de {result.window_days} dias ate {result.as_of.strftime('%d/%m/%Y')}, uma pesquisa por instituto (a mais recente).
    Percentuais rebaseados para votos validos (indecisos, brancos e nulos fora do denominador).
    Peso de cada pesquisa = <code>(EAM mediano / EAM do instituto) x exp(-idade em dias / {config.PROJECTION_RECENCY_TAU_DAYS:.0f})
    x min(sqrt(amostra / {config.PROJECTION_REFERENCE_SAMPLE}), 2)</code>.
    O EAM vem do relatorio de precisao deste projeto (disputas presidenciais desde 2002, ambos os turnos, cada eleicao
    com peso <code>0.5 ** ((2022 - ano) / {config.PROJECTION_HISTORY_HALF_LIFE_YEARS:.0f})</code>): {known_html}. Mediana: {result.median_eam:.1f} pp. Institutos sem historico recebem a mediana (peso 1).</p>
    <h3>Simulacao</h3>
    <p>{result.n_sims:,} simulacoes. Em cada uma, a margem entre os dois primeiros recebe um choque
    <code>N(0, sigma)</code> (metade para cada lado), com sigma de <strong>{(result.sigma_margin_r1 or result.sigma_margin):.1f} pp no 1o turno</strong>
    e <strong>{result.sigma_margin:.1f} pp no 2o turno</strong>; os demais candidatos recebem ruido
    <code>N(0, {result.sigma_other:.1f} pp)</code>; as parcelas sao truncadas em zero e renormalizadas a 100%.
    Cada sigma e o maior entre {config.PROJECTION_SIGMA_FLOOR:.1f} pp e o RMSE do erro da media dos institutos
    na margem entre os dois primeiros nas disputas historicas daquele turno (2002-2022). Intervalos sao os percentis 5 e 95.</p>
    <h3>Correcao de vies</h3>
    <p>Para cada disputa presidencial passada com um candidato de esquerda e um de direita entre os dois primeiros,
    calculamos o erro da media dos institutos na margem <em>esquerda - direita</em> (positivo = as pesquisas superestimaram
    a esquerda). A media ponderada por recencia desses erros e <strong>{result.bias_margin:+.1f} pp</strong>. Na variante
    "com correcao", a margem projetada entre os dois lideres e deslocada por esse valor (metade para cada lado) antes da
    simulacao. E uma escolha de julgamento: com poucas eleicoes, o vies pode nao se repetir.</p>
    {_bias_table(result)}
    <h3>Ressalvas</h3>
    <ul>
      <li>A calibracao usa 12 disputas historicas (2002-2022, dois turnos). Eleicoes antigas pesam menos, mas
          candidatos, institutos e metodos mudaram muito no periodo.</li>
      <li>Institutos ausentes do agregador do Poder360 nao entram (ex.: Verita, Palver, DataTrends, Indexa).</li>
      <li>O modelo nao estima efeito sistematico por instituto (house effect) nem tendencia; a media movel
          e apenas descritiva.</li>
      <li>Entretenimento pessoal. Nao use para decisoes.</li>
    </ul>
    </div>
    """)

    html = ("<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
            "<title>Projecao Presidencial 2026</title>" + CSS + "</head><body>"
            + "".join(sections) + "</body></html>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
