import pytest

from app.mocks.data import MEMBERS, PARTNER_CONFIGS
from app.services.errors import MemberNotFoundError, PartnerConfigUnavailableError
from app.services.recommendation_service import get_recommendations


def test_partner_cap_is_enforced():
    response = get_recommendations("member_001")

    assert len(response.recommendations) <= 3


def test_cruise_exclusion_is_enforced():
    response = get_recommendations("member_001")

    categories = [
        recommendation.category.lower()
        for recommendation in response.recommendations
    ]

    assert "cruise" not in categories


def test_partner_allowing_cruise_receives_cruise():
    response = get_recommendations("member_002")

    categories = [
        recommendation.category.lower()
        for recommendation in response.recommendations
    ]

    assert "cruise" in categories


def test_exclusions_are_applied_before_cap():
    response = get_recommendations("member_001")

    assert len(response.recommendations) == 3

    assert all(
        recommendation.category.lower() != "cruise"
        for recommendation in response.recommendations
    )


def test_missing_partner_config_fails_closed():
    with pytest.raises(PartnerConfigUnavailableError):
        get_recommendations("member_003")


def test_unknown_member_raises_not_found():
    with pytest.raises(MemberNotFoundError):
        get_recommendations("no_such_member")


def test_malformed_partner_config_fails_closed(monkeypatch):
    monkeypatch.setitem(
        PARTNER_CONFIGS,
        "partner_bank_a",
        {"partner_id": "partner_bank_a", "max_recommendations": -1},
    )

    with pytest.raises(PartnerConfigUnavailableError):
        get_recommendations("member_001")


def test_zero_cap_returns_no_recommendations(monkeypatch):
    monkeypatch.setitem(
        PARTNER_CONFIGS,
        "partner_bank_b",
        {"partner_id": "partner_bank_b", "max_recommendations": 0},
    )

    response = get_recommendations("member_002")

    assert response.recommendations == []
    assert response.applied_rules.max_recommendations == 0


def test_exclusion_matching_ignores_case_and_whitespace(monkeypatch):
    monkeypatch.setitem(
        PARTNER_CONFIGS,
        "partner_bank_b",
        {"partner_id": "partner_bank_b", "excluded_categories": [" Cruise "]},
    )

    response = get_recommendations("member_002")

    assert all(r.category != "cruise" for r in response.recommendations)


def test_config_change_takes_effect_on_next_request(monkeypatch):
    assert len(get_recommendations("member_002").recommendations) > 2

    monkeypatch.setitem(
        PARTNER_CONFIGS,
        "partner_bank_b",
        {"partner_id": "partner_bank_b", "max_recommendations": 2},
    )

    assert len(get_recommendations("member_002").recommendations) == 2


def test_applied_rules_report_what_was_enforced():
    rules = get_recommendations("member_001").applied_rules

    assert rules.max_recommendations == 3
    assert rules.excluded_categories == ["cruise"]
    assert rules.removed_by_exclusion > 0


def test_previously_visited_destinations_are_skipped():
    visited = {b["destination"] for b in MEMBERS["member_001"]["travel_history"]}

    response = get_recommendations("member_001")

    assert not visited & {r.destination for r in response.recommendations}


def test_platinum_only_offers_hidden_from_lower_tiers():
    gold = get_recommendations("member_001")
    platinum = get_recommendations("member_002")

    assert "Maldives" not in {r.destination for r in gold.recommendations}
    assert "Maldives" in {r.destination for r in platinum.recommendations}


def test_previously_booked_categories_rank_first():
    response = get_recommendations("member_002")

    assert response.recommendations[0].category == "cruise"

def test_exclusion_holds_when_member_prefers_excluded_category(monkeypatch):
    # member_002 books cruises, so cruises rank first. With a cap, a missing
    # exclusion would surface here; for member_001 the cap would mask it.
    monkeypatch.setitem(
        PARTNER_CONFIGS,
        "partner_bank_b",
        {
            "partner_id": "partner_bank_b",
            "max_recommendations": 3,
            "excluded_categories": ["cruise"],
        },
    )

    response = get_recommendations("member_002")

    assert len(response.recommendations) == 3
    assert "cruise" not in {r.category for r in response.recommendations}
