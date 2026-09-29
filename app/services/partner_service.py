from pydantic import ValidationError

from app.mocks.data import PARTNER_CONFIGS
from app.models.schemas import PartnerConfig
from app.services.errors import PartnerConfigUnavailableError


def get_partner_config(partner_id: str) -> PartnerConfig:
    data = PARTNER_CONFIGS.get(partner_id)

    if not data:
        raise PartnerConfigUnavailableError(
            f"Partner configuration not found for {partner_id}"
        )

    try:
        return PartnerConfig(**data)
    except ValidationError as exc:
        # A malformed config must never be treated as "no rules".
        raise PartnerConfigUnavailableError(
            f"Partner configuration invalid for {partner_id}"
        ) from exc
