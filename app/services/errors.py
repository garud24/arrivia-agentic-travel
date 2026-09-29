class RecommendationServiceError(Exception):
    """Base class for errors the API and MCP layers translate for callers."""


class MemberNotFoundError(RecommendationServiceError):
    pass


class PartnerConfigUnavailableError(RecommendationServiceError):
    """Partner rules could not be read or validated. We fail closed."""
