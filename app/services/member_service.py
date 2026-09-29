from app.mocks.data import MEMBERS
from app.models.schemas import Member
from app.services.errors import MemberNotFoundError


def get_member(member_id: str) -> Member:
    data = MEMBERS.get(member_id)

    if not data:
        raise MemberNotFoundError(f"Member {member_id} not found")

    return Member(**data)
