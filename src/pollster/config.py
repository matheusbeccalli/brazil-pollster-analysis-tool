from datetime import date

ELECTIONS: dict[int, dict[str, date]] = {
    2002: {"round_1": date(2002, 10, 6), "round_2": date(2002, 10, 27)},
    2006: {"round_1": date(2006, 10, 1), "round_2": date(2006, 10, 29)},
    2010: {"round_1": date(2010, 10, 3), "round_2": date(2010, 10, 31)},
    2014: {"round_1": date(2014, 10, 5), "round_2": date(2014, 10, 26)},
    2018: {"round_1": date(2018, 10, 7), "round_2": date(2018, 10, 28)},
    2022: {"round_1": date(2022, 10, 2), "round_2": date(2022, 10, 30)},
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
