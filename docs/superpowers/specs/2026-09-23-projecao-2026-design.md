# Projecao da eleicao presidencial de 2026 — design

Data: 2026-09-23 (13 dias antes do 1o turno, em 4 de outubro de 2026).
Uso: pessoal / entretenimento. Nao e um produto.

## Objetivo

1. Trazer para o projeto as pesquisas presidenciais de 2026 (1o e 2o turno), que nao
   existem no Base dos Dados (o dataset Poder360 parou em nov/2023).
2. Gerar uma projecao do resultado do 1o e do 2o turno, com probabilidades, a partir
   de uma media ponderada das pesquisas recentes e simulacao Monte Carlo calibrada pelo
   erro historico dos institutos que o projeto ja calcula.

## Fonte de dados 2026

Backend do agregador do Poder360 (aberto, sem login, para 2026):

- `POST https://monitor-agregador.poder360.com.br/pesquisas/v1/api`
- corpo JSON: `{"cargosId": 3, "ano": 2026, "turno": "1"|"2", "unidadesFederativasId": 6, "cidade": "", "pagina": 1}`
  (cargo 3 = presidente; UF 6 = Brasil)
- headers: `User-Agent` de navegador e `Origin: https://drive.poder360.com.br`
- resposta: lista de pesquisas `{id, instituto, data, contratante, entrevistas, margem, registro, apuracoes, noticias, integra}`;
  `apuracoes` e uma lista com uma unica lista plana de `{nome, partido, percentual}`.

Quirks conhecidos (tratados no parser):

- `entrevistas` vem com separador de milhar interpretado como decimal (`2.006` = 2006).
  Regra: valor < 100 -> multiplicar por 1000.
- A lista plana de `apuracoes[0]` pode concatenar varios cenarios (ex.: Lula x Flavio,
  Lula x Caiado...). Regra de corte: um novo cenario comeca quando um nome de candidato
  ja visto no cenario atual aparece de novo. Entradas sem `nome` sao ignoradas.
- `partido` pode faltar; "brancos/nulos", "indecisos", "nenhum" etc. sao classificados
  como nao-validos por padrao de texto.

## Componentes

### 1. `stages/fetch2026.py` — `fetch_2026(data_dir, force)`

- Baixa os dois turnos, normaliza para um DataFrame longo:
  `poll_id, instituto, pollster_display_name, data, contratante, entrevistas, margem,
  registro, turno, cenario_idx, nome_candidato, partido, percentual, is_valid_candidate`
- Salva `data/parquet/polls_2026.parquet` e registra a tabela `polls_2026` no DuckDB.
- `pollster_display_name` usa `normalize_pollster_name` + novo dicionario
  `POLLSTER_ALIASES_2026` em `config.py` para casar com os nomes historicos
  (`AtlasIntel`->`AtlasIntel/Internet`, `Futura Inteligencia`->`Futura`, `Ipec`->`IBOPE/Ipec`,
  `Instituto Ideia`->`Ideia Big Data`, `CNT (...)`->`MDA`).
- Sem cache por padrao? Nao: mesmo comportamento do `fetch` (pula se o parquet existe,
  `--force` rebaixa). Os dados mudam toda semana, entao o README orienta usar `--force`.

### 2. `stages/project.py` — `project_election(con, as_of, window_days, n_sims, data_dir)`

Entradas: tabela `polls_2026`, tabela `poll_level_metrics` (para os pesos e o sigma).

Passos:

1. **Selecao**: cenario principal de cada pesquisa (1o turno: o cenario com mais
   candidatos validos; 2o turno: o cenario que contem Lula e Flavio Bolsonaro).
   Janela: pesquisas com `data` nos `window_days` (padrao 14) anteriores a `as_of`
   (padrao: hoje). Uma pesquisa por instituto (a mais recente) para nao superponderar
   institutos semanais.
2. **Rebase** para votos validos com `rebase_to_valid_votes` (so candidatos validos).
3. **Pesos** por pesquisa: `w = w_acc * w_rec * w_n`
   - `w_acc = median_EAM / EAM_instituto`, com `EAM_instituto` = media de `mae_top2`
     nas disputas presidenciais de 2022 (`poll_level_metrics`, `cargo='presidente'`,
     `year=2022`). Institutos sem historico recebem `EAM = mediana` (peso 1).
   - `w_rec = exp(-idade_dias / 7)`
   - `w_n = min(sqrt(entrevistas / 2000), 2)`
4. **Estimativa pontual**: media ponderada por candidato (validos), renormalizada a 100.
   Tambem calcula a media simples para comparacao.
5. **Sigma historico**: para cada disputa presidencial de 2022 (turnos 1 e 2), erro da
   media dos institutos na margem entre os 2 primeiros (`mean(predicted_margin) - actual_margin`).
   `sigma_margin = max(RMSE desses erros, 3.0)`. Os demais candidatos recebem
   `sigma_other = 1.5` pp. Ambos ficam expostos como constantes em `config.py`
   (`PROJECTION_SIGMA_FLOOR`, `PROJECTION_SIGMA_OTHER`).
6. **Monte Carlo** (`n_sims` = 10.000, seed fixa): em cada simulacao,
   `delta ~ N(0, sigma_margin)` e somado como `+delta/2` ao 1o e `-delta/2` ao 2o colocado;
   os demais recebem `N(0, sigma_other)` independentes; valores truncados em 0 e
   renormalizados a 100. Saidas do 1o turno: P(cada candidato em 1o), P(cada candidato
   entre os 2 primeiros), P(decisao no 1o turno, ou seja alguem > 50%), intervalos de
   90% de cada candidato e da margem.
7. **2o turno**: mesma media ponderada usando as pesquisas diretas Lula x Flavio da
   janela; P(vitoria) via `N(margem, sigma_margin)`. Intervalos de 90%.
8. Persiste `projection_2026_polls` (pesquisas usadas, pesos), `projection_2026_summary`
   (uma linha por candidato e turno) e `projection_2026_sims` nao e salvo (so agregados).

### 3. `stages/project_report.py` — `generate_projection_report(con, output_path, results)`

HTML em portugues em `data/reports/projecao_2026.html`, reutilizando `CSS`,
`_fig_to_svg` e `_render_table` de `report.py`:

- Resumo: estimativa pontual do 1o turno (validos), P(1o turno decide),
  P(2o turno Lula x Flavio), P(vitoria no 2o turno).
- Grafico de barras dos validos com intervalo de 90%.
- Histograma da margem simulada Lula - Flavio (1o e 2o turno).
- Serie temporal desde 1/jul/2026 dos validos dos 2 lideres por pesquisa, com a media
  ponderada movel de 14 dias.
- Tabela das pesquisas usadas com data, instituto, amostra, validos e peso.
- Metodologia e ressalvas (poucos pontos historicos, 2018 excluido, uso pessoal).

### 4. CLI

- `pollster fetch-2026 [--force]`
- `pollster project [--as-of YYYY-MM-DD] [--window-days 14] [--sims 10000]`
  (roda projecao + relatorio; exige `polls_2026` e `poll_level_metrics` no banco).

## Testes

- Parser: split de cenarios concatenados, `entrevistas` com milhar, entradas sem nome,
  classificacao de nao-validos.
- Fetch: mock de `requests.post`, verifica parquet + tabela.
- Projecao: fixture com 3 pesquisas sinteticas, checa pesos (instituto desconhecido
  recebe peso 1, decaimento por recencia), rebase, soma 100, probabilidades coerentes
  (lider com >50% de P(1o) quando margem >> sigma), reprodutibilidade por seed.
- Relatorio: gera HTML, contem as secoes e o nome dos candidatos.

## Fora de escopo

- Corrigir o casamento das disputas presidenciais de 2018 em `polls_vs_actual`
  (Datafolha com EAM 31 pp). Anotado para depois; a projecao usa so 2022.
- Governadores 2026, house effects, tendencia suavizada.
