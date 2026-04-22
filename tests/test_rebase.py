import pytest
from pollster.utils.rebase import rebase_to_valid_votes


def test_rebase_basic():
    raw_pcts = {"Lula": 45.0, "Bolsonaro": 35.0, "Tebet": 8.0, "Ciro": 6.0}
    result = rebase_to_valid_votes(raw_pcts)
    total = sum(result.values())
    assert abs(total - 100.0) < 0.01
    assert result["Lula"] == pytest.approx(47.87, abs=0.01)
    assert result["Bolsonaro"] == pytest.approx(37.23, abs=0.01)


def test_rebase_already_sums_to_100():
    raw_pcts = {"A": 60.0, "B": 40.0}
    result = rebase_to_valid_votes(raw_pcts)
    assert result["A"] == pytest.approx(60.0)
    assert result["B"] == pytest.approx(40.0)


def test_rebase_with_undecided_gap():
    raw_pcts = {"A": 40.0, "B": 30.0}
    result = rebase_to_valid_votes(raw_pcts)
    assert result["A"] == pytest.approx(57.14, abs=0.01)
    assert result["B"] == pytest.approx(42.86, abs=0.01)
