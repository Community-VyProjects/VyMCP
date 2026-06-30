import pytest

from vymcp.features import FEATURES, resolve_feature


def test_registry_populated():
    assert len(FEATURES) > 50
    slugs = {f.slug for f in FEATURES}
    assert {"nat", "system", "firewall/groups", "vpn/ipsec"} <= slugs


def test_resolve_known():
    assert resolve_feature("nat").slug == "nat"


def test_resolve_case_insensitive_and_trimmed():
    assert resolve_feature("  NAT ").slug == "nat"


def test_resolve_unknown_raises():
    with pytest.raises(ValueError) as exc:
        resolve_feature("not-a-feature")
    assert "list_features" in str(exc.value)


def test_every_feature_has_description():
    assert all(f.description for f in FEATURES)
