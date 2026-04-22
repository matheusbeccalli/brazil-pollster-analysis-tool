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

## Inicio Rapido

Se voce quer apenas ver o relatorio, ele ja esta pronto no repositorio:

```bash
# Abrir o relatorio diretamente
xdg-open data/reports/pollster_accuracy_report.html   # Linux
open data/reports/pollster_accuracy_report.html        # macOS
```

Se voce quer regenerar a analise ou explorar os dados, siga as instrucoes abaixo.

## Instalacao

### 1. Clonar o repositorio

```bash
git clone https://github.com/seu-usuario/brazil-pollster-analysis-tool.git
cd brazil-pollster-analysis-tool
```

### 2. Criar ambiente virtual e instalar dependencias

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Apos a instalacao, o comando `pollster` estara disponivel no terminal (enquanto o ambiente virtual estiver ativo).

### 3. Verificar a instalacao

```bash
pollster --help
```

Deve mostrar os subcomandos disponiveis: `fetch`, `assemble`, `analyze`, `report`, `run`, `query`.

## Como Executar

### Opcao A: Usar os dados que ja estao no repositorio

Os arquivos Parquet com os dados brutos ja estao no repositorio (`data/parquet/`). Para regenerar a analise e o relatorio a partir deles, sem precisar baixar nada:

```bash
# Ativar o ambiente virtual (se ainda nao estiver ativo)
source .venv/bin/activate

# Reconstruir o banco DuckDB a partir dos parquets
pollster assemble

# Calcular metricas e rankings (desde 2000)
pollster analyze --since 2000

# Gerar o relatorio HTML
pollster report
```

O relatorio sera salvo em `data/reports/pollster_accuracy_report.html`.

**Importante:** O `assemble` precisa que as tabelas estejam registradas no DuckDB. Na primeira execucao apos o clone, rode `pollster fetch` (que vai detectar os parquets existentes e apenas registra-los, sem baixar nada) ou rode o pipeline completo com `pollster run`.

### Opcao B: Baixar dados frescos do Base dos Dados

Se voce quiser re-baixar os dados diretamente do Google BigQuery (por exemplo, quando novas eleicoes forem adicionadas ao Base dos Dados):

**Passo 1: Criar um projeto no Google Cloud (gratis)**

- Acesse https://console.cloud.google.com/
- Crie um projeto (ou use um existente) e anote o **ID do projeto** (ex: `meu-projeto-123456`)
- Ative a API do BigQuery: https://console.cloud.google.com/apis/library/bigquery.googleapis.com

Os dados consultados sao publicos e ficam dentro do limite gratuito do BigQuery (1 TB/mes — nossas consultas usam apenas alguns MB).

**Passo 2: Autenticar com o Google Cloud**

Instale o `gcloud` CLI se ainda nao tiver: https://cloud.google.com/sdk/docs/install

```bash
gcloud auth application-default login
```

Isso abre o navegador para login na conta Google e salva as credenciais localmente.

**Passo 3: Definir o ID do projeto e executar**

```bash
export BIGQUERY_PROJECT="seu-projeto-gcp"
pollster run --since 2000
```

Isso executa o pipeline completo: `fetch` (baixa os dados) -> `assemble` (cruza pesquisas com resultados) -> `analyze` (calcula metricas) -> `report` (gera HTML).

Para forcar o re-download mesmo que os parquets ja existam:

```bash
pollster run --since 2000 --force
```

### Opcao C: Executar etapas individualmente

Cada etapa do pipeline pode ser executada separadamente:

```bash
export BIGQUERY_PROJECT="seu-projeto-gcp"

# Etapa 1: Baixar dados do Base dos Dados
pollster fetch                  # pula se os parquets ja existem
pollster fetch --force          # forca re-download

# Etapa 2: Cruzar pesquisas com resultados oficiais
pollster assemble

# Etapa 3: Calcular metricas e rankings
pollster analyze                # padrao: desde 2014
pollster analyze --since 2000   # desde 2000
pollster analyze --since 2018   # apenas ciclos recentes

# Etapa 4: Gerar relatorio HTML
pollster report
```

## Explorando os Dados com SQL

Apos rodar o pipeline, voce pode fazer consultas SQL diretamente nos dados:

```bash
# Ranking dos 10 institutos mais precisos
pollster query "SELECT pollster_display_name, n_races, mean_mae
                FROM pollster_rankings ORDER BY mean_mae LIMIT 10"

# Pesquisas de 2022 para presidente
pollster query "SELECT instituto, nome_candidato, percentual
                FROM poder360_polls
                WHERE ano=2022 AND cargo='presidente' AND turno=1
                LIMIT 20"

# Erro por instituto na eleicao de 2022
pollster query "SELECT pollster_display_name, mae_top2, margin_error
                FROM poll_level_metrics WHERE year=2022"

# Ver todas as tabelas disponiveis
pollster query "SHOW TABLES"
```

### Formatos de saida

```bash
# Tabela formatada (padrao)
pollster query "SELECT * FROM pollster_rankings ORDER BY mean_mae"

# CSV
pollster query --format csv "SELECT * FROM pollster_rankings" > rankings.csv

# JSON
pollster query --format json "SELECT * FROM poll_level_metrics"

# Parquet
pollster query --format parquet --output resultado.parquet "SELECT * FROM poll_level_metrics"
```

### Tabelas disponiveis

| Tabela | Descricao |
|--------|-----------|
| `poder360_polls` | Dados brutos de pesquisas (Poder360) |
| `tse_results` | Resultados oficiais (TSE) |
| `tse_candidates` | Dados cadastrais dos candidatos (TSE) |
| `polls_vs_actual` | Pesquisas cruzadas com resultados oficiais |
| `poll_level_metrics` | Metricas de erro por pesquisa individual |
| `pollster_rankings` | Ranking geral dos institutos |
| `pollster_rankings_by_year` | Rankings por ano eleitoral |
| `pollster_rankings_by_round` | Rankings por turno |
| `pollster_rankings_by_race_type` | Rankings por tipo de disputa (presidente/governador) |

## Arquivos de Saida

Apos executar o pipeline, a pasta `data/` contera:

```
data/
├── parquet/                              # Dados em formato Parquet
│   ├── poder360_pesquisas.parquet        # Dados brutos de pesquisas
│   ├── tse_resultados_candidato.parquet  # Resultados oficiais do TSE
│   ├── tse_candidatos.parquet            # Dados dos candidatos
│   ├── polls_vs_actual.parquet           # Pesquisas cruzadas com resultados
│   ├── poll_level_metrics.parquet        # Metricas de erro por pesquisa
│   ├── pollster_rankings.parquet         # Ranking geral
│   ├── pollster_rankings_by_year.parquet # Rankings por ano
│   ├── pollster_rankings_by_round.parquet # Rankings por turno
│   └── pollster_rankings_by_race_type.parquet # Rankings por cargo
├── pollster.duckdb                       # Banco de dados local (gerado, nao versionado)
└── reports/
    └── pollster_accuracy_report.html     # Relatorio final
```

## Estrutura do Projeto

```
src/pollster/
├── cli.py              # CLI com Click (subcomandos por etapa)
├── config.py           # Datas eleitorais, partidos, merges de institutos
├── db.py               # Helper DuckDB
├── stages/
│   ├── fetch.py        # Etapa 1: download do Base dos Dados via BigQuery
│   ├── assemble.py     # Etapa 2: cruzamento pesquisas x resultados
│   ├── analyze.py      # Etapa 3: metricas, rankings, bootstrap CIs
│   └── report.py       # Etapa 4: relatorio HTML com graficos SVG
└── utils/
    ├── normalize.py    # Normalizacao de nomes de institutos
    ├── rebase.py       # Rebase de percentuais para votos validos
    └── candidates.py   # Match fuzzy de nomes de candidatos
```

## Fontes de Dados

- **Pesquisas:** `basedosdados.br_poder360_pesquisas.microdados` — banco de dados do Poder360 com pesquisas eleitorais
- **Resultados:** `basedosdados.br_tse_eleicoes.resultados_candidato` — resultados oficiais do TSE
- **Candidatos:** `basedosdados.br_tse_eleicoes.candidatos` — dados cadastrais dos candidatos

Todos acessados via [Base dos Dados](https://basedosdados.org/), uma iniciativa brasileira de dados abertos.

## Adicionando Uma Nova Eleicao (ex: 2026)

1. Aguardar o Base dos Dados atualizar os datasets com os dados de 2026
2. Adicionar as datas da eleicao em `src/pollster/config.py` (dicionario `ELECTIONS`)
3. Adicionar novos partidos/institutos se necessario em `config.py`
4. Executar:

```bash
export BIGQUERY_PROJECT="seu-projeto-gcp"
pollster fetch --force
pollster assemble
pollster analyze --since 2000
pollster report
```

## Testes

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Licenca

MIT
