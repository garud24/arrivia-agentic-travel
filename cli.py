import sys

from app.services.errors import RecommendationServiceError
from app.services.recommendation_service import get_recommendations


def main():
    print("\n=== Arrivia AI Concierge ===\n")

    member_id = sys.argv[1] if len(sys.argv) > 1 else input("Enter member ID: ").strip()

    try:
        result = get_recommendations(member_id)

        print("\nMember Profile")
        print("-------------------------")
        print(f"Member ID:    {result.member_id}")
        print(f"Loyalty Tier: {result.loyalty_tier}")
        print(f"Partner:      {result.partner_id}")

        print("\nTravel Recommendations")
        print("-------------------------")

        if not result.recommendations:
            print("No recommendations available.")
            return

        for index, recommendation in enumerate(
            result.recommendations,
            start=1,
        ):
            print(
                f"{index}. {recommendation.destination} " f"[{recommendation.category}]"
            )
            print(f"   {recommendation.reason}")

        rules = result.applied_rules
        print("\nPartner Rules Applied")
        print("-------------------------")
        print(f"Cap:          {'unlimited' if rules.max_recommendations is None else rules.max_recommendations}")
        print(f"Excluded:     {', '.join(rules.excluded_categories) or 'none'}")
        print(f"Removed:      {rules.removed_by_exclusion} by exclusion, {rules.removed_by_cap} by cap")
        print()

    except RecommendationServiceError as exc:
        print(f"\nUnable to generate recommendations: {exc}\n")


if __name__ == "__main__":
    main()
