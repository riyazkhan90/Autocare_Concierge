"""A/B experiment assignment and prompt variants."""

from __future__ import annotations

import hashlib

VARIANT_B_ADDENDUM = """

EXPERIMENT VARIANT B — extra brevity:
- Maximum 2 sentences per reply unless listing slots or recalls.
- Skip pleasantries; go straight to the question or result.
- Target under 40 words when possible."""

CONVERSION_TOOLS = frozenset({
    "book_appointment",
    "lookup_vehicle_recall",
    "get_trade_in_quote",
    "request_test_drive",
})

INTENT_FROM_TOOL = {
    "book_appointment": "booking",
    "lookup_vehicle_recall": "recall",
    "get_trade_in_quote": "tradein",
    "request_test_drive": "sales",
}


def assign_variant(thread_id: str) -> str:
    digest = hashlib.md5(thread_id.encode()).hexdigest()
    return "B" if int(digest[0], 16) % 2 else "A"


def apply_variant_prompt(base_prompt: str, variant: str) -> str:
    if variant == "B":
        return base_prompt + VARIANT_B_ADDENDUM
    return base_prompt
