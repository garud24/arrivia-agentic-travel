from fastapi import APIRouter, HTTPException

from app.models.schemas import Member, RecommendationResponse
from app.services.errors import MemberNotFoundError, PartnerConfigUnavailableError
from app.services.member_service import get_member
from app.services.recommendation_service import get_recommendations


router = APIRouter()


@router.get("/members/{member_id}", response_model=Member)
def member_profile(member_id: str):
    try:
        return get_member(member_id)

    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get("/recommendations/{member_id}", response_model=RecommendationResponse)
def recommendations(member_id: str):
    try:
        return get_recommendations(member_id)

    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except PartnerConfigUnavailableError:
        # Fail closed: without partner rules we cannot know what is allowed.
        raise HTTPException(
            status_code=503,
            detail="Recommendation service temporarily unavailable",
        )
