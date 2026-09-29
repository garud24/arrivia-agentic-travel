from pydantic import BaseModel, Field
from typing import List, Optional


class Booking(BaseModel):
    destination: str
    dates: str
    booking_type: str


class Member(BaseModel):
    member_id: str
    loyalty_tier: str
    partner_id: str
    travel_history: List[Booking]


class PartnerConfig(BaseModel):
    partner_id: str
    max_recommendations: Optional[int] = Field(default=None, ge=0)
    excluded_categories: List[str] = []


class Recommendation(BaseModel):
    destination: str
    category: str
    reason: str


class AppliedRules(BaseModel):
    """What partner config was enforced on this response, for debugging."""

    max_recommendations: Optional[int]
    excluded_categories: List[str]
    removed_by_exclusion: int
    removed_by_cap: int


class RecommendationResponse(BaseModel):
    member_id: str
    partner_id: str
    loyalty_tier: str
    recommendations: List[Recommendation]
    applied_rules: AppliedRules
