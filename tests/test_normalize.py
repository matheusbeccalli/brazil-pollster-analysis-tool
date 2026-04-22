from pollster.utils.normalize import normalize_pollster_name


def test_merge_ibope_ipec():
    assert normalize_pollster_name("Ibope") == "IBOPE/Ipec"
    assert normalize_pollster_name("Ipec") == "IBOPE/Ipec"
    assert normalize_pollster_name("IBOPE") == "IBOPE/Ipec"


def test_alias_datafolha():
    assert normalize_pollster_name("Instituto Datafolha") == "Datafolha"
    assert normalize_pollster_name("Datafolha Instituto de Pesquisas") == "Datafolha"


def test_unknown_pollster_passes_through():
    assert normalize_pollster_name("AtlasIntel") == "AtlasIntel"
