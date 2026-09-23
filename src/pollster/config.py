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
PROJECTION_MIN_SCENARIO_TOTAL = 85.0   # scenarios summing less are incomplete API rows

# --- Prediction markets (storage only; not used by the analysis) --------------

POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
# Event slugs verified on 2026-09-23 (gamma-api /events/slug/{slug}).
POLYMARKET_EVENT_SLUGS: list[str] = [
    "brazil-presidential-election",
    "brazil-presidential-election-first-round-winner",
    "brazil-presidential-election-first-round-2nd-place",
    "brazil-presidential-election-first-round-3rd-place",
    "which-candidates-will-advance-to-brazils-presidential-runoff",
    "will-any-presidential-candidate-win-outright-in-the-first-round-of-the-brazil-election",
    "brazil-presidential-election-first-round-lula-da-silva-vote-share",
    "who-will-trump-endorse-for-president-of-brazil-20260803210809",
    "lula-participates-in-debate-before-first-round",
    "will-the-workers-party-nominate-lula-for-president-of-brazil-by-august-15",
]

KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
# Series tickers verified on 2026-09-23 (all open Brazil-election series).
KALSHI_SERIES_TICKERS: list[str] = [
    "KXBRPRES", "KXBRPRES1R", "KXBRAZILPRES1R", "KXBRPRESADVANCE", "KXBRPRES1MOV",
    "KXBRPRESIDENT2", "KXBRPRESIDENT3", "KXBRPRESIDENT4", "KXBRPRESIDENT5",
    "KXVOTEBR1", "KXBRBALLOT", "KXTRUMPFLAVIO",
    "KXBRSENMOSTSEATS", "KXBRAZILSENATE", "KXBRDEP", "KXBRGOVMOSTSEATS", "KXDFGOV",
]
KALSHI_HISTORY_START = date(2025, 1, 1)
