from pollster.utils.poder360 import (parse_sample_size, is_valid_candidate, split_scenarios,
                                     polls_to_frame, candidate_key, normalize_pollster_2026)


def test_parse_sample_size_handles_thousands_as_decimal():
    assert parse_sample_size(2.006) == 2006
    assert parse_sample_size(2000) == 2000
    assert parse_sample_size("1.500") == 1500
    assert parse_sample_size(None) is None
    assert parse_sample_size(0) is None


def test_is_valid_candidate():
    assert is_valid_candidate("Lula")
    assert is_valid_candidate("Flávio Bolsonaro")
    for bad in ["brancos / nulos", "não sabem / não responderam", "indecisos", "nenhum deles",
                "ninguém / brancos / nulos", "Outros", "não iria votar", "não sabe / não opinou",
                "brancos / nulos / não vai votar", ""]:
        assert not is_valid_candidate(bad), bad


def test_split_scenarios_on_repeated_name():
    flat = [{"nome": "Lula", "percentual": 46}, {"nome": "Flávio Bolsonaro", "percentual": 44},
            {"nome": "brancos / nulos", "percentual": 8},
            {"nome": "Lula", "percentual": 49}, {"nome": "Romeu Zema", "percentual": 39},
            {"partido": "UP", "percentual": 1}]  # no name -> ignored
    scen = split_scenarios(flat)
    assert len(scen) == 2
    assert [e["nome"] for e in scen[0]] == ["Lula", "Flávio Bolsonaro", "brancos / nulos"]
    assert [e["nome"] for e in scen[1]] == ["Lula", "Romeu Zema"]


def test_split_scenarios_keeps_late_appended_candidate_in_same_scenario():
    flat = [{"nome": "Lula"}, {"nome": "brancos / nulos"}, {"nome": "indecisos"}, {"nome": "Renan Santos"}]
    assert len(split_scenarios(flat)) == 1


def test_candidate_key_is_accent_and_case_insensitive():
    assert candidate_key("Flavio  Bolsonaro") == candidate_key("FLÁVIO BOLSONARO") == "flavio bolsonaro"


def test_normalize_pollster_2026_maps_to_historical_names():
    assert normalize_pollster_2026("AtlasIntel") == "AtlasIntel/Internet"
    assert normalize_pollster_2026("Ipec") == "IBOPE/Ipec"
    assert normalize_pollster_2026("Nexus") == "Nexus"


def test_polls_to_frame_long_format():
    raw = [{"id": 1, "instituto": "AtlasIntel", "data": "2026-09-16T00:00:00.000Z",
            "contratante": "Bloomberg", "entrevistas": 5.018, "margem": 1, "registro": "BR-1",
            "apuracoes": [[{"nome": "Lula", "partido": "PT", "percentual": 44.1},
                            {"nome": "Flávio Bolsonaro", "partido": "PL", "percentual": 41.7},
                            {"nome": "brancos / nulos", "partido": "N/A", "percentual": 5}]]}]
    df = polls_to_frame(raw, turno=1)
    assert list(df.columns) == ["poll_id", "instituto", "pollster_display_name", "data", "contratante",
                                "entrevistas", "margem", "registro", "turno", "cenario_idx",
                                "nome_candidato", "candidate_key", "partido", "percentual",
                                "is_valid_candidate"]
    assert len(df) == 3
    assert df["entrevistas"].iloc[0] == 5018
    assert df["pollster_display_name"].iloc[0] == "AtlasIntel/Internet"
    assert str(df["data"].iloc[0].date()) == "2026-09-16"
    assert df["turno"].tolist() == [1, 1, 1]
    assert df["is_valid_candidate"].tolist() == [True, True, False]


def test_polls_to_frame_uses_contratante_when_instituto_blank():
    raw = [{"id": 2, "instituto": "", "contratante": "AtlasIntel", "data": "2026-03-28",
            "entrevistas": 1029, "apuracoes": [[{"nome": "Lula", "percentual": 40}]]}]
    df = polls_to_frame(raw, turno=1)
    assert df["instituto"].iloc[0] == "AtlasIntel"


def test_polls_to_frame_empty_input():
    assert polls_to_frame([], turno=2).empty
