import duckdb
import pandas as pd
from pollster.stages import fetch2026


def _fake_download(turno, year=2026):
    return [{"id": turno, "instituto": "Quaest", "data": "2026-09-20", "contratante": "Globo",
             "entrevistas": 2004, "margem": 2, "registro": "BR-2",
             "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 37},
                            {"nome": "Flávio Bolsonaro", "partido": "PL", "percentual": 33}]]}]


def test_fetch_2026_writes_parquet_and_table(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(fetch2026, "download_polls", _fake_download)
    fetch2026.fetch_2026(tmp_data_dir, force=True)
    df = pd.read_parquet(tmp_data_dir / "parquet" / "polls_2026.parquet")
    assert sorted(df["turno"].unique()) == [1, 2]
    con = duckdb.connect(str(tmp_data_dir / "pollster.duckdb"))
    assert con.execute("SELECT COUNT(*) FROM polls_2026").fetchone()[0] == 4
    con.close()


def test_fetch_2026_skips_download_when_parquet_exists(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(fetch2026, "download_polls", _fake_download)
    fetch2026.fetch_2026(tmp_data_dir, force=True)

    def boom(turno, year=2026):
        raise AssertionError("should not download")
    monkeypatch.setattr(fetch2026, "download_polls", boom)
    fetch2026.fetch_2026(tmp_data_dir, force=False)
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
    monkeypatch.setattr(fetch2026.requests, "post", fake_post)
    out = fetch2026.download_polls(2)
    assert out == [{"id": 1, "apuracoes": []}]
    assert captured["json"] == {"cargosId": 3, "ano": 2026, "turno": "2",
                                "unidadesFederativasId": 6, "cidade": "", "pagina": 1}
    assert captured["headers"]["Origin"] == "https://drive.poder360.com.br"
