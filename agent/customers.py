"""Mock customer profiles — vehicle on file for personalised concierge."""

from __future__ import annotations

MOCK_CUSTOMERS: dict[str, dict] = {
    "+971501234567": {
        "customer_id": "CUST-1001",
        "name": "Sara Ahmed",
        "loyalty_tier": "Gold",
        "language": "en",
        "vehicles": [
            {
                "make": "Toyota",
                "model": "Camry",
                "year": 2020,
                "plate": "A 12345",
                "last_service": "2026-03-15",
                "open_recalls": 1,
            }
        ],
    },
    "+971509876543": {
        "customer_id": "CUST-1002",
        "name": "Khalid Al Mansoori",
        "loyalty_tier": "Platinum",
        "language": "ar",
        "vehicles": [
            {
                "make": "Lexus",
                "model": "RX",
                "year": 2022,
                "plate": "B 98765",
                "last_service": "2026-01-20",
                "open_recalls": 0,
            },
            {
                "make": "Honda",
                "model": "Civic",
                "year": 2019,
                "plate": "C 55443",
                "last_service": "2025-11-08",
                "open_recalls": 0,
            },
        ],
    },
}

DEMO_PHONE = "+971501234567"


def get_customer_by_phone(phone: str) -> dict | None:
    normalized = phone.strip().replace(" ", "")
    if not normalized.startswith("+"):
        normalized = f"+{normalized}" if normalized.startswith("971") else f"+971{normalized.lstrip('0')}"
    return MOCK_CUSTOMERS.get(normalized)


def format_profile_greeting(profile: dict) -> str:
    v = profile["vehicles"][0]
    return (
        f"Welcome back, {profile['name']} ({profile['loyalty_tier']} member). "
        f"I see your {v['year']} {v['make']} {v['model']} on file."
    )
