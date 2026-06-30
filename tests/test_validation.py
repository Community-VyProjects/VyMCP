import pytest

from vymcp.validation import MAX_VALUES, validate_identifier, validate_values


def test_identifier_strips_and_accepts():
    assert validate_identifier("  WEB_SERVERS ") == "WEB_SERVERS"


@pytest.mark.parametrize("bad", ["", "   ", "has space", "a" * 200])
def test_identifier_rejects(bad):
    with pytest.raises(ValueError):
        validate_identifier(bad)


def test_values_accepts_and_strips():
    assert validate_values([" 10.0.0.1 ", "10.0.0.2"]) == ["10.0.0.1", "10.0.0.2"]


def test_values_defers_semantics_to_vyos():
    # A CIDR is structurally fine here; VyOS decides if it's valid for the feature.
    assert validate_values(["10.0.0.0/24"]) == ["10.0.0.0/24"]


@pytest.mark.parametrize("bad", [[], ["with space"], [""]])
def test_values_rejects(bad):
    with pytest.raises(ValueError):
        validate_values(bad)


def test_values_caps_count():
    with pytest.raises(ValueError):
        validate_values(["10.0.0.1"] * (MAX_VALUES + 1))
