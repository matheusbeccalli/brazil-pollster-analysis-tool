from pollster.utils.candidates import match_candidate_name


def test_exact_match_after_normalization():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("Luiz Inácio Lula da Silva", officials) == "LUIZ INACIO LULA DA SILVA"


def test_fuzzy_match_partial_name():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("LULA", officials) is None  # too short for fuzzy


def test_fuzzy_match_close_name():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    assert match_candidate_name("JAIR BOLSONARO", officials) == "JAIR MESSIAS BOLSONARO"


def test_no_match():
    officials = ["LUIZ INACIO LULA DA SILVA"]
    assert match_candidate_name("SIMONE TEBET", officials) is None


def test_party_fallback():
    officials = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]
    parties = {"LUIZ INACIO LULA DA SILVA": "PT", "JAIR MESSIAS BOLSONARO": "PL"}
    assert match_candidate_name("LULA", officials, poll_party="PT", official_parties=parties) == "LUIZ INACIO LULA DA SILVA"
