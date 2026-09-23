import duckdb
import pandas as pd

from pollster.stages import fetch_poder360 as FP


def _fake_download(turno, year=2026):
    return [{"id": year * 10 + turno, "instituto": "Quaest", "data": f"{year}-09-20", "contratante": "Globo",
             "entrevistas": 2004, "margem": 2, "registro": "BR-2",
             "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 37},
                            {"nome": "Flávio Bolsonaro", "partido": "PL", "percentual": 33}]]}]


def test_fetch_poder360_writes_all_years_and_polls_2026(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(FP, "download_polls", _fake_download)
    FP.fetch_poder360(tmp_data_dir, years=[2022, 2026], force=True)
    df = pd.read_parquet(tmp_data_dir / "parquet" / "poder360_presidential.parquet")
    assert df.columns[0] == "ano"
    assert sorted(df["ano"].unique()) == [2022, 2026]
    assert sorted(df["turno"].unique()) == [1, 2]
    p26 = pd.read_parquet(tmp_data_dir / "parquet" / "polls_2026.parquet")
    assert p26["ano"].unique().tolist() == [2026] and len(p26) == 4
    con = duckdb.connect(str(tmp_data_dir / "pollster.duckdb"))
    assert con.execute("SELECT COUNT(*) FROM poder360_presidential").fetchone()[0] == 8
    assert con.execute("SELECT COUNT(*) FROM polls_2026").fetchone()[0] == 4
    con.close()


def test_fetch_poder360_skips_download_when_parquet_exists(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(FP, "download_polls", _fake_download)
    FP.fetch_poder360(tmp_data_dir, years=[2026], force=True)

    def boom(turno, year=2026):
        raise AssertionError("should not download")
    monkeypatch.setattr(FP, "download_polls", boom)
    FP.fetch_poder360(tmp_data_dir, years=[2026], force=False)
    con = duckdb.connect(str(tmp_data_dir / "pollster.duckdb"))
    assert con.execute("SELECT COUNT(*) FROM polls_2026").fetchone()[0] == 4
    con.close()


def test_download_polls_posts_expected_payload(monkeypatch):
    captured = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return [{"id": 1, "apuracoes": []}]

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers)
        return Resp()
    monkeypatch.setattr(FP.requests, "post", fake_post)
    assert FP.download_polls(2, 2018) == [{"id": 1, "apuracoes": []}]
    assert captured["json"] == {"cargosId": 3, "ano": 2018, "turno": "2",
                                "unidadesFederativasId": 6, "cidade": "", "pagina": 1}
    assert captured["headers"]["Origin"] == "https://drive.poder360.com.br"
