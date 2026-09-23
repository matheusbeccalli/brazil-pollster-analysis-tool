from pollster.utils.candidates import match_candidate_name

OFFICIALS = ["LUIZ INACIO LULA DA SILVA", "JAIR MESSIAS BOLSONARO"]


def test_exact_match_after_normalization():
    assert match_candidate_name("Luiz Inácio Lula da Silva", OFFICIALS) == "LUIZ INACIO LULA DA SILVA"


def test_ballot_name_is_subset_of_full_name():
    # TSE nome_urna is often a single name; polls use the full name (and vice versa)
    assert match_candidate_name("LULA", OFFICIALS) == "LUIZ INACIO LULA DA SILVA"
    assert match_candidate_name("Dilma", ["Dilma Rousseff", "Aécio Neves"]) == "Dilma Rousseff"
    assert match_candidate_name("José Serra", ["Lula", "Serra"]) == "Serra"
    assert match_candidate_name("Geraldo Alckmin", ["Lula", "Alckmin"]) == "Alckmin"


def test_fuzzy_match_close_name():
    assert match_candidate_name("JAIR BOLSONARO", OFFICIALS) == "JAIR MESSIAS BOLSONARO"


def test_no_match():
    assert match_candidate_name("SIMONE TEBET", ["LUIZ INACIO LULA DA SILVA"]) is None
    assert match_candidate_name("Marina Silva", OFFICIALS) is None   # shares only "SILVA"


def test_very_short_names_never_fuzzy_match():
    assert match_candidate_name("Zé", ["Zé Maria", "Lula"]) is None


def test_party_breaks_ties_between_bolsonaros():
    officials = ["Jair Bolsonaro", "Flávio Bolsonaro"]
    parties = {"Jair Bolsonaro": "PSL", "Flávio Bolsonaro": "PL"}
    assert match_candidate_name("Bolsonaro", officials, poll_party="PL", official_parties=parties) == "Flávio Bolsonaro"
    assert match_candidate_name("Bolsonaro", officials, poll_party="PSL", official_parties=parties) == "Jair Bolsonaro"


def test_party_fallback():
    parties = {"LUIZ INACIO LULA DA SILVA": "PT", "JAIR MESSIAS BOLSONARO": "PL"}
    assert match_candidate_name("O Presidente", OFFICIALS, poll_party="PT", official_parties=parties) == "LUIZ INACIO LULA DA SILVA"
