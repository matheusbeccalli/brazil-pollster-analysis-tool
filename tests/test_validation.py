import pandas as pd
import pytest
from pollster.utils.rebase import rebase_to_valid_votes
from pollster.utils.candidates import match_candidate_name
from pollster.utils.normalize import normalize_pollster_name


def test_rebase_handles_zero_sum():
    result = rebase_to_valid_votes({"A": 0.0, "B": 0.0})
    assert result == {"A": 0.0, "B": 0.0}


def test_rebase_single_candidate():
    result = rebase_to_valid_votes({"A": 75.0})
    assert result["A"] == pytest.approx(100.0)


def test_candidate_match_accented_names():
    officials = ["CIRO FERREIRA GOMES"]
    assert match_candidate_name("CIRO FERREIRA GOMES", officials) == "CIRO FERREIRA GOMES"
    assert match_candidate_name("Ciro Ferreira Gomes", officials) == "CIRO FERREIRA GOMES"


def test_candidate_match_with_cedilla():
    officials = ["MARCIO FRANCA"]
    assert match_candidate_name("Márcio França", officials) == "MARCIO FRANCA"


def test_normalize_unknown_pollster_preserves_case():
    assert normalize_pollster_name("Quaest") == "Quaest"


def test_normalize_case_sensitive_merge():
    assert normalize_pollster_name("Ibope") == "IBOPE/Ipec"
    assert normalize_pollster_name("IBOPE") == "IBOPE/Ipec"
