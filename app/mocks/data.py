MEMBERS = {
    "member_001": {
        "member_id": "member_001",
        "loyalty_tier": "Gold",
        "partner_id": "partner_bank_a",
        "travel_history": [
            {
                "destination": "Miami",
                "dates": "2026-05-10 to 2026-05-15",
                "booking_type": "hotel",
            },
            {
                "destination": "Cancun",
                "dates": "2026-02-12 to 2026-02-18",
                "booking_type": "flight",
            },
        ],
    },
    "member_002": {
        "member_id": "member_002",
        "loyalty_tier": "Platinum",
        "partner_id": "partner_bank_b",
        "travel_history": [
            {
                "destination": "Barcelona",
                "dates": "2026-06-01 to 2026-06-08",
                "booking_type": "cruise",
            }
        ],
    },
    "member_003": {
        "member_id": "member_003",
        "loyalty_tier": "Silver",
        "partner_id": "unknown_partner",
        "travel_history": [],
    },
}


PARTNER_CONFIGS = {
    "partner_bank_a": {
        "partner_id": "partner_bank_a",
        "max_recommendations": 3,
        "excluded_categories": ["cruise"],
    },
    "partner_bank_b": {
        "partner_id": "partner_bank_b",
        "max_recommendations": None,
        "excluded_categories": [],
    },
}
