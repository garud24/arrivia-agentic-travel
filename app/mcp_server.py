from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from app.services.errors import RecommendationServiceError
from app.services.member_service import get_member
from app.services.recommendation_service import get_recommendations

mcp = MCPServer("Arrivia Travel Recommendations")

MemberId = Annotated[
    str,
    Field(description="arrivia member ID, e.g. 'member_001'"),
]


@mcp.tool()
def get_member_profile(member_id: MemberId) -> dict:
    """
    Retrieve a member's loyalty tier, partner,
    and recent travel history.
    """
    try:
        member = get_member(member_id)
    except RecommendationServiceError as exc:
        # ToolError messages reach the agent; other exceptions are masked.
        raise ToolError(str(exc)) from exc
    return member.model_dump()


@mcp.tool()
def get_travel_recommendations(member_id: MemberId) -> dict:
    """
    Generate personalized travel recommendations for a member.
    Partner rules (recommendation cap, excluded categories) are already
    enforced; present the results as returned and do not add to them.
    """
    try:
        response = get_recommendations(member_id)
    except RecommendationServiceError as exc:
        raise ToolError(str(exc)) from exc
    return response.model_dump()


if __name__ == "__main__":
    mcp.run()
