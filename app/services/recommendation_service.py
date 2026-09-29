import logging
from dataclasses import dataclass

from app.models.schemas import (
    AppliedRules,
    Member,
    Recommendation,
    RecommendationResponse,
)
from app.services.errors import PartnerConfigUnavailableError
from app.services.member_service import get_member
from app.services.partner_service import get_partner_config

logger = logging.getLogger(__name__)


TIER_RANK = {"silver": 1, "gold": 2, "platinum": 3}


@dataclass(frozen=True)
class Candidate:
    destination: str
    category: str
    reason: str
    min_tier: str = "silver"


CANDIDATE_CATALOG = [
    Candidate("Rome", "hotel", "Popular destination for members with similar travel history"),
    Candidate("Alaska", "cruise", "Popular premium cruise itinerary", min_tier="gold"),
    Candidate("Tokyo", "flight", "Recommended international destination"),
    Candidate("New York", "hotel", "Popular city destination"),
    Candidate("Hawaii", "package", "Recommended leisure package"),
    Candidate("Caribbean", "cruise", "Warm-weather cruise getaway"),
    Candidate("Lisbon", "flight", "Trending European city break"),
    Candidate("Maldives", "package", "Exclusive overwater villa package", min_tier="platinum"),
    Candidate("Miami", "hotel", "Beachfront hotel deals"),
]


def _tier_rank(tier: str) -> int:
    # Unknown tiers get the lowest entitlement rather than an error.
    return TIER_RANK.get(tier.lower(), 1)


def _personalize(member: Member) -> list[Recommendation]:
    """Rank the catalog for this member. Partner rules are NOT applied here."""
    member_rank = _tier_rank(member.loyalty_tier)
    visited = {booking.destination.lower() for booking in member.travel_history}
    booked_categories = {
        booking.booking_type.lower() for booking in member.travel_history
    }

    eligible = [
        candidate
        for candidate in CANDIDATE_CATALOG
        if _tier_rank(candidate.min_tier) <= member_rank
        and candidate.destination.lower() not in visited
    ]

    # Stable sort: categories the member has booked before come first.
    eligible.sort(key=lambda c: c.category.lower() not in booked_categories)

    return [
        Recommendation(
            destination=candidate.destination,
            category=candidate.category,
            reason=(
                f"{candidate.reason}. You have booked {candidate.category} travel before."
                if candidate.category.lower() in booked_categories
                else candidate.reason
            ),
        )
        for candidate in eligible
    ]


def get_recommendations(member_id: str) -> RecommendationResponse:
    logger.info(
        "recommendation_request_started member_id=%s",
        member_id,
    )

    member = get_member(member_id)

    try:
        config = get_partner_config(member.partner_id)
    except PartnerConfigUnavailableError:
        logger.error(
            "partner_config_unavailable member_id=%s partner_id=%s",
            member.member_id,
            member.partner_id,
        )
        raise

    ranked = _personalize(member)

    # Partner rules run last so nothing downstream can reintroduce an
    # excluded item, and the cap counts only items the partner allows.
    excluded = {category.strip().lower() for category in config.excluded_categories}

    allowed_recommendations = [
        recommendation
        for recommendation in ranked
        if recommendation.category.lower() not in excluded
    ]
    removed_by_exclusion = len(ranked) - len(allowed_recommendations)

    removed_by_cap = 0
    if config.max_recommendations is not None:
        removed_by_cap = max(0, len(allowed_recommendations) - config.max_recommendations)
        allowed_recommendations = allowed_recommendations[: config.max_recommendations]

    logger.info(
        "recommendations_generated member_id=%s partner_id=%s "
        "count=%s excluded_categories=%s max_recommendations=%s "
        "removed_by_exclusion=%s removed_by_cap=%s",
        member.member_id,
        member.partner_id,
        len(allowed_recommendations),
        config.excluded_categories,
        config.max_recommendations,
        removed_by_exclusion,
        removed_by_cap,
    )

    return RecommendationResponse(
        member_id=member.member_id,
        partner_id=member.partner_id,
        loyalty_tier=member.loyalty_tier,
        recommendations=allowed_recommendations,
        applied_rules=AppliedRules(
            max_recommendations=config.max_recommendations,
            excluded_categories=config.excluded_categories,
            removed_by_exclusion=removed_by_exclusion,
            removed_by_cap=removed_by_cap,
        ),
    )
