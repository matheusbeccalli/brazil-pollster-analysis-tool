from datetime import date

ELECTIONS: dict[int, dict[str, date]] = {
    2002: {"round_1": date(2002, 10, 6), "round_2": date(2002, 10, 27)},
    2006: {"round_1": date(2006, 10, 1), "round_2": date(2006, 10, 29)},
    2010: {"round_1": date(2010, 10, 3), "round_2": date(2010, 10, 31)},
    2014: {"round_1": date(2014, 10, 5), "round_2": date(2014, 10, 26)},
    2018: {"round_1": date(2018, 10, 7), "round_2": date(2018, 10, 28)},
    2022: {"round_1": date(2022, 10, 2), "round_2": date(2022, 10, 30)},
    2026: {"round_1": date(2026, 10, 4), "round_2": date(2026, 10, 25)},
}

DEFAULT_SINCE_YEAR = 2014

PARTY_LEANING: dict[str, str] = {
    # Left
    "PT": "left",
    "PSOL": "left",
    "PCdoB": "left",
    "PDT": "left",
    "PCB": "left",
    "PCO": "left",
    "PSTU": "left",
    "UP": "left",
    "REDE": "left",
    "PV": "left",
    "PSB": "left",
    # Center
    "MDB": "center",
    "PMDB": "center",
    "PSD": "center",
    "CIDADANIA": "center",
    "PPS": "center",
    "PODE": "center",
    "SOLIDARIEDADE": "center",
    "SD": "center",
    "AVANTE": "center",
    "PMN": "center",
    "PROS": "center",
    # Right
    "PSDB": "right",
    "PL": "right",
    "PP": "right",
    "DEM": "right",
    "PFL": "right",
    "REPUBLICANOS": "right",
    "PRB": "right",
    "PTB": "right",
    "PSC": "right",
    "PATRIOTA": "right",
    "PSL": "right",
    "NOVO": "right",
    "UNIÃO": "right",
    "UNIÃO BRASIL": "right",
}

POLLSTER_MERGES: dict[str, str] = {
    "Ibope": "IBOPE/Ipec",
    "IBOPE": "IBOPE/Ipec",
    "Ibope Inteligência": "IBOPE/Ipec",
    "Ipec": "IBOPE/Ipec",
    "IPEC": "IBOPE/Ipec",
}

POLLSTER_ALIASES: dict[str, str] = {
    "Instituto Datafolha": "Datafolha",
    "Datafolha Instituto de Pesquisas": "Datafolha",
}

BIGQUERY_BILLING_PROJECT: str | None = None

BIGQUERY_TABLES = {
    "polls": "basedosdados.br_poder360_pesquisas.microdados",
    "results": "basedosdados.br_tse_eleicoes.resultados_candidato",
    "candidates": "basedosdados.br_tse_eleicoes.candidatos",
}

DATA_DIR_NAME = "data"
DB_FILENAME = "pollster.duckdb"

# --- 2026 projection -------------------------------------------------------

# Poder360 aggregator names -> historical display names used in the rankings.
POLLSTER_ALIASES_2026: dict[str, str] = {
    "AtlasIntel": "AtlasIntel/Internet",
    "Futura Inteligência": "Futura",
    "Ipec": "IBOPE/Ipec",
    "Instituto Ideia": "Ideia Big Data",
    "CNT (Confederação Nacional do Transporte)": "MDA",
}

# Open backend of the Poder360 aggregator (no login needed for the 2026 cycle).
PODER360_AGREGADOR_URL = "https://monitor-agregador.poder360.com.br/pesquisas/v1/api"
PODER360_CARGO_PRESIDENTE = 3
PODER360_UF_BRASIL = 6

PROJECTION_YEAR = 2026
PROJECTION_WINDOW_DAYS = 14            # polls considered: last N days before --as-of
PROJECTION_RECENCY_TAU_DAYS = 7.0      # weight = exp(-age_days / tau)
PROJECTION_REFERENCE_SAMPLE = 2000     # weight = min(sqrt(n / ref), 2)
PROJECTION_SIGMA_FLOOR = 3.0           # min. sigma (pp) of the top-2 margin error
PROJECTION_SIGMA_OTHER = 1.5           # sigma (pp) for candidates outside the top 2
PROJECTION_N_SIMS = 10_000
PROJECTION_SEED = 2026
PROJECTION_RUNOFF_PAIR = ("Lula", "Flávio Bolsonaro")
PROJECTION_HISTORY_YEARS = (2022,)     # 2018 presidential rows are mis-matched; excluded
