# Historico presidencial completo (2002-2022) e correcao de vies — design

Data: 2026-09-23. Continuacao de `2026-09-23-projecao-2026-design.md`.

## Problema

1. O espelho do Poder360 no Base dos Dados nao tem nenhuma pesquisa presidencial de 2018
   (ultima: dez/2017) e as de 2002-2014 existem mas nao casam com o TSE porque `nome_urna`
   e so o primeiro nome ("Dilma", "Serra") e o matcher usa `token_sort_ratio` (53 < 75).
2. A projecao pondera pela magnitude do erro (EAM) mas ignora a direcao. Em 2018 e 2022 a
   media dos institutos superestimou a margem do candidato de esquerda.

## Decisoes

- **Fonte unica para pesquisas presidenciais nacionais: o backend aberto do agregador do
  Poder360**, que cobre 2002-2022 (ambos os turnos, com partido) e 2026. Verificado em
  2026-09-23: 2002 (75/56 pesquisas), 2006 (52/23), 2010 (101/66), 2014 (61/78),
  2018 (109/102), 2022 (211/235). Nao ha 1989-1998 (o TSE tem resultados, mas sem pesquisas
  nessa fonte; fica fora).
- As pesquisas para governador continuam vindo do Base dos Dados. As linhas presidenciais
  nacionais do Base dos Dados (`sigla_uf IS NULL`) sao descartadas no `assemble` quando a
  tabela do backend existe, para nao duplicar.
- Matcher: exato → `token_set_ratio >= 85` (100 quando um nome e subconjunto do outro; empate
  desfeito pelo partido) → partido unico. O partido tambem e usado na selecao de cenario.
- Historico na projecao: todas as eleicoes presidenciais disponiveis, com **peso por recencia**
  `0.5 ** ((2022 - ano) / 8)` (meia-vida de duas eleicoes) para EAM por instituto e para o vies.
  O sigma da margem usa o RMSE nao ponderado dos erros da media dos institutos por disputa,
  com o mesmo piso de 3 pp.
- **Vies global historico**: para cada disputa presidencial, erro da media dos institutos na
  margem `esquerda - direita` (usando `PARTY_LEANING`). O vies e a media ponderada por
  recencia desses erros. A projecao gera duas variantes: `sem correcao` (atual) e
  `com correcao` (margem dos dois lideres deslocada por `-vies`, aplicando metade a cada um,
  na direcao esquerda→direita conforme o partido). O relatorio mostra as duas lado a lado e o
  resumo destaca as duas probabilidades.

## Componentes

- `stages/fetch2026.py` → renomeado para `stages/fetch_poder360.py`; `fetch_poder360(data_dir,
  years, force)` baixa cada ano em `years` (padrao: anos em `ELECTIONS`), turnos 1 e 2, e grava
  `poder360_presidential.parquet` / tabela `poder360_presidential` (mesmo formato longo de
  `polls_2026`, mais coluna `ano`). `polls_2026` passa a ser a tabela filtrada `ano = 2026`
  (mantida para `project`). CLI: `fetch-poder360 [--years 2018,2022] [--force]`; `fetch-2026`
  vira alias de `fetch-poder360 --years 2026`.
- `stages/assemble.py`: `_load_polls(con)` une Base dos Dados (sem presidente nacional) com
  `poder360_presidential` convertido para o esquema `poder360_polls` (`sigla_uf='BR'`,
  `condicao` 0/1 por `is_valid_candidate`, `id_cenario = poll_id-cenario_idx`).
- `utils/candidates.py`: novo criterio de match.
- `config.py`: `POLLSTER_ALIASES_2026` renomeado `POLLSTER_ALIASES_PODER360` (+ "Paraná" →
  "Paraná Pesquisas"); `PROJECTION_HISTORY_YEARS` substituido por
  `PROJECTION_HISTORY_HALF_LIFE_YEARS = 8`; `PROJECTION_BIAS_CORRECTION = True`.
- `stages/project.py`: `pollster_accuracy` e `historical_sigma_margin` usam todos os anos;
  novo `historical_margin_bias(con)`; `ProjectionResult` ganha `bias_margin`, `round1_adj`,
  `round2_adj`; `projection_2026_summary` ganha coluna `variant` (`raw`/`bias_adjusted`).
- `stages/project_report.py`: resumo com as duas variantes; secoes de 1o e 2o turno mostram a
  tabela e o grafico de barras das duas; metodologia explica o vies e a tabela de erros
  historicos por eleicao (ano, turno, margem prevista, margem real, erro).

## Testes

Matcher (Dilma/Dilma Rousseff, Serra/José Serra, Bolsonaro x 2 com partido), conversao do
backend para o esquema `poder360_polls`, assemble com as duas fontes (sem duplicar), fetch com
varios anos mockado, `historical_margin_bias` com sinal correto, variantes na projecao e no
relatorio.

## Fora de escopo

1989-1998; house effects por instituto dentro de 2026; governadores pelo backend.
