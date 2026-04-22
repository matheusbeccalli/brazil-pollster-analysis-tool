# Analise de Precisao dos Institutos de Pesquisa Eleitoral Brasileiros

Ferramenta CLI em Python que classifica institutos de pesquisa brasileiros por precisao preditiva, comparando suas pesquisas finais pre-eleitorais com os resultados oficiais do TSE.

## O que faz

Baixa dados de pesquisas eleitorais (Poder360 via Base dos Dados) e resultados oficiais (TSE), cruza as previsoes com os resultados reais e gera um relatorio HTML com rankings, graficos e analise de vies partidario.

**Cobertura:** Eleicoes presidenciais e para governador, ambos os turnos, de 2000 a 2022.

## Resultados

O relatorio gerado esta em `data/reports/pollster_accuracy_report.html`. Os dados processados estao em `data/parquet/`.

### Metricas principais

- **EAM (Erro Absoluto Medio):** Media dos erros absolutos para os 2 candidatos mais votados (Medida de Mosteller 3)
- **Erro de Margem:** Erro na diferenca prevista entre os candidatos lideres
- **Vies Partidario:** Erro medio com sinal por orientacao politica (esquerda/direita)
- **Intervalos de Confianca:** Bootstrap 95% (10.000 reamostragens)

## Instalacao

```bash
git clone https://github.com/seu-usuario/brazil-pollster-analysis-tool.git
cd brazil-pollster-analysis-tool
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Pre-requisitos para baixar dados

A etapa de download (`fetch`) consulta o Google BigQuery. E necessario:

1. Uma conta Google com um projeto no Google Cloud (gratis — os dados consultados estao dentro do limite gratuito de 1 TB/mes)
2. Autenticacao via `gcloud`:

```bash
gcloud auth application-default login
```

3. Definir o ID do projeto:

```bash
export BIGQUERY_PROJECT="seu-projeto-gcp"
```

Se voce nao precisar re-baixar os dados (os parquets ja estao no repositorio), pode pular direto para `assemble`.

## Uso

### Pipeline completo

```bash
pollster run                    # fetch -> assemble -> analyze -> report
pollster run --since 2014       # analisar apenas de 2014 em diante
pollster run --force            # re-baixar dados mesmo se ja existirem
```

### Etapas individuais

```bash
pollster fetch                  # baixar dados do Base dos Dados
pollster assemble               # cruzar pesquisas com resultados oficiais
pollster analyze --since 2000   # calcular metricas e rankings
pollster report                 # gerar relatorio HTML
```

### Consultas ad-hoc

```bash
# Top 10 institutos mais precisos
pollster query "SELECT * FROM pollster_rankings ORDER BY mean_mae LIMIT 10"

# Exportar para CSV
pollster query --format csv "SELECT * FROM poll_level_metrics" > metricas.csv

# Consulta a partir de arquivo SQL
pollster query --sql-file minha_consulta.sql
```

## Estrutura do projeto

```
src/pollster/
├── cli.py              # CLI com Click (subcomandos por etapa)
├── config.py           # Datas eleitorais, partidos, merges de institutos
├── db.py               # Helper DuckDB
├── stages/
│   ├── fetch.py        # Etapa 1: download do Base dos Dados
│   ├── assemble.py     # Etapa 2: cruzamento pesquisas x resultados
│   ├── analyze.py      # Etapa 3: metricas, rankings, bootstrap
│   └── report.py       # Etapa 4: relatorio HTML com graficos SVG
└── utils/
    ├── normalize.py    # Normalizacao de nomes de institutos
    ├── rebase.py       # Rebase para votos validos
    └── candidates.py   # Match fuzzy de nomes de candidatos
```

## Fontes de dados

- **Pesquisas:** `basedosdados.br_poder360_pesquisas.microdados` — banco de dados do Poder360 com pesquisas eleitorais
- **Resultados:** `basedosdados.br_tse_eleicoes.resultados_candidato` — resultados oficiais do TSE
- **Candidatos:** `basedosdados.br_tse_eleicoes.candidatos` — dados cadastrais dos candidatos

Todos acessados via [Base dos Dados](https://basedosdados.org/), uma iniciativa brasileira de dados abertos.

## Testes

```bash
pytest tests/ -v
```

## Licenca

MIT
