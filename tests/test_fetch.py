import pandas as pd
import pytest
from unittest.mock import patch

from pollster.stages.fetch import fetch_data, _save_and_register


@pytest.fixture
def sample_polls_df():
    return pd.DataFrame({
        "id_pesquisa": ["P1", "P1", "P2", "P2"],
        "id_cenario": ["C1", "C1", "C1", "C1"],
        "id_candidato_poder360": ["1", "2", "1", "2"],
        "ano": [2022, 2022, 2022, 2022],
        "data": pd.to_datetime(["2022-09-30", "2022-09-30", "2022-09-28", "2022-09-28"]),
        "data_referencia": ["2022-10", "2022-10", "2022-10", "2022-10"],
        "turno": [1, 1, 1, 1],
        "cargo": ["PRESIDENTE", "PRESIDENTE", "PRESIDENTE", "PRESIDENTE"],
        "sigla_uf": ["BR", "BR", "BR", "BR"],
        "nome_municipio": [None, None, None, None],
        "instituto": ["Datafolha", "Datafolha", "AtlasIntel", "AtlasIntel"],
        "contratante": ["Folha", "Folha", "proprio", "proprio"],
        "orgao_registro": ["TSE", "TSE", "TSE", "TSE"],
        "numero_registro": ["BR-001/2022", "BR-001/2022", "BR-002/2022", "BR-002/2022"],
        "quantidade_entrevistas": [2000.0, 2000.0, 3000.0, 3000.0],
        "margem_mais": [2.0, 2.0, 1.5, 1.5],
        "margem_menos": [2.0, 2.0, 1.5, 1.5],
        "tipo": ["estimulada", "estimulada", "estimulada", "estimulada"],
        "tipo_voto": [None, None, None, None],
        "descricao_cenario": ["cenario 1", "cenario 1", "cenario 1", "cenario 1"],
        "nome_candidato": ["LULA", "BOLSONARO", "LULA", "BOLSONARO"],
        "sigla_partido": ["PT", "PL", "PT", "PL"],
        "condicao": [1, 1, 1, 1],
        "percentual": [48.0, 34.0, 50.5, 36.2],
    })


def test_save_and_register(tmp_data_dir, sample_polls_df):
    from pollster.db import get_connection

    parquet_path = tmp_data_dir / "parquet" / "test.parquet"
    con = get_connection(tmp_data_dir)

    _save_and_register(con, sample_polls_df, "test_table", parquet_path)

    assert parquet_path.exists()
    result = con.execute("SELECT COUNT(*) FROM test_table").fetchone()
    assert result == (4,)
    con.close()
