import pandas as pd
import numpy as np


def make_polls_df():
    """Minimal realistic poll data for 2022 presidential round 1."""
    rows = []
    # Datafolha poll - 2022-09-30 (final before R1 on Oct 2)
    for cand, party, pct in [("LULA", "PT", 48.0), ("BOLSONARO", "PL", 34.0),
                              ("TEBET", "MDB", 8.0), ("CIRO", "PDT", 6.0)]:
        rows.append({
            "id_pesquisa": "P1", "id_cenario": "C1",
            "id_candidato_poder360": f"cand_{cand}",
            "ano": 2022, "data": pd.Timestamp("2022-09-30"),
            "data_referencia": "2022-10", "turno": 1,
            "cargo": "Presidente", "sigla_uf": "BR", "nome_municipio": None,
            "instituto": "Datafolha", "contratante": "Folha",
            "orgao_registro": "TSE", "numero_registro": "BR-001/2022",
            "quantidade_entrevistas": 2000.0,
            "margem_mais": 2.0, "margem_menos": 2.0,
            "tipo": "estimulada", "tipo_voto": None,
            "descricao_cenario": "cenario 1",
            "nome_candidato": cand, "sigla_partido": party,
            "condicao": 0, "percentual": pct,
        })
    # AtlasIntel poll - 2022-10-01 (also before R1)
    for cand, party, pct in [("LULA", "PT", 50.5), ("BOLSONARO", "PL", 36.2),
                              ("TEBET", "MDB", 5.5), ("CIRO", "PDT", 4.8)]:
        rows.append({
            "id_pesquisa": "P2", "id_cenario": "C1",
            "id_candidato_poder360": f"cand_{cand}",
            "ano": 2022, "data": pd.Timestamp("2022-10-01"),
            "data_referencia": "2022-10", "turno": 1,
            "cargo": "Presidente", "sigla_uf": "BR", "nome_municipio": None,
            "instituto": "AtlasIntel", "contratante": "proprio",
            "orgao_registro": "TSE", "numero_registro": "BR-002/2022",
            "quantidade_entrevistas": 3000.0,
            "margem_mais": 1.5, "margem_menos": 1.5,
            "tipo": "estimulada", "tipo_voto": None,
            "descricao_cenario": "cenario 1",
            "nome_candidato": cand, "sigla_partido": party,
            "condicao": 0, "percentual": pct,
        })
    return pd.DataFrame(rows)


def make_results_df():
    """Official results for 2022 presidential round 1."""
    rows = []
    for cand_num, seq, name, party, votes, resultado in [
        ("13", "seq1", "LUIZ INACIO LULA DA SILVA", "PT", 57259504, "2o turno"),
        ("22", "seq2", "JAIR MESSIAS BOLSONARO", "PL", 51072345, "2o turno"),
        ("15", "seq3", "SIMONE NASSAR TEBET", "MDB", 4915423, "nao eleito"),
        ("12", "seq4", "CIRO FERREIRA GOMES", "PDT", 3599287, "nao eleito"),
    ]:
        rows.append({
            "ano": 2022, "turno": 1, "tipo_eleicao": "eleicao ordinaria",
            "sigla_uf": "BR", "id_municipio": None, "id_municipio_tse": None,
            "cargo": "presidente",
            "numero_partido": cand_num[:2], "sigla_partido": party,
            "numero_candidato": cand_num, "sequencial_candidato": seq,
            "id_candidato_bd": f"bd_{seq}",
            "resultado": resultado, "votos": votes,
        })
    return pd.DataFrame(rows)


def make_candidates_df():
    """Candidate details for resolving names."""
    rows = [
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero": "13", "sequencial": "seq1",
         "nome": "LUIZ INACIO LULA DA SILVA",
         "nome_urna": "LULA", "sigla_partido": "PT"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero": "22", "sequencial": "seq2",
         "nome": "JAIR MESSIAS BOLSONARO",
         "nome_urna": "BOLSONARO", "sigla_partido": "PL"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero": "15", "sequencial": "seq3",
         "nome": "SIMONE NASSAR TEBET",
         "nome_urna": "TEBET", "sigla_partido": "MDB"},
        {"ano": 2022, "tipo_eleicao": "eleicao ordinaria", "sigla_uf": "BR",
         "cargo": "presidente", "numero": "12", "sequencial": "seq4",
         "nome": "CIRO FERREIRA GOMES",
         "nome_urna": "CIRO", "sigla_partido": "PDT"},
    ]
    return pd.DataFrame(rows)
